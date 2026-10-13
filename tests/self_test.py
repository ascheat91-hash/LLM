import sys
import os
import time
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def run_self_test():
    print("==================================================")
    print("       FOXSI ASSISTANT - STARTUP SELF-TEST        ")
    print("==================================================")
    all_ok = True

    # 1. Configuration
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        print(f"  [PASS] Configuration ({settings.assistant.name}, port {settings.server.port})")
    except Exception as e:
        print(f"  [FAIL] Configuration: {e}")
        all_ok = False

    # 2. Python environment
    try:
        import psutil, yaml, fastapi, uvicorn
        print(f"  [PASS] Python environment (v{sys.version.split()[0]} on Windows)")
    except Exception as e:
        print(f"  [FAIL] Python environment: {e}")
        all_ok = False

    # 3. LLM runtime
    try:
        import llama_cpp
        print(f"  [PASS] LLM runtime (llama-cpp-python v{llama_cpp.__version__})")
    except Exception as e:
        print(f"  [FAIL] LLM runtime: {e}")
        all_ok = False

    # 4. GGUF Model
    try:
        from app.llm.model_manager import get_model_manager
        mgr = get_model_manager()
        models = mgr.scan_models()
        if models:
            print(f"  [PASS] Model ({len(models)} local GGUF models: {', '.join(m['name'] for m in models)})")
        else:
            print("  [WARN] Model (No GGUF models in models/ directory)")
    except Exception as e:
        print(f"  [FAIL] Model check: {e}")
        all_ok = False

    # 5. Speech-to-Text (STT)
    try:
        import faster_whisper
        from app.speech.stt import get_speech_recognizer
        stt = get_speech_recognizer()
        print("  [PASS] STT (faster-whisper engine initialized)")
    except Exception as e:
        print(f"  [FAIL] STT: {e}")
        all_ok = False

    # 6. Text-to-Speech (TTS)
    try:
        from app.speech.tts import get_speech_synthesizer
        tts = get_speech_synthesizer()
        voices = tts.list_voices()
        piper_count = len(voices.get("piper", []))
        sapi_count = len(voices.get("system_sapi", []))
        print(f"  [PASS] TTS (Piper: {piper_count} voices, SAPI5 fallback: {sapi_count} voices)")
    except Exception as e:
        print(f"  [FAIL] TTS: {e}")
        all_ok = False

    # 7. Microphone & Audio Devices
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        in_count = sum(1 for d in devs if d['max_input_channels'] > 0)
        out_count = sum(1 for d in devs if d['max_output_channels'] > 0)
        print(f"  [PASS] Microphone & Audio ({in_count} inputs, {out_count} outputs)")
    except Exception as e:
        print(f"  [FAIL] Microphone: {e}")
        all_ok = False

    # 8. Local Server Interface
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        res = client.get("/api/status")
        if res.status_code == 200:
            print("  [PASS] Local server (FastAPI routes & static assets operational)")
        else:
            print(f"  [FAIL] Local server returned status {res.status_code}")
            all_ok = False
    except Exception as e:
        print(f"  [FAIL] Local server: {e}")
        all_ok = False

    print("==================================================")
    if all_ok:
        print("  ALL CORE SYSTEM CHECKS PASSED SUCCESSFULLY! [OK]")
    else:
        print("  SOME CHECKS REPORTED WARNINGS OR FAILURES.")
    print("==================================================")
    return all_ok


if __name__ == "__main__":
    success = run_self_test()
    sys.exit(0 if success else 1)
