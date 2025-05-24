import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from Heti.mcp.tools import activity_embedder_handler, eddi_g_handler, task_tracker_handler

tool_dispatcher = {
    "activity_embedder": activity_embedder_handler,
    "eddi_g": eddi_g_handler,
    "task_tracker": task_tracker_handler,
}

app = FastAPI()

@app.get("/mcp/{client_name}/sse/{user_id}")
async def sse_endpoint(client_name: str, user_id: str):
    async def event_generator():
        while True:
            # Heartbeat ping or real events would go here
            yield "data: heartbeat\\n\\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/mcp/{client_name}/invoke/{tool}/{user_id}")
async def invoke_tool(client_name: str, tool: str, user_id: str, payload: dict):
    if tool not in tool_dispatcher:
        raise HTTPException(status_code=404, detail=f"Tool {tool} not found")
    # Combine context and payload, then dispatch to the appropriate tool handler
    invocation_payload = {"client": client_name, "user": user_id}
    invocation_payload.update(payload)
    result = await tool_dispatcher[tool](invocation_payload)
    return result
