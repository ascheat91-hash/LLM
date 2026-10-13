import time
import threading
from typing import Optional, Callable, Dict, Any, List
import numpy as np
import sounddevice as sd

from app.core.logger import logger
from app.config.settings import get_settings


class WakeWordEngine:
    """Local Wake Word detection engine using openWakeWord."""

    def __init__(self):
        self._model = None
        self._is_running = False
        self._stream: Optional[sd.InputStream] = None
        self._callback: Optional[Callable[[str, float], None]] = None
        self._lock = threading.Lock()
        self._model_name: str = "hey_jarvis"
        self._threshold: float = 0.5
        self._chunk_size: int = 1280  # 80ms at 16kHz for openWakeWord

    def list_available_models(self) -> List[str]:
        try:
            import openwakeword
            paths = openwakeword.get_pretrained_model_paths()
            models = []
            for p in paths:
                name = p.split("/")[-1].split("\\")[-1].replace(".tflite", "").replace("_v0.1", "")
                models.append(name)
            return models
        except Exception:
            return ["hey_jarvis", "alexa", "hey_mycroft", "timer", "weather"]

    def initialize_model(self, model_name: Optional[str] = None) -> bool:
        with self._lock:
            settings = get_settings()
            target = model_name or settings.wakeword.model_name
            try:
                import openwakeword
                from openwakeword.model import Model

                logger.info(f"Loading openWakeWord model '{target}'...")
                # openwakeword can load by name or path
                self._model = Model(wakeword_models=[target], inference_framework="tflite")
                self._model_name = target
                logger.info("openWakeWord model loaded successfully.")
                return True
            except Exception as e:
                logger.warning(f"Failed to load specific wake word model '{target}': {e}. Attempting fallback...")
                try:
                    from openwakeword.model import Model
                    self._model = Model()
                    self._model_name = "default"
                    return True
                except Exception as ex:
                    logger.error(f"Cannot initialize wake word model: {ex}")
                    self._model = None
                    return False

    def _audio_callback(self, indata, frames, time_info, status):
        if not self._is_running or self._model is None:
            return

        # Audio chunk to int16 16kHz
        chunk = (indata[:, 0] * 32767).astype(np.int16)
        try:
            prediction = self._model.predict(chunk)
            for mdl_key, score in prediction.items():
                if score >= self._threshold:
                    logger.info(f"Wake word detected! Model: {mdl_key}, Confidence: {score:.3f}")
                    # Reset model buffer to avoid multiple rapid re-triggers
                    self._model.reset()
                    if self._callback:
                        self._callback(mdl_key, float(score))
                    break
        except Exception as e:
            logger.debug(f"Prediction error in wakeword: {e}")

    def start(self, on_wake: Optional[Callable[[str, float], None]] = None) -> bool:
        """Starts the background wake-word listening loop."""
        if self._is_running:
            return True

        if self._model is None:
            if not self.initialize_model():
                return False

        settings = get_settings()
        self._threshold = settings.wakeword.threshold
        self._callback = on_wake
        self._is_running = True

        dev_idx = settings.stt.microphone_index

        try:
            self._stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                device=dev_idx,
                callback=self._audio_callback,
                blocksize=self._chunk_size,
            )
            self._stream.start()
            logger.info(f"Wake-word engine started (Model: {self._model_name}, Threshold: {self._threshold}).")
            return True
        except Exception as e:
            self._is_running = False
            self._stream = None
            logger.exception(f"Failed to start wake-word audio stream: {e}")
            return False

    def stop(self) -> None:
        """Stops the wake-word engine."""
        self._is_running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        logger.info("Wake-word engine stopped.")

    def is_running(self) -> bool:
        return self._is_running


_wakeword_instance: Optional[WakeWordEngine] = None


def get_wakeword_engine() -> WakeWordEngine:
    global _wakeword_instance
    if _wakeword_instance is None:
        _wakeword_instance = WakeWordEngine()
    return _wakeword_instance
