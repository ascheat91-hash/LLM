import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_api_status(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "assistant" in data
    assert "system" in data

def test_api_models(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json()
    assert "local_models" in data
    assert "catalog" in data

def test_api_tools(client):
    res = client.get("/api/tools")
    assert res.status_code == 200
    data = res.json()
    assert "tools" in data
    assert len(data["tools"]) >= 10

def test_api_settings(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["assistant"]["name"] is not None

def test_api_chat(client):
    res = client.post("/api/chat", json={"message": "What is the current time?", "speak": False})
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
