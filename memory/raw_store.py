"""Append-only raw layer (#08/#14). Its only job: lose nothing.

One file per item, named by timestamp. Files are created with mode "x" (never overwritten)
and chmod 0444. There is deliberately no update/delete/overwrite path in this module.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import frontmatter
from .contract import parse_time

# Draft L1 raw frontmatter format. Everything about the raw format is centralized here.
RAW_FIELDS = ("source", "source_id", "source_sha256", "occurred_at", "ingested_at")
FILENAME_TIME = "%Y%m%dT%H%M%SZ"


def check_filename(name: str) -> str:
    """Reject '/', '..' and names starting with '.'."""
    if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise ValueError(f"illegal filename: {name!r}")
    return name


def raw_filename(item: dict) -> str:
    occurred = parse_time(item["occurred_at"])
    if not isinstance(occurred, datetime) or occurred.tzinfo is None:
        raise ValueError(f"occurred_at must be a timezone-aware datetime: {item['occurred_at']!r}")
    stamp = occurred.astimezone(timezone.utc).strftime(FILENAME_TIME)
    return check_filename(f"{stamp}-{item['source']}-{item['source_sha256'][:8]}.md")


def write_raw(raw_dir, item: dict, now: datetime) -> Path:
    """Write one raw item. Raises FileExistsError rather than overwrite anything."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / raw_filename(item)
    fm = {k: str(item[k]) for k in RAW_FIELDS if k != "ingested_at"}
    fm["ingested_at"] = now.astimezone(timezone.utc).isoformat()
    fm = {k: fm[k] for k in RAW_FIELDS}
    with open(path, "x", encoding="utf-8", newline="\n") as f:
        f.write(frontmatter.render(fm, item["text"]))
    os.chmod(path, 0o444)
    return path


def iter_raw(raw_dir) -> Iterator[tuple[Path, dict | None, str]]:
    """Read-only iteration over raw files: yields (path, frontmatter, body), sorted by name."""
    raw_dir = Path(raw_dir)
    if not raw_dir.is_dir():
        return
    for path in sorted(raw_dir.glob("*.md")):
        fm, body = frontmatter.split(path.read_text(encoding="utf-8"))
        yield path, fm, body
