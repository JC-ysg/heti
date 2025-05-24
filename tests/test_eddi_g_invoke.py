import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from httpx import AsyncClient, ASGITransport
from Heti.mcp_server import app

# Stub eddi_g to avoid real Ollama calls during unit test
import Heti.mcp_server as server
async def stub_eddig(payload):
    return {"status": "ok", "tool": "eddi_g", "output": payload}
server.tool_dispatcher["eddi_g"] = stub_eddig

def test_eddi_g_invoke():
    async def run_test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {"prompt": "What is 2 + 2?"}
            response = await client.post(
                "/mcp/testclient/invoke/eddi_g/default_user",
                json=payload,
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert data.get("status") == "ok"
            # The output may be JSON or text; ensure it's present
            assert "output" in data

    asyncio.run(run_test())
