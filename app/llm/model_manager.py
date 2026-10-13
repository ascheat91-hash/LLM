import os
import time
import urllib.request
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core.logger import logger
from app.config.settings import get_settings
from app.llm.engine import get_llm_engine

# Curated catalog of legitimate public GGUF models from official/reputable creators
MODEL_CATALOG = [
    {
        "id": "qwen2.5-0.5b-instruct-q4_k_m",
        "name": "Qwen 2.5 0.5B Instruct (Q4_K_M)",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size_mb": 468,
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "description": "Ultra-fast, lightweight 0.5B model. Exceptional responsiveness on CPU.",
        "recommended": True,
    },
    {
        "id": "qwen2.5-1.5b-instruct-q4_k_m",
        "name": "Qwen 2.5 1.5B Instruct (Q4_K_M)",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size_mb": 986,
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "description": "Smart, highly capable 1.5B model. Great balance of reasoning and speed.",
        "recommended": False,
    },
    {
        "id": "phi-3.5-mini-instruct-q4_k_m",
        "name": "Phi-3.5 Mini 3.8B Instruct (Q4_K_M)",
        "filename": "phi-3.5-mini-instruct-q4_k_m.gguf",
        "size_mb": 2390,
        "url": "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "description": "Microsoft Phi-3.5 high-reasoning mini model for complex instructions.",
        "recommended": False,
    },
    {
        "id": "gemma-2-2b-it-q4_k_m",
        "name": "Gemma 2 2B Instruct (Q4_K_M)",
        "filename": "gemma-2-2b-it-q4_k_m.gguf",
        "size_mb": 1640,
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "description": "Google Gemma 2 2B instruct model with strong conversational output.",
        "recommended": False,
    },
]


class DownloadTask:
    def __init__(self, model_id: str, filename: str, url: str, expected_size_mb: float):
        self.model_id = model_id
        self.filename = filename
        self.url = url
        self.expected_size_mb = expected_size_mb
        self.status = "starting"  # starting, downloading, completed, failed, cancelled
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed_mbps = 0.0
        self.progress_pct = 0.0
        self.error_message: Optional[str] = None
        self._cancel_flag = False

    def cancel(self):
        self._cancel_flag = True
        self.status = "cancelled"

    def is_cancelled(self) -> bool:
        return self._cancel_flag


