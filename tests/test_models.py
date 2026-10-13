import pytest
from pathlib import Path
from app.llm.model_manager import get_model_manager, MODEL_CATALOG

def test_model_discovery():
    mgr = get_model_manager()
    models = mgr.scan_models()
    assert isinstance(models, list)
    # Check if downloaded Qwen model is discovered
    names = [m["name"] for m in models]
    assert any("qwen" in name.lower() for name in names)

def test_model_catalog():
    mgr = get_model_manager()
    catalog = mgr.get_catalog()
    assert len(catalog) >= 3
    ids = [c["id"] for c in catalog]
    assert "qwen2.5-0.5b-instruct-q4_k_m" in ids

def test_validate_nonexistent_model():
    mgr = get_model_manager()
    with pytest.raises(FileNotFoundError):
        mgr.load_model_by_path("models/definitely_not_existing_xyz.gguf")
