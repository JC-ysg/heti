from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from httpx import AsyncClient, ASGITransport
from Heti.mcp_server import app

# Stub out activity_embedder handler to avoid external HTTP calls during unit test
import Heti.mcp_server as server
async def stub_activity_embedder(payload):
    return {"status": "ok", "memory_id": "test"}
server.tool_dispatcher["activity_embedder"] = stub_activity_embedder

def test_activity_embedder_invoke():
    # Prepare a minimal payload
    payload = {
        "log_batch": [{"timestamp": "2025-05-23T00:00:00Z", "message": "Test"}],
        "meta": {"category": "monitor_test", "source": "unit_test", "loop_id": "test-loop"}
    }

    async def run_test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/mcp/testclient/invoke/activity_embedder/default_user",
                json=payload,
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert data.get("status") == "ok"
            assert "memory_id" in data and isinstance(data["memory_id"], str)

    asyncio.run(run_test())
