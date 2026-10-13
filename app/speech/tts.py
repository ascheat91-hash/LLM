import os
import io
import time
import wave
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import sounddevice as sd
import soundfile as sf

from app.core.logger import logger
from app.config.settings import get_settings


class SpeechSynthesizer:
    """Local Text-to-Speech synthesizer with Piper and pyttsx3 fallback."""

    def __init__(self):
        self._piper_voice = None
        self._current_piper_model_path: Optional[str] = None
        self._pyttsx3_engine = None
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def get_voices_dir(self) -> Path:
        settings = get_settings()
        v_dir = settings.resolve_path("voices")
        v_dir.mkdir(parents=True, exist_ok=True)
        return v_dir

    def list_voices(self) -> Dict[str, Any]:
        """Lists available Piper models and system SAPI voices."""
        voices_dir = self.get_voices_dir()
        piper_voices = []

        for onnx_file in voices_dir.glob("*.onnx"):
            json_file = onnx_file.with_suffix(".onnx.json")
            piper_voices.append({
                "id": onnx_file.stem,
                "name": onnx_file.name,
                "type": "piper",
                "path": str(onnx_file.resolve()),
                "has_config": json_file.exists(),
                "size_mb": round(onnx_file.stat().st_size / (1024 * 1024), 2),
            })

        sapi_voices = []
        try:
            import pyttsx3
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                sapi_voices.append({
                    "id": v.id,
                    "name": v.name,
                    "type": "sapi",
                    "languages": getattr(v, "languages", []),
                })
        except Exception as e:
            logger.warning(f"Failed to query pyttsx3 voices: {e}")

        return {
            "piper": piper_voices,
            "system_sapi": sapi_voices,
        }

    def _load_piper_voice(self, model_path: str, config_path: Optional[str] = None):
        with self._lock:
            p_model = Path(model_path)
            if not p_model.is_absolute():
                settings = get_settings()
                p_model = settings.resolve_path(model_path)

            p_config = Path(config_path) if config_path else p_model.with_suffix(".onnx.json")
            if not p_config.is_absolute():
                settings = get_settings()
                p_config = settings.resolve_path(str(p_config))

            if not p_model.exists():
                raise FileNotFoundError(f"Piper ONNX model not found: {p_model}")

            logger.info(f"Loading Piper voice from {p_model.name}...")
            from piper.voice import PiperVoice
            self._piper_voice = PiperVoice.load(
                str(p_model.resolve()),
                str(p_config.resolve()) if p_config.exists() else None,
            )
            self._current_piper_model_path = str(p_model.resolve())
            logger.info("Piper voice loaded successfully.")

    def set_voice(self, voice_path_or_id: str):
        settings = get_settings()
        if voice_path_or_id.endswith(".onnx"):
            settings.tts.engine = "piper"
            settings.tts.voice_model = voice_path_or_id
            self._load_piper_voice(voice_path_or_id)
        else:
            settings.tts.engine = "pyttsx3"
            settings.tts.pyttsx3_voice_id = voice_path_or_id
        logger.info(f"TTS voice updated to: {voice_path_or_id}")

    def synthesize_to_wav_bytes(self, text: str) -> bytes:
        """Synthesizes text and returns WAV audio bytes for web streaming or playback."""
        settings = get_settings()
        engine_type = settings.tts.engine

        if engine_type == "piper":
            try:
                if self._piper_voice is None or self._current_piper_model_path != str(settings.resolve_path(settings.tts.voice_model)):
                    self._load_piper_voice(settings.tts.voice_model, settings.tts.voice_config)

                chunks = list(self._piper_voice.synthesize(text))
                if not chunks:
                    return b""

                audio_data = np.concatenate([c.audio_float_array for c in chunks])
                sample_rate = chunks[0].sample_rate

                buf = io.BytesIO()
                sf.write(buf, audio_data, sample_rate, format="WAV", subtype="PCM_16")
                return buf.getvalue()
            except Exception as e:
                logger.warning(f"Piper TTS synthesis failed: {e}. Falling back to pyttsx3.")

        # Fallback to pyttsx3
        return self._synthesize_pyttsx3_bytes(text)

    def _synthesize_pyttsx3_bytes(self, text: str) -> bytes:
        import pyttsx3
        import tempfile
        temp_wav = Path(tempfile.gettempdir()) / f"tts_{int(time.time()*1000)}.wav"
        try:
            engine = pyttsx3.init()
            settings = get_settings()
            if settings.tts.pyttsx3_voice_id:
                engine.setProperty("voice", settings.tts.pyttsx3_voice_id)
            engine.save_to_file(text, str(temp_wav))
            engine.runAndWait()
            if temp_wav.exists():
                data = temp_wav.read_bytes()
                temp_wav.unlink(missing_ok=True)
                return data
        except Exception as e:
            logger.error(f"pyttsx3 synthesis failed: {e}")
            if temp_wav.exists():
                temp_wav.unlink(missing_ok=True)
        return b""

    def speak(self, text: str, block: bool = False) -> bool:
        """Synthesizes text and plays it through local speakers."""
        if not text.strip():
            return False

        self.stop()
        self._stop_event.clear()

        def _play_worker():
            self._is_speaking = True
            logger.info(f"Speaking: '{text[:60]}...'")
            try:
                wav_bytes = self.synthesize_to_wav_bytes(text)
                if not wav_bytes:
                    logger.warning("Empty audio generated by TTS.")
                    return

                data, fs = sf.read(io.BytesIO(wav_bytes), dtype="float32")

                # Play via sounddevice
                sd.play(data, fs)
                # Poll for completion or stop event
                while sd.get_stream().active:
                    if self._stop_event.is_set():
                        sd.stop()
                        break
                    time.sleep(0.05)
            except Exception as e:
                logger.error(f"Error during TTS playback: {e}")
            finally:
                self._is_speaking = False

        self._playback_thread = threading.Thread(target=_play_worker, daemon=True)
        self._playback_thread.start()

        if block:
            self._playback_thread.join()

        return True

    def stop(self) -> None:
        """Stops any active TTS audio playback."""
        self._stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass
        self._is_speaking = False
        logger.info("TTS playback stopped.")

    def is_speaking(self) -> bool:
        return self._is_speaking


_synthesizer_instance: Optional[SpeechSynthesizer] = None


def get_speech_synthesizer() -> SpeechSynthesizer:
    global _synthesizer_instance
    if _synthesizer_instance is None:
        _synthesizer_instance = SpeechSynthesizer()
    return _synthesizer_instance
