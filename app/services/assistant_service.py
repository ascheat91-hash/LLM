import time
import json
import threading
from typing import Dict, Any, Optional, Generator, Callable, List

from app.core.logger import logger
from app.core.state import runtime_state, AssistantStateEnum, update_runtime_state
from app.config.settings import get_settings
from app.llm.engine import get_llm_engine
from app.llm.model_manager import get_model_manager
from app.llm.prompts import build_system_prompt
from app.speech.stt import get_speech_recognizer
from app.speech.tts import get_speech_synthesizer
from app.speech.wakeword import get_wakeword_engine
from app.tools.router import get_tool_router
from app.tools.permissions import get_permission_manager
from app.memory.database import get_memory_db


class AssistantService:
    """Core orchestration pipeline connecting Speech, LLM, Tools, and Memory."""

    def __init__(self):
        self.settings = get_settings()
        self.engine = get_llm_engine()
        self.model_mgr = get_model_manager()
        self.stt = get_speech_recognizer()
        self.tts = get_speech_synthesizer()
        self.wakeword = get_wakeword_engine()
        self.router = get_tool_router()
        self.perms = get_permission_manager()
        self.memory = get_memory_db()

        self._processing_lock = threading.Lock()
        self._voice_session_active = False

    def startup(self):
        """Initializes components and auto-loads the configured model if present."""
        logger.info("Initializing FOXSI Voice Assistant Service...")
        settings = get_settings()

        # 1. Try loading configured GGUF model
        model_path = settings.resolve_path(settings.llm.model_path)
        if model_path.exists():
            try:
                self.model_mgr.load_model_by_path(str(model_path))
                update_runtime_state(
                    llm_status="ready",
                    current_model=model_path.name,
                    current_model_path=str(model_path),
                )
            except Exception as e:
                logger.warning(f"Could not auto-load default model: {e}")
                update_runtime_state(llm_status="error", last_error=str(e))
        else:
            logger.info("No default model file at configured path. Available models can be selected in UI.")
            update_runtime_state(llm_status="unloaded")

        # 2. Check TTS readiness
        try:
            voices = self.tts.list_voices()
            update_runtime_state(tts_status="ready")
        except Exception as e:
            logger.warning(f"TTS initialization notice: {e}")
            update_runtime_state(tts_status="error")

        # 3. Check STT readiness
        try:
            update_runtime_state(stt_status="ready")
        except Exception as e:
            update_runtime_state(stt_status="error")

        # 4. Wake word initialization if enabled
        if settings.wakeword.enabled:
            self.start_wakeword()

        update_runtime_state(state=AssistantStateEnum.IDLE)
        logger.info("FOXSI Assistant Service startup completed.")

    def start_wakeword(self) -> bool:
        def on_wake(model_name: str, confidence: float):
            logger.info(f"Wake word '{model_name}' triggered assistant loop!")
            # Start push-to-talk voice capture asynchronously
            threading.Thread(target=self.trigger_voice_interaction, daemon=True).start()

        success = self.wakeword.start(on_wake=on_wake)
        update_runtime_state(wakeword_status="active" if success else "error")
        return success

    def stop_wakeword(self) -> None:
        self.wakeword.stop()
        update_runtime_state(wakeword_status="inactive")

    def trigger_voice_interaction(self):
        """Pipeline triggered by Wake Word or Voice PTT button."""
        with self._processing_lock:
            try:
                update_runtime_state(state=AssistantStateEnum.LISTENING, is_recording=True)
                logger.info("Listening for user voice...")

                # Record audio until silence or manual stop
                stop_event = threading.Event()

                def on_silence():
                    stop_event.set()

                self.stt.start_recording(silence_callback=on_silence)

                # Wait up to 8 seconds max for speech + silence
                start_t = time.time()
                while not stop_event.is_set() and (time.time() - start_t < 8.0):
                    time.sleep(0.1)

                audio_data = self.stt.stop_recording()
                update_runtime_state(state=AssistantStateEnum.TRANSCRIBING, is_recording=False)

                if audio_data is None or len(audio_data) < 8000:
                    logger.info("Audio too short or silent.")
                    update_runtime_state(state=AssistantStateEnum.IDLE)
                    return

                res = self.stt.transcribe(audio_data)
                transcript = res.get("text", "").strip()

                if not transcript:
                    logger.info("No speech recognized in audio.")
                    update_runtime_state(state=AssistantStateEnum.IDLE)
                    return

                logger.info(f"Recognized user transcript: '{transcript}'")
                update_runtime_state(last_user_input=transcript)

                # Process query through LLM and tool pipeline
                self.process_query(transcript, speak_response=True)

            except Exception as e:
                logger.exception(f"Voice interaction pipeline error: {e}")
                update_runtime_state(state=AssistantStateEnum.ERROR, last_error=str(e))
                time.sleep(1.5)
                update_runtime_state(state=AssistantStateEnum.IDLE)

    def process_query(self, user_text: str, speak_response: bool = True) -> Dict[str, Any]:
        """Main textual processing pipeline: User -> LLM -> Tools -> Response -> TTS."""
        with self._processing_lock:
            update_runtime_state(
                state=AssistantStateEnum.THINKING,
                is_thinking=True,
                last_user_input=user_text,
            )

            # Store user message in local SQLite memory
            self.memory.add_message("user", user_text)

            # Check if LLM is loaded
            if not self.engine.is_loaded():
                msg = "No local LLM model is currently loaded. Please select and load a GGUF model in the Model tab."
                update_runtime_state(
                    state=AssistantStateEnum.IDLE,
                    is_thinking=False,
                    last_assistant_output=msg,
                )
                self.memory.add_message("assistant", msg)
                if speak_response:
                    self.tts.speak(msg)
                return {"response": msg, "tool_executed": None}

            # Build context messages
            settings = get_settings()
            tools_spec = self.router.get_tool_catalog()
            system_prompt = build_system_prompt(
                assistant_name=settings.assistant.name,
                custom_system_prompt=settings.assistant.system_prompt,
                response_style=settings.assistant.response_style,
                tools=tools_spec,
            )

            messages = [{"role": "system", "content": system_prompt}]

            # Add recent history from SQLite
            history = self.memory.get_recent_messages(limit=6)
            for h in history[:-1]:  # exclude the one we just added
                messages.append({"role": h["role"], "content": h["content"]})

            messages.append({"role": "user", "content": user_text})

            try:
                # LLM Inference
                llm_output = self.engine.generate(
                    messages=messages,
                    temperature=settings.llm.temperature,
                    max_tokens=settings.llm.max_tokens,
                )
                logger.info(f"LLM Raw Output: {llm_output}")

                # Check for tool call
                tool_call = self.router.extract_tool_call(llm_output)
                tool_result = None

                if tool_call:
                    tool_name = tool_call.get("tool")
                    args = tool_call.get("arguments", {})
                    logger.info(f"Parsed tool call: {tool_name}({args})")

                    tool_exec = self.router.execute_tool(tool_name, args)
                    tool_result = tool_exec

                    if tool_exec.get("status") == "pending_confirmation":
                        cid = tool_exec.get("confirmation_id")
                        confirm_msg = f"I need your confirmation before proceeding with: '{tool_name}'. Please approve or reject request #{cid} in the dashboard."
                        final_response = confirm_msg
                    elif tool_exec.get("status") == "blocked":
                        final_response = f"Action blocked by security policy: {tool_exec.get('message')}"
                    else:
                        # Append tool result to context and request conversational response
                        tool_context = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_text},
                            {"role": "assistant", "content": llm_output},
                            {
                                "role": "user",
                                "content": (
                                    f"Tool '{tool_name}' executed. Result: {json.dumps(tool_exec.get('result', {}))}. "
                                    f"Now provide a helpful, natural spoken answer to the user summarizing this result."
                                ),
                            },
                        ]
                        final_response = self.engine.generate(
                            messages=tool_context,
                            temperature=settings.llm.temperature,
                            max_tokens=settings.llm.max_tokens,
                        )
                else:
                    final_response = llm_output

                # Save assistant response to memory
                self.memory.add_message("assistant", final_response, tool_calls=tool_result)
                update_runtime_state(
                    state=AssistantStateEnum.SPEAKING if speak_response else AssistantStateEnum.IDLE,
                    is_thinking=False,
                    last_assistant_output=final_response,
                )

                # Voice output
                if speak_response and final_response:
                    self.tts.speak(final_response)

                update_runtime_state(state=AssistantStateEnum.IDLE)

                return {
                    "response": final_response,
                    "tool_executed": tool_result,
                }

            except Exception as e:
                logger.exception(f"Error in processing query: {e}")
                err_msg = f"Sorry, I encountered an internal error: {str(e)}"
                update_runtime_state(state=AssistantStateEnum.ERROR, last_error=str(e), is_thinking=False)
                return {"response": err_msg, "error": str(e)}

    def stream_query(self, user_text: str) -> Generator[Dict[str, Any], None, None]:
        """Streams tokens from LLM via SSE or WebSocket."""
        # Record user message in memory
        self.memory.add_message("user", user_text)

        if not self.engine.is_loaded():
            yield {"type": "error", "content": "No local model loaded. Please load a GGUF model."}
            return

        settings = get_settings()
        tools_spec = self.router.get_tool_catalog()
        system_prompt = build_system_prompt(
            assistant_name=settings.assistant.name,
            custom_system_prompt=settings.assistant.system_prompt,
            response_style=settings.assistant.response_style,
            tools=tools_spec,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        full_text = ""
        for token in self.engine.stream_generate(
            messages=messages,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        ):
            full_text += token
            yield {"type": "token", "content": token}

        # Check for tool call in completed stream
        tool_call = self.router.extract_tool_call(full_text)
        if tool_call:
            tool_name = tool_call.get("tool")
            args = tool_call.get("arguments", {})
            yield {"type": "tool_start", "tool": tool_name, "arguments": args}

            tool_exec = self.router.execute_tool(tool_name, args)
            yield {"type": "tool_result", "result": tool_exec}

            # Generate follow up
            tool_context = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": full_text},
                {"role": "user", "content": f"Tool result: {json.dumps(tool_exec)}. Summarize for user."},
            ]
            final_summary = ""
            for tok in self.engine.stream_generate(messages=tool_context):
                final_summary += tok
                yield {"type": "token", "content": tok}
            full_text = final_summary

        self.memory.add_message("assistant", full_text)
        yield {"type": "done", "content": full_text}


_service_instance: Optional[AssistantService] = None


def get_assistant_service() -> AssistantService:
    global _service_instance
    if _service_instance is None:
        _service_instance = AssistantService()
    return _service_instance
