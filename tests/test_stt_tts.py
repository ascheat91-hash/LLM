import pytest
import numpy as np
from app.speech.stt import get_speech_recognizer
from app.speech.tts import get_speech_synthesizer

def test_stt_interface():
    stt = get_speech_recognizer()
    mics = stt.list_microphones()
    assert isinstance(mics, list)
    
    # Test transcribe empty/dummy audio
    dummy_audio = np.zeros(16000, dtype=np.float32)
    res = stt.transcribe(dummy_audio)
    assert isinstance(res, dict)
    assert "text" in res

def test_tts_interface():
    tts = get_speech_synthesizer()
    voices = tts.list_voices()
    assert "piper" in voices
    assert "system_sapi" in voices

    # Test synthesize to wav
    wav_bytes = tts.synthesize_to_wav_bytes("Testing voice synthesis.")
    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > 1000
    assert wav_bytes.startswith(b"RIFF")
