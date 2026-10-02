"""Normalization gate (#37): the only L1 gate. Checks format, duplicates and time.

Adapters produce items {source, source_id, occurred_at, text, source_sha256}.
Rejections are never silent: each carries a readable reason.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import raw_store
from .contract import parse_time

ITEM_KEYS = ("source", "source_id", "occurred_at", "text", "source_sha256")
SOURCE_RE = re.compile(r"^[a-z0-9_-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{8,}$")
EARLIEST = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE_SLACK = timedelta(days=1)


@dataclass
class GateResult:
    written: list = field(default_factory=list)      # Paths
    duplicates: list = field(default_factory=list)   # items
    rejected: list = field(default_factory=list)     # (item, reason)


def dedup_key(d: dict) -> tuple:
    return (d.get("source"), d.get("source_id"), d.get("source_sha256"))


def check(item: dict, now: datetime) -> list[str]:
    """Return a list of reasons; empty means the item is admissible."""
    missing = [k for k in ITEM_KEYS if not isinstance(item.get(k), str)]
    if missing:
        return [f"missing or non-string keys: {', '.join(missing)}"]
    reasons = []
    if not item["text"].strip():
        reasons.append("empty text")
    if not SOURCE_RE.match(item["source"]):
        reasons.append(f"illegal source {item['source']!r} (must match {SOURCE_RE.pattern})")
    if not SHA_RE.match(item["source_sha256"]):
        reasons.append("illegal source_sha256 (need lowercase hex)")
    t = parse_time(item["occurred_at"])
    if t is None:
        reasons.append(f"unparseable occurred_at {item['occurred_at']!r}")
    elif not isinstance(t, datetime) or t.tzinfo is None:
        reasons.append(f"occurred_at has no timezone {item['occurred_at']!r}")
    elif not (EARLIEST <= t <= now + FUTURE_SLACK):
        reasons.append(f"occurred_at out of bounds {item['occurred_at']!r}")
    return reasons


def admit(items, raw_dir, now: datetime) -> GateResult:
    raw_dir = Path(raw_dir)
    seen = {dedup_key(fm) for _, fm, _ in raw_store.iter_raw(raw_dir) if fm}
    res = GateResult()
    for item in items:
        reasons = check(item, now)
        if reasons:
            res.rejected.append((item, "; ".join(reasons)))
            continue
        key = dedup_key(item)
        if key in seen:
            res.duplicates.append(item)
            continue
        try:
            res.written.append(raw_store.write_raw(raw_dir, item, now=now))
        except FileExistsError as e:
            res.rejected.append((item, f"raw filename collision, nothing overwritten: {Path(e.filename).name}"))
            continue
        seen.add(key)
    return res
