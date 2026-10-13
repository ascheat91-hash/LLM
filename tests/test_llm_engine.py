import pytest
from pathlib import Path
from app.llm.engine import get_llm_engine
from app.config.settings import get_settings

def test_engine_interface():
    engine = get_llm_engine()
    info = engine.get_model_info()
    assert "status" in info
    assert "backend" in info

def test_engine_load_and_generate():
    engine = get_llm_engine()
    settings = get_settings()
    model_path = settings.resolve_path(settings.llm.model_path)
    
    if model_path.exists():
        loaded = engine.load_model(str(model_path), context_size=512, threads=2)
        assert loaded is True
        assert engine.is_loaded() is True
        
        # Test generation
        res = engine.generate([{"role": "user", "content": "Respond with 'FOXSI_TEST_PASSED'."}], max_tokens=10)
        assert isinstance(res, str)
        assert len(res) > 0
        
        # Test streaming
        tokens = list(engine.stream_generate([{"role": "user", "content": "Hi"}], max_tokens=5))
        assert isinstance(tokens, list)
