import json
import io
import time
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.logger import logger
from app.core.state import get_runtime_state, runtime_state
from app.core.system_info import get_full_system_status
from app.config.settings import get_settings, update_settings
from app.services.assistant_service import get_assistant_service
from app.llm.model_manager import get_model_manager
from app.llm.engine import get_llm_engine
from app.speech.stt import get_speech_recognizer
from app.speech.tts import get_speech_synthesizer
from app.speech.wakeword import get_wakeword_engine
from app.tools.router import get_tool_router
from app.tools.permissions import get_permission_manager
from app.memory.database import get_memory_db

api_router = APIRouter(prefix="/api")


# Schemas
class ChatRequest(BaseModel):
    message: str
    speak: bool = False


class LoadModelRequest(BaseModel):
    path: str
    context_size: Optional[int] = None
    threads: Optional[int] = None
    gpu_layers: Optional[int] = None


class DownloadModelRequest(BaseModel):
    model_id: str


class SynthesizeRequest(BaseModel):
    text: str


class ResolveConfirmationRequest(BaseModel):
    approved: bool


# 1. System & Assistant Status
@api_router.get("/status")
def get_status():
    system_telemetry = get_full_system_status()
    engine = get_llm_engine()
    model_info = engine.get_model_info()

    return {
        "status": "online",
        "assistant": {
            "state": runtime_state.state.value,
            "is_recording": runtime_state.is_recording,
            "is_speaking": runtime_state.is_speaking,
            "is_thinking": runtime_state.is_thinking,
            "stt_status": runtime_state.stt_status,
            "tts_status": runtime_state.tts_status,
            "llm_status": "ready" if engine.is_loaded() else "unloaded",
            "wakeword_status": runtime_state.wakeword_status,
            "current_model": model_info.get("model_name"),
            "current_model_path": model_info.get("model_path"),
            "current_model_size_mb": model_info.get("model_size_mb"),
            "last_error": runtime_state.last_error,
        },
        "system": system_telemetry,
    }


# 2. Chat & LLM
@api_router.post("/chat")
def post_chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    service = get_assistant_service()
    result = service.process_query(req.message, speak_response=req.speak)
    return result


@api_router.post("/chat/stream")
def post_chat_stream(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    service = get_assistant_service()

    def event_generator():
        for event in service.stream_query(req.message):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# 3. Speech & Audio
@api_router.post("/audio/transcribe")
async def post_audio_transcribe(file: UploadFile = File(...)):
    try:
        content = await file.read()
        import soundfile as sf
        import numpy as np

        data, samplerate = sf.read(io.BytesIO(content), dtype="float32")
        # Ensure mono
        if len(data.shape) > 1:
            data = data.mean(axis=1)

        # Resample to 16000 if needed
        if samplerate != 16000:
            import scipy.signal
            num_samples = int(len(data) * 16000 / samplerate)
            data = scipy.signal.resample(data, num_samples).astype(np.float32)

        stt = get_speech_recognizer()
        result = stt.transcribe(data)
        return result
    except Exception as e:
        logger.exception(f"Audio transcription endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/audio/synthesize")
def post_audio_synthesize(req: SynthesizeRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    tts = get_speech_synthesizer()
    wav_bytes = tts.synthesize_to_wav_bytes(req.text)
    if not wav_bytes:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech audio")
    return Response(content=wav_bytes, media_type="audio/wav")


@api_router.post("/voice/listen")
def post_voice_listen():
    """Trigger microphone listening cycle."""
    service = get_assistant_service()
    import threading
    threading.Thread(target=service.trigger_voice_interaction, daemon=True).start()
    return {"status": "started", "message": "Listening on microphone"}


@api_router.post("/voice/stop")
def post_voice_stop():
    """Immediately stop TTS speech and microphone recording."""
    tts = get_speech_synthesizer()
    tts.stop()
    stt = get_speech_recognizer()
    stt.stop_recording()
    return {"status": "stopped"}


@api_router.get("/devices")
def get_devices():
    stt = get_speech_recognizer()
    tts = get_speech_synthesizer()
    return {
        "microphones": stt.list_microphones(),
        "voices": tts.list_voices(),
    }


# 4. Model Management
@api_router.get("/models")
def get_models():
    mgr = get_model_manager()
    return {
        "local_models": mgr.scan_models(),
        "catalog": mgr.get_catalog(),
        "download_status": mgr.get_active_download_status(),
    }


@api_router.post("/models/load")
def post_models_load(req: LoadModelRequest):
    mgr = get_model_manager()
    try:
        success = mgr.load_model_by_path(
            model_path=req.path,
            context_size=req.context_size,
            threads=req.threads,
            gpu_layers=req.gpu_layers,
        )
        return {"status": "success", "loaded": success}
    except Exception as e:
        logger.exception(f"Error loading model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/models/unload")
def post_models_unload():
    mgr = get_model_manager()
    success = mgr.unload_model()
    return {"status": "success", "unloaded": success}


@api_router.post("/models/download")
def post_models_download(req: DownloadModelRequest):
    mgr = get_model_manager()
    try:
        mgr.start_catalog_download(req.model_id)
        return {"status": "download_started", "model_id": req.model_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/models/download/status")
def get_models_download_status():
    mgr = get_model_manager()
    status = mgr.get_active_download_status()
    return {"active": status is not None, "download": status}


@api_router.post("/models/download/cancel")
def post_models_download_cancel():
    mgr = get_model_manager()
    cancelled = mgr.cancel_download()
    return {"cancelled": cancelled}


# 5. Tools & Confirmations
@api_router.get("/tools")
def get_tools():
    router = get_tool_router()
    return {"tools": router.get_tool_catalog()}


@api_router.get("/tools/confirmations")
def get_confirmations():
    perms = get_permission_manager()
    return {"pending": list(perms.get_pending_requests().values())}


@api_router.post("/tools/confirmations/{confirmation_id}/resolve")
def resolve_confirmation(confirmation_id: str, req: ResolveConfirmationRequest):
    router = get_tool_router()
    perms = get_permission_manager()

    if not req.approved:
        perms.resolve_request(confirmation_id, approved=False)
        return {"status": "rejected", "message": "Action rejected by user."}

    exec_result = router.execute_confirmed_request(confirmation_id)
    return {"status": "resolved", "execution": exec_result}


# 6. Memory & Database
@api_router.get("/memory/history")
def get_memory_history(limit: int = 50):
    db = get_memory_db()
    return {"history": db.get_recent_messages(limit=limit)}


@api_router.delete("/memory/history")
def clear_memory_history():
    db = get_memory_db()
    cleared = db.clear_conversation()
    return {"status": "cleared", "messages_removed": cleared}


@api_router.get("/memory/export")
def export_memory():
    db = get_memory_db()
    return db.export_memory()


# 7. Settings
@api_router.get("/settings")
def get_app_settings():
    s = get_settings()
    return s.model_dump()


@api_router.post("/settings")
def post_app_settings(updates: Dict[str, Any]):
    try:
        new_s = update_settings(updates)
        # Apply wake-word setting changes if applicable
        service = get_assistant_service()
        if new_s.wakeword.enabled:
            service.start_wakeword()
        else:
            service.stop_wakeword()
        return {"status": "updated", "settings": new_s.model_dump()}
    except Exception as e:
        logger.exception(f"Error updating settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
