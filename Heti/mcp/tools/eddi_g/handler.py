"""
eddi_g tool: integrate Ollama LLM via subprocess for reasoning and orchestration.
"""
import json
import subprocess
from typing import Any, Dict

async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept a payload containing memory context and task parameters,
    invoke Ollama LLM via CLI, and return its response.
    """
    # Serialize payload to JSON for LLM input
    prompt_json = json.dumps(payload)
    try:
        result = subprocess.run(
            ["ollama", "run", "llama2", "--json-input", prompt_json],
            capture_output=True,
            text=True,
            check=True
        )
        # Attempt to parse JSON output
        try:
            llm_output = json.loads(result.stdout)
        except json.JSONDecodeError:
            llm_output = result.stdout.strip()
        return {
            "status": "ok",
            "tool": "eddi_g",
            "output": llm_output
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "tool": "eddi_g",
            "error": e.stderr or str(e)
        }
