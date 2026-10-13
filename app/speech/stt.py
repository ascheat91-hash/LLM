import os
import io
import time
import threading
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import sounddevice as sd

from app.core.logger import logger
from app.config.settings import get_settings


class SpeechRecognizer:
    """Local Speech-to-Text engine powered by faster-whisper and sounddevice."""

    def __init__(self):
        self._model = None
        self._model_name: Optional[str] = None
        self._device: str = "cpu"
        self._compute_type: str = "int8"
        self._lock = threading.Lock()

        # Recording state
        self._is_recording = False
        self._audio_buffer: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._sample_rate: int = 16000
        self._channels: int = 1
        self._microphone_index: Optional[int] = None

        # Silence detection
        self._silence_threshold: float = 0.015
        self._silence_start_time: Optional[float] = None
        self._silence_duration_seconds: float = 1.5
        self._silence_callback = None

    def initialize_model(
        self,
        model_name: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> bool:
        """Initializes or switches the faster-whisper model."""
        with self._lock:
            settings = get_settings()
            target_model = model_name or settings.stt.model
            if self._model is not None and self._model_name == target_model:
                return True

            logger.info(f"Initializing faster-whisper model '{target_model}' on {device} ({compute_type})...")
            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    target_model,
                    device=device,
                    compute_type=compute_type,
                )
                self._model_name = target_model
                self._device = device
                self._compute_type = compute_type
                logger.info(f"Whisper model '{target_model}' loaded successfully.")
                return True
            except Exception as e:
                logger.exception(f"Failed to load Whisper model '{target_model}': {e}")
                self._model = None
                raise

    def set_microphone(self, device_index: Optional[int]) -> None:
        """Sets the active input microphone device index."""
        self._microphone_index = device_index
        logger.info(f"Selected microphone device index: {device_index}")

    def list_microphones(self) -> List[Dict[str, Any]]:
        devices = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "id": idx,
                        "name": dev.get("name"),
                        "channels": dev.get("max_input_channels"),
                        "default": (idx == sd.default.device[0]),
                    })
        except Exception as e:
            logger.warning(f"Failed to query microphone devices: {e}")
        return devices

    def _audio_callback(self, indata, frames, time_info, status):
        """Streaming callback receiving 16kHz audio frames."""
        if not self._is_recording:
            return

        chunk = indata[:, 0].copy()
        self._audio_buffer.append(chunk)

        # Silence / Voice activity detection
        rms = float(np.sqrt(np.mean(chunk**2)))
        now = time.time()

        if rms < self._silence_threshold:
            if self._silence_start_time is None:
                self._silence_start_time = now
            elif (now - self._silence_start_time) >= self._silence_duration_seconds:
                # Continuous silence detected
                if self._silence_callback and len(self._audio_buffer) > 10:
                    try:
                        self._silence_callback()
                    except Exception:
                        pass
        else:
            self._silence_start_time = None

    def start_recording(self, silence_callback=None) -> bool:
        """Starts capturing audio from the configured microphone."""
        if self._is_recording:
            return True

        self._audio_buffer = []
        self._silence_start_time = None
        self._silence_callback = silence_callback
        self._is_recording = True

        settings = get_settings()
        dev_idx = self._microphone_index if self._microphone_index is not None else settings.stt.microphone_index
        self._silence_threshold = settings.stt.silence_threshold
        self._silence_duration_seconds = settings.stt.silence_duration_seconds

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=dev_idx,
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
            logger.info("Microphone recording started.")
            return True
        except Exception as e:
            self._is_recording = False
            self._stream = None
            logger.exception(f"Failed to start microphone stream: {e}")
            raise

    def stop_recording(self) -> np.ndarray:
        """Stops capturing audio and returns the recorded float32 array."""
        self._is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error stopping audio stream: {e}")
            finally:
                self._stream = None

        logger.info(f"Microphone recording stopped. Collected {len(self._audio_buffer)} chunks.")
        if not self._audio_buffer:
            return np.array([], dtype=np.float32)

        audio_data = np.concatenate(self._audio_buffer, axis=0)
        self._audio_buffer = []
        return audio_data

    def transcribe(
        self,
        audio_data: Optional[np.ndarray] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribes audio array using local faster-whisper."""
        if audio_data is None or len(audio_data) == 0:
            return {"text": "", "language": "en", "duration": 0.0}

        if self._model is None:
            self.initialize_model()

        settings = get_settings()
        lang = language or settings.stt.language
        if lang == "auto":
            lang = None

        logger.info(f"Transcribing audio ({len(audio_data)} samples, {round(len(audio_data)/self._sample_rate, 2)}s)...")
        t0 = time.time()
        try:
            segments, info = self._model.transcribe(
                audio_data,
                language=lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            transcript_parts = [segment.text.strip() for segment in segments]
            full_text = " ".join(transcript_parts).strip()
            duration = round(time.time() - t0, 3)

            logger.info(f"Transcription complete in {duration}s: '{full_text}' (lang={info.language})")
            return {
                "text": full_text,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration_seconds": duration,
            }
        except Exception as e:
            logger.exception(f"STT transcription error: {e}")
            return {"text": "", "error": str(e), "duration_seconds": 0.0}


_recognizer_instance: Optional[SpeechRecognizer] = None


def get_speech_recognizer() -> SpeechRecognizer:
    global _recognizer_instance
    if _recognizer_instance is None:
        _recognizer_instance = SpeechRecognizer()
    return _recognizer_instance
