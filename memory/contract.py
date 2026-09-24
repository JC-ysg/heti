"""Note contract (#07): 5 fields, exactly one type out of 4. status is counted, never judged."""
from __future__ import annotations

from datetime import date, datetime

FIELDS = ("type", "created", "about", "source", "status")
TYPES = {"decision", "learning", "fact", "open"}


def parse_time(value: str) -> datetime | date | None:
    """Parse ISO date or datetime; trailing Z → +00:00. Returns None if unparseable."""
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        pass
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def validate_note(fm: dict | None) -> tuple[list[str], list[str]]:
    """Return (problems, warnings). Problems keep a note out of the index; warnings don't."""
    if fm is None:
        return ["no frontmatter"], []
    problems: list[str] = []
    warnings: list[str] = []
    for f in FIELDS:
        if f not in fm:
            problems.append(f"missing field: {f}")
    t = fm.get("type")
    if "type" in fm:
        if not isinstance(t, str) or "," in t or t.strip() not in TYPES:
            problems.append(f"illegal or multiple type: {t!r}")
    if "created" in fm and parse_time(fm.get("created")) is None:
        problems.append(f"unparseable created: {fm.get('created')!r}")
    for k in fm:
        if k not in FIELDS:
            warnings.append(f"extra field: {k}")
    return problems, warnings
