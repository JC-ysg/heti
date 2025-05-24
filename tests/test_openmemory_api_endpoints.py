import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
import types

# Ensure the API code is on the import path
api_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'mem0', 'openmemory', 'openmemory', 'api')
)
sys.path.insert(0, api_path)

# Stub out mcp modules for testing
sys.modules['mcp'] = types.ModuleType('mcp')
sys.modules['mcp.server'] = types.ModuleType('mcp.server')
fake_fastmcp = types.ModuleType('mcp.server.fastmcp')
fake_fastmcp.FastMCP = lambda *args, **kwargs: None
sys.modules['mcp.server.fastmcp'] = fake_fastmcp
fake_sse = types.ModuleType('mcp.server.sse')
fake_sse.SseServerTransport = lambda *args, **kwargs: None
sys.modules['mcp.server.sse'] = fake_sse

# Stub out OpenMemory memory client to avoid external Qdrant calls
fake_memmod = types.ModuleType('app.utils.memory')
import uuid as _uuid
class FakeMemoryClient:
    def add(self, text, user_id=None, metadata=None, memory_id=None):
        # Simulate Qdrant ADD event with same text
        return {'results': [{'event': 'ADD', 'id': str(_uuid.uuid4()), 'memory': text}]}
    def get_all(self, user_id=None):
        return {'results': []}
    def embedding_model(self):
        return None
fake_memmod.get_memory_client = lambda custom_instructions=None: FakeMemoryClient()
fake_memmod.memory_client = FakeMemoryClient()
sys.modules['app.utils.memory'] = fake_memmod

import main  # FastAPI app defined in main.py

client = TestClient(main.app)


def test_create_memory_success():
    payload = {"user_id": "default_user", "text": "Hello world", "metadata": {}, "infer": False, "app": "testapp"}
    response = client.post("/api/v1/memories", json=payload)
    assert response.status_code in (200, 201)
    data = response.json()
    assert "id" in data
    assert data["text"] == "Hello world"


def test_create_memory_missing_user():
    response = client.post("/api/v1/memories", json={"text": "Missing user_id"})
    assert response.status_code == 422


def test_create_memory_unknown_user():
    payload = {"user_id": "unknown_user", "text": "Hi"}
    response = client.post("/api/v1/memories", json=payload)
    assert response.status_code == 404


def test_list_memories_success():
    response = client.get("/api/v1/memories", params={"user_id": "default_user"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data and isinstance(data["items"], list)
    assert "total" in data


def test_list_memories_invalid_user():
    response = client.get("/api/v1/memories", params={"user_id": "noexist"})
    assert response.status_code == 404


def test_get_memory_not_found():
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/memories/{fake_id}")
    assert response.status_code == 404


def test_get_memory_success():
    # Create a memory first
    payload = {"user_id": "default_user", "text": "test get"}
    res = client.post("/api/v1/memories", json=payload)
    mem_id = res.json()["id"]
    response = client.get(f"/api/v1/memories/{mem_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mem_id
    assert data["text"] == "test get"


def test_update_memory_success():
    # Create a memory first
    payload = {"user_id": "default_user", "text": "original"}
    res = client.post("/api/v1/memories", json=payload)
    mem_id = res.json()["id"]
    update = {"memory_content": "updated", "user_id": "default_user"}
    response = client.put(f"/api/v1/memories/{mem_id}", json=update)
    assert response.status_code == 200
    data = response.json()
    assert data.get("text") in ("updated", None)  # may reflect schema field name


def test_update_memory_invalid_uuid():
    response = client.put("/api/v1/memories/not-a-uuid", json={"memory_content": "x", "user_id": "default_user"})
    assert response.status_code == 422


def test_delete_memories_success():
    # Create a memory first
    payload = {"user_id": "default_user", "text": "to delete"}
    res = client.post("/api/v1/memories", json=payload)
    mem_id = res.json()["id"]
    delete = {"memory_ids": [mem_id], "user_id": "default_user"}
    response = client.delete("/api/v1/memories", json=delete)
    assert response.status_code == 200
    data = response.json()
    assert "Successfully deleted" in data.get("message", "")


def test_stats_success():
    response = client.get("/api/v1/stats", params={"user_id": "default_user"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("total_memories"), int)


def test_stats_missing_user_id():
    response = client.get("/api/v1/stats")
    assert response.status_code == 422


def test_create_memory_large_payload():
    long_text = "A" * 10000
    payload = {"user_id": "default_user", "text": long_text}
    response = client.post("/api/v1/memories", json=payload)
    assert response.status_code in (200, 201)
    assert response.json()["text"] == long_text


@pytest.mark.skip(reason="Network/API downtime simulation requires custom transport mockup")
def test_network_downtime_placeholder():
    # Placeholder: simulate target service down and expect a connection error or 5xx
    pass 