from __future__ import annotations

import os
import logging
from typing import Any, Dict, List
 
from dotenv import load_dotenv
load_dotenv()
from httpx import AsyncClient
import asyncio
from openai import OpenAI
# Initialize OpenAI client with API key from environment
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configure logger
logger = logging.getLogger("activity_embedder")

# HTTP client settings
TIMEOUT = 2.0
RETRIES = 3


async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts a batch of log entries, builds a memory payload,
    posts to OpenMemory, and returns the stored memory ID.
    """
    log_batch: List[Dict[str, Any]] = payload.get("log_batch", [])
    meta: Dict[str, Any] = payload.get("meta", {})
    user_id: str = meta.get("user_id", "default_user")

    # Build embedding text from log entries
    entries_text = "\n".join(
        f"{entry.get('timestamp', '')}: {entry.get('message', '')}" 
        for entry in log_batch
    )
    text = entries_text or f"Monitor batch {len(log_batch)} entries"

    # Generate embedding vector via OpenAI if API key is set
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            # Use specified embedding model or default to ada-002
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
            response = await openai_client.embeddings.create(input=text, model=model)
            vector: List[float] = response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            # Fallback stub vector on embedding failure
            vector = [0.0] * 768
    else:
        # Fallback stub vector
        vector: List[float] = [0.0] * 768
    memory_payload: Dict[str, Any] = {
        "user_id": user_id,
        "text": text,
        "metadata": meta,
        "vector": vector,
        "infer": False,
        "app": "monitor_embedder",
    }

    base_url = "http://localhost:8765"
    post_url = f"{base_url}/api/v1/memories/"
    data: Dict[str, Any] = {}
    last_exc: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            async with AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(post_url, json=memory_payload)
                resp.raise_for_status()
                data = resp.json()
            break
        except Exception as e:
            last_exc = e
            logger.warning(f"Attempt {attempt}/{RETRIES} failed: {e}")
            if attempt < RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))
    if last_exc is not None:
        logger.error(f"All {RETRIES} attempts failed: {last_exc}")
        return {"status": "error", "error": str(last_exc)}

    memory_id = data.get("id") or data.get("memory_id") or ""
    logger.info(f"Stored memory {memory_id}")
    return {"status": "ok", "memory_id": memory_id}
