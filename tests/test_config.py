import pytest
from pathlib import Path
from app.config.settings import load_settings, Settings, get_settings, update_settings

def test_settings_defaults():
    s = Settings()
    assert s.assistant.name == "FOXSI"
    assert s.server.port == 8000
    assert s.stt.engine == "faster-whisper"
    assert s.tts.engine in ["piper", "pyttsx3"]
    assert s.security.block_dangerous_tools is True

def test_settings_resolve_path():
    s = get_settings()
    p = s.resolve_path("models/test.gguf")
    assert isinstance(p, Path)
    assert p.name == "test.gguf"

def test_settings_update():
    orig_name = get_settings().assistant.name
    try:
        updated = update_settings({"assistant": {"name": "TEST_FOXSI"}})
        assert updated.assistant.name == "TEST_FOXSI"
    finally:
        update_settings({"assistant": {"name": orig_name}})
