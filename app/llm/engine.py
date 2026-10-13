import os
import gc
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Generator, List
import psutil

from app.core.logger import logger

class LLMEngine:
    """Dedicated LLM Engine abstraction shielding the app from llama.cpp internals."""

    def __init__(self):
        self._model = None
        self._model_path: Optional[str] = None
        self._lock = threading.Lock()
        self._info: Dict[str, Any] = {
            "status": "unloaded",
            "model_path": None,
            "context_size": 0,
            "threads": 0,
            "gpu_layers": 0,
            "backend": "llama-cpp-python",
        }

    def _determine_threads(self, requested_threads: int) -> int:
        if requested_threads and requested_threads > 0:
            return requested_threads
        # Reasonable auto-detect: physical cores, min 2, max 8
        cores = psutil.cpu_count(logical=False) or 4
        return max(2, min(cores, 8))

    def _determine_gpu_layers(self, requested_layers: int) -> int:
        if requested_layers >= 0:
            return requested_layers
        # Auto mode: default 0 (safe CPU mode), can offload to GPU if supported
        return 0

    def load_model(
        self,
        model_path: str,
        context_size: int = 4096,
        threads: int = 0,
        gpu_layers: int = -1,
        verbose: bool = False,
    ) -> bool:
        """Loads a GGUF model into memory safely, unloading any prior model first."""
        with self._lock:
            if self._model is not None:
                self._unload_internal()

            p = Path(model_path)
            if not p.is_file():
                err = f"Model file not found: {model_path}"
                logger.error(err)
                self._info["status"] = "error"
                self._info["last_error"] = err
                raise FileNotFoundError(err)

            n_threads = self._determine_threads(threads)
            n_gpu = self._determine_gpu_layers(gpu_layers)

            logger.info(f"Loading LLM model from '{model_path}' (ctx={context_size}, threads={n_threads}, gpu_layers={n_gpu})...")
            try:
                from llama_cpp import Llama

                self._model = Llama(
                    model_path=str(p.resolve()),
                    n_ctx=context_size,
                    n_threads=n_threads,
                    n_gpu_layers=n_gpu,
                    verbose=verbose,
                )
                self._model_path = str(p.resolve())
                self._info = {
                    "status": "loaded",
                    "model_path": self._model_path,
                    "model_name": p.name,
                    "model_size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                    "context_size": context_size,
                    "threads": n_threads,
                    "gpu_layers": n_gpu,
                    "backend": "llama-cpp-python",
                }
                logger.info(f"Model successfully loaded: {p.name}")
                return True
            except Exception as e:
                err = f"Failed to load model '{model_path}': {str(e)}"
                logger.exception(err)
                self._info["status"] = "error"
                self._info["last_error"] = str(e)
                self._model = None
                self._model_path = None
                raise RuntimeError(err) from e

    def _unload_internal(self):
        if self._model is not None:
            logger.info(f"Unloading LLM model: {self._model_path}")
            try:
                if hasattr(self._model, "close"):
                    self._model.close()
            except Exception:
                pass
            del self._model
            self._model = None
            self._model_path = None
            gc.collect()
        self._info = {
            "status": "unloaded",
            "model_path": None,
            "context_size": 0,
            "threads": 0,
            "gpu_layers": 0,
            "backend": "llama-cpp-python",
        }

    def unload_model(self) -> bool:
        """Safely unloads the loaded model and releases system memory."""
        with self._lock:
            self._unload_internal()
            return True

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_model_info(self) -> Dict[str, Any]:
        return dict(self._info)

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Synchronous chat completion."""
        if not self.is_loaded():
            raise RuntimeError("LLM is not loaded. Please select and load a model.")

        with self._lock:
            try:
                response = self._model.create_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop or [],
                )
                text = response["choices"][0]["message"].get("content", "")
                return text.strip()
            except Exception as e:
                logger.error(f"Error during LLM generate: {e}")
                raise

    def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop: Optional[List[str]] = None,
    ) -> Generator[str, None, None]:
        """Streaming chat completion generator yielding tokens."""
        if not self.is_loaded():
            raise RuntimeError("LLM is not loaded. Please select and load a model.")

        with self._lock:
            try:
                stream = self._model.create_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop or [],
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        yield token
            except Exception as e:
                logger.error(f"Error during LLM stream_generate: {e}")
                raise


_engine_instance: Optional[LLMEngine] = None


def get_llm_engine() -> LLMEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LLMEngine()
    return _engine_instance
