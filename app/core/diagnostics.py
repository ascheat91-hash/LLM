import sys
import platform
import os
import shutil

def run_diagnostics():
    print("================ SYSTEM & ENVIRONMENT ================")
    print("Operating System :", platform.system(), platform.release(), platform.version())
    print("Python Version   :", platform.python_version(), "(" + sys.executable + ")")

    try:
        import psutil
        cpu_cores = psutil.cpu_count(logical=True)
        phys_cores = psutil.cpu_count(logical=False)
        mem = psutil.virtual_memory()
        print("CPU Processor    :", platform.processor())
        print("CPU Cores        :", f"{phys_cores} physical, {cpu_cores} logical threads")
        print("System RAM Total :", f"{round(mem.total / (1024**3), 2)} GB")
        print("System RAM Avail :", f"{round(mem.available / (1024**3), 2)} GB free")
    except Exception as e:
        print("Hardware stats   :", e)

    print("\n================ GPU ACCELERATION ====================")
    try:
        import subprocess, json
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8", errors="ignore").strip()
        if out:
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for g in data:
                vram = round(g.get("AdapterRAM", 0) / (1024*1024), 1) if g.get("AdapterRAM") else "N/A"
                print("GPU Detected     :", g.get("Name"), f"(VRAM: {vram} MB)")
    except Exception as e:
        print("GPU Query Error  :", e)

    print("\n================ LOCAL LLM RUNTIME ===================")
    try:
        import llama_cpp
        print("llama.cpp runtime: INSTALLED (version " + llama_cpp.__version__ + ")")
    except Exception as e:
        print("llama.cpp runtime: MISSING/FAILED ->", e)

    models_dir = os.path.join(os.getcwd(), "models")
    models = list(os.listdir(models_dir)) if os.path.exists(models_dir) else []
    ggufs = [m for m in models if m.endswith(".gguf")]
    print("Models directory :", f"{len(ggufs)} .gguf file(s) found:")
    for g in ggufs:
        sz = round(os.path.getsize(os.path.join(models_dir, g)) / (1024*1024), 1)
        print(f"  - {g} ({sz} MB)")

    print("\n================ SPEECH & AUDIO ENGINES ==============")
    try:
        import faster_whisper
        print("Speech-to-Text   : faster-whisper is READY")
    except Exception as e:
        print("Speech-to-Text   : faster-whisper MISSING ->", e)

    try:
        import piper
        print("Text-to-Speech   : Piper Neural TTS is READY")
    except Exception as e:
        print("Text-to-Speech   : Piper MISSING ->", e)

    voices_dir = os.path.join(os.getcwd(), "voices")
    voices = list(os.listdir(voices_dir)) if os.path.exists(voices_dir) else []
    onnx_voices = [v for v in voices if v.endswith(".onnx")]
    print("Voices directory :", f"{len(onnx_voices)} ONNX voice(s) found:")
    for v in onnx_voices:
        sz = round(os.path.getsize(os.path.join(voices_dir, v)) / (1024*1024), 1)
        print(f"  - {v} ({sz} MB)")

    print("\n================ AUDIO HARDWARE ======================")
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        inputs = [d["name"] for d in devs if d.get("max_input_channels", 0) > 0]
        outputs = [d["name"] for d in devs if d.get("max_output_channels", 0) > 0]
        print(f"Input Microphones : {len(inputs)} device(s) detected")
        for d in inputs[:3]:
            print(f"  - [MIC] {d}")
        print(f"Output Speakers   : {len(outputs)} device(s) detected")
        for d in outputs[:3]:
            print(f"  - [SPK] {d}")
    except Exception as e:
        print("Audio Query Error:", e)

    print("\n================ SERVER STATUS =======================")
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=2)
        print("Localhost Server : RUNNING (HTTP 200 OK at http://127.0.0.1:8000)")
    except Exception:
        print("Localhost Server : NOT RUNNING (Start with start.bat)")
    print("======================================================")


if __name__ == "__main__":
    run_diagnostics()