class ModelManager:
    """Manages GGUF model files in models/, scans, loads, and downloads."""

    def __init__(self):
        self._engine = get_llm_engine()
        self._active_download: Optional[DownloadTask] = None
        self._download_lock = threading.Lock()

    def get_models_dir(self) -> Path:
        settings = get_settings()
        d = settings.resolve_path("models")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def scan_models(self) -> List[Dict[str, Any]]:
        """Scans the models directory for .gguf files."""
        models_dir = self.get_models_dir()
        found: List[Dict[str, Any]] = []

        if not models_dir.exists():
            return found

        for f in models_dir.glob("*.gguf"):
            try:
                stat = f.stat()
                size_mb = round(stat.st_size / (1024 * 1024), 2)
                is_currently_loaded = (
                    self._engine.is_loaded()
                    and self._engine.get_model_info().get("model_path") == str(f.resolve())
                )
                found.append({
                    "name": f.name,
                    "path": str(f.resolve()),
                    "relative_path": f"models/{f.name}",
                    "size_mb": size_mb,
                    "modified": stat.st_mtime,
                    "is_loaded": is_currently_loaded,
                })
            except Exception as e:
                logger.warning(f"Error inspecting model file {f}: {e}")

        return sorted(found, key=lambda x: x["name"])

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Returns the public curated catalog with local downloaded status."""
        local_models = {m["name"].lower(): m for m in self.scan_models()}
        catalog = []
        for item in MODEL_CATALOG:
            entry = dict(item)
            fname = item["filename"].lower()
            if fname in local_models:
                entry["is_downloaded"] = True
                entry["local_path"] = local_models[fname]["path"]
                entry["is_loaded"] = local_models[fname]["is_loaded"]
            else:
                entry["is_downloaded"] = False
                entry["local_path"] = None
                entry["is_loaded"] = False
            catalog.append(entry)
        return catalog

    def load_model_by_path(
        self,
        model_path: str,
        context_size: Optional[int] = None,
        threads: Optional[int] = None,
        gpu_layers: Optional[int] = None,
    ) -> bool:
        """Loads a model file by path safely."""
        settings = get_settings()
        resolved = settings.resolve_path(model_path)
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Model file does not exist: {resolved}")

        ctx = context_size if context_size is not None else settings.llm.context_size
        th = threads if threads is not None else settings.llm.threads
        gpu = gpu_layers if gpu_layers is not None else settings.llm.gpu_layers

        return self._engine.load_model(
            model_path=str(resolved),
            context_size=ctx,
            threads=th,
            gpu_layers=gpu,
        )

    def unload_model(self) -> bool:
        return self._engine.unload_model()

    def get_active_download_status(self) -> Optional[Dict[str, Any]]:
        if self._active_download is None:
            return None
        t = self._active_download
        return {
            "model_id": t.model_id,
            "filename": t.filename,
            "status": t.status,
            "progress_pct": round(t.progress_pct, 1),
            "downloaded_bytes": t.downloaded_bytes,
            "total_bytes": t.total_bytes,
            "speed_mbps": round(t.speed_mbps, 2),
            "error_message": t.error_message,
        }

    def cancel_download(self) -> bool:
        if self._active_download and self._active_download.status in ["starting", "downloading"]:
            self._active_download.cancel()
            return True
        return False

    def start_catalog_download(self, model_id: str) -> bool:
        """Starts a background download of an approved public catalog model."""
        target = next((m for m in MODEL_CATALOG if m["id"] == model_id), None)
        if not target:
            raise ValueError(f"Unknown model id: {model_id}")

        with self._download_lock:
            if self._active_download and self._active_download.status == "downloading":
                raise RuntimeError("Another model download is currently in progress.")

            task = DownloadTask(
                model_id=target["id"],
                filename=target["filename"],
                url=target["url"],
                expected_size_mb=target["size_mb"],
            )
            self._active_download = task

        thread = threading.Thread(target=self._run_download, args=(task,), daemon=True)
        thread.start()
        return True

    def _run_download(self, task: DownloadTask):
        models_dir = self.get_models_dir()
        dest_file = models_dir / task.filename
        temp_file = models_dir / f"{task.filename}.download"

        try:
            logger.info(f"Starting download of {task.filename} from {task.url}")
            task.status = "downloading"

            req = urllib.request.Request(
                task.url,
                headers={"User-Agent": "FOXSI-Voice-Assistant/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_len = response.headers.get("Content-Length")
                task.total_bytes = int(total_len) if total_len else int(task.expected_size_mb * 1024 * 1024)

                with open(temp_file, "wb") as f_out:
                    chunk_size = 1024 * 512  # 512 KB
                    start_time = time.time()
                    last_calc_time = start_time
                    bytes_since_last = 0

                    while True:
                        if task.is_cancelled():
                            logger.info(f"Download cancelled for {task.filename}")
                            if temp_file.exists():
                                temp_file.unlink(missing_ok=True)
                            return

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f_out.write(chunk)
                        task.downloaded_bytes += len(chunk)
                        bytes_since_last += len(chunk)

                        now = time.time()
                        dt = now - last_calc_time
                        if dt >= 0.5:
                            task.speed_mbps = (bytes_since_last / (1024 * 1024)) / dt
                            last_calc_time = now
                            bytes_since_last = 0
                            if task.total_bytes > 0:
                                task.progress_pct = (task.downloaded_bytes / task.total_bytes) * 100.0

            # Verify downloaded file
            if temp_file.exists() and temp_file.stat().st_size > 10 * 1024 * 1024:
                if dest_file.exists():
                    dest_file.unlink()
                temp_file.rename(dest_file)
                task.status = "completed"
                task.progress_pct = 100.0
                logger.info(f"Download completed for {task.filename} ({dest_file.stat().st_size} bytes)")
            else:
                raise RuntimeError("Downloaded file is empty or corrupted.")

        except Exception as e:
            if not task.is_cancelled():
                logger.exception(f"Error downloading {task.filename}: {e}")
                task.status = "failed"
                task.error_message = str(e)
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)


_manager_instance: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ModelManager()
    return _manager_instance
