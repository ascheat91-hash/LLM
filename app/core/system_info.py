import platform
import os
import psutil
from typing import Dict, Any, List

def get_cpu_info() -> Dict[str, Any]:
    logical_cores = psutil.cpu_count(logical=True) or 1
    physical_cores = psutil.cpu_count(logical=False) or logical_cores
    cpu_percent = psutil.cpu_percent(interval=0.1)
    return {
        "processor": platform.processor() or platform.machine(),
        "physical_cores": physical_cores,
        "logical_cores": logical_cores,
        "usage_percent": cpu_percent,
    }


def get_memory_info() -> Dict[str, Any]:
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "usage_percent": mem.percent,
    }


def get_gpu_info() -> List[Dict[str, Any]]:
    gpus: List[Dict[str, Any]] = []

    # 1. Try PyTorch / DirectML / Windows WMI
    try:
        import subprocess
        # Query WMI for Win32_VideoController
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8", errors="ignore").strip()
        if output:
            import json
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get("Name")
                if name:
                    vram_bytes = item.get("AdapterRAM") or 0
                    vram_mb = round(vram_bytes / (1024 * 1024), 1) if isinstance(vram_bytes, int) and vram_bytes > 0 else "N/A"
                    gpus.append({
                        "name": str(name),
                        "vram": vram_mb,
                        "type": "Discrete / Integrated"
                    })
    except Exception:
        pass

    if not gpus:
        gpus.append({"name": "No dedicated GPU detected (CPU mode active)", "vram": "0 MB", "type": "CPU"})

    return gpus


def get_audio_devices() -> Dict[str, List[Dict[str, Any]]]:
    inputs = []
    outputs = []
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_in, default_out = sd.default.device

        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                inputs.append({
                    "id": idx,
                    "name": dev.get("name"),
                    "hostapi": dev.get("hostapi"),
                    "default": (idx == default_in),
                    "channels": dev.get("max_input_channels")
                })
            if dev.get("max_output_channels", 0) > 0:
                outputs.append({
                    "id": idx,
                    "name": dev.get("name"),
                    "hostapi": dev.get("hostapi"),
                    "default": (idx == default_out),
                    "channels": dev.get("max_output_channels")
                })
    except Exception as e:
        inputs.append({"id": 0, "name": f"Default Input ({e})", "default": True})
        outputs.append({"id": 0, "name": f"Default Output ({e})", "default": True})

    return {"inputs": inputs, "outputs": outputs}


def get_full_system_status() -> Dict[str, Any]:
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": platform.python_version(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "gpus": get_gpu_info(),
        "audio": get_audio_devices(),
    }
