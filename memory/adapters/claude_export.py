"""Claude conversation export adapter (#38/#39), lossless.

Assumed export structure (written from memory, NOT verified against a real export):
a list of conversations {uuid, name, created_at, updated_at,
chat_messages: [{uuid, sender, created_at, text, content: [{type, text?, ...}], attachments?, files?}]}.

Raw body = readable transcript + the conversation's full original JSON, verbatim, so nothing
(tool_use, thinking, attachments, files, unknown keys) is ever dropped.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

SOURCE = "claude"
EXPORT_NAME = "conversations.json"
JSON_HEADING = "## Source JSON (verbatim)"
JSON_OPEN = f"\n{JSON_HEADING}\n```json\n"
JSON_CLOSE = "\n```\n"


def load(path) -> list:
    """Load conversations.json from a file, a directory containing it, or a zip containing it."""
    path = Path(path)
    if path.is_dir():
        found = sorted(path.rglob(EXPORT_NAME))
        if not found:
            raise FileNotFoundError(f"{EXPORT_NAME} not found under {path}")
        return json.loads(found[0].read_text(encoding="utf-8"))
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            names = sorted(n for n in zf.namelist() if n.rsplit("/", 1)[-1] == EXPORT_NAME)
            if not names:
                raise FileNotFoundError(f"{EXPORT_NAME} not found in {path}")
            with zf.open(names[0]) as f:
                return json.load(io.TextIOWrapper(f, encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def source_sha256(conv) -> str:
    """Hash of the original object, independent of rendering and key order."""
    canon = json.dumps(conv, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def message_text(msg: dict) -> str:
    content = msg.get("content") or []
    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    parts = [p for p in parts if isinstance(p, str) and p]
    if parts:
        return "\n\n".join(parts)
    text = msg.get("text")
    return text if isinstance(text, str) and text else "(no text)"


def render(conv: dict) -> str:
    out = [f"# {conv.get('name') or '(untitled)'}", ""]
    messages = conv.get("chat_messages") or []
    if not messages:
        out += ["(no messages)", ""]
    for msg in messages:
        out += [f"## {msg.get('sender', '?')} · {msg.get('created_at', '?')}", message_text(msg), ""]
    transcript = "\n".join(out)
    return transcript + JSON_OPEN + json.dumps(conv, ensure_ascii=False, indent=1) + JSON_CLOSE


def extract_source_json(body: str):
    """Recover the original conversation object from a raw body."""
    start = body.rindex(JSON_OPEN) + len(JSON_OPEN)
    end = body.rindex(JSON_CLOSE)
    return json.loads(body[start:end])


def items_from_conversations(convs) -> tuple[list[dict], dict]:
    stats = {"conversations": 0, "messages": 0, "empty_conversations": 0,
             "non_text_items": 0, "attachments": 0, "files": 0}
    items = []
    for conv in convs:
        stats["conversations"] += 1
        if not isinstance(conv, dict):
            conv = {"_non_object": conv}
        messages = conv.get("chat_messages") or []
        if not messages:
            stats["empty_conversations"] += 1
        for msg in messages:
            stats["messages"] += 1
            if not isinstance(msg, dict):
                continue
            for c in msg.get("content") or []:
                if not (isinstance(c, dict) and c.get("type") == "text"):
                    stats["non_text_items"] += 1
            stats["attachments"] += len(msg.get("attachments") or [])
            stats["files"] += len(msg.get("files") or [])
        uuid = conv.get("uuid")
        created = conv.get("created_at")
        items.append({
            "source": SOURCE,
            "source_id": uuid if isinstance(uuid, str) else None,
            "occurred_at": created if isinstance(created, str) else None,
            "text": render(conv),
            "source_sha256": source_sha256(conv),
        })
    return items, stats


def read_export(path) -> tuple[list[dict], dict]:
    convs = load(path)
    if not isinstance(convs, list):
        raise ValueError("expected a JSON list of conversations")
    return items_from_conversations(convs)
