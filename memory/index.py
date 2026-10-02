"""Rebuildable structural index (#10/#11/#12/#13). Derived data, never a cache.

The index can be deleted and rebuilt from the vault at any time. rebuild() only ever
deletes and rewrites three named files in the index dir; it never touches anything else.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from . import frontmatter
from .contract import parse_time, validate_note
from .raw_store import RAW_FIELDS

INDEX_DIRNAME = ".heti-index"
RAW_DIRNAME = "raw"
MARKER = ".heti-index"
INDEX_FILE = "index.json"
PROBLEMS_FILE = "problems.json"
OWNED_FILES = (INDEX_FILE, PROBLEMS_FILE, MARKER)


class IndexLocationError(ValueError):
    pass


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def check_index_dir(vault: Path, index_dir: Path) -> None:
    v, i, raw = vault.resolve(), index_dir.resolve(), (vault / RAW_DIRNAME).resolve()
    if _is_within(v, i):
        raise IndexLocationError(f"refusing: index dir {index_dir} is the vault or one of its ancestors")
    if _is_within(i, raw):
        raise IndexLocationError(f"refusing: index dir {index_dir} is inside the raw layer")
    if i.is_dir() and any(i.iterdir()) and not (i / MARKER).is_file():
        raise IndexLocationError(f"refusing: {index_dir} is not empty and has no {MARKER} marker")


def _str(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True)


def _read(path: Path):
    try:
        return frontmatter.parse(path.read_text(encoding="utf-8")), None
    except UnicodeDecodeError:
        return None, "not valid utf-8"


def note_paths(vault: Path):
    for p in sorted(vault.rglob("*.md")):
        rel = p.relative_to(vault)
        if any(part.startswith(".") for part in rel.parts) or rel.parts[0] == RAW_DIRNAME:
            continue
        if p.is_file():
            yield p, rel


def scan(vault: Path) -> tuple[list[dict], list[dict], list[dict]]:
    records, problems, warnings = [], [], []

    def add(rel: Path, kind: str, fm, probs, warns):
        path = rel.as_posix()
        if warns:
            warnings.append({"path": path, "kind": kind, "warnings": warns})
        if probs:
            problems.append({"path": path, "kind": kind, "problems": probs})
            return
        rec = {"path": path, "kind": kind}
        rec.update({k: _str(v) for k, v in fm.items() if k not in ("path", "kind")})
        records.append(rec)

    for p, rel in note_paths(vault):
        fm, err = _read(p)
        probs, warns = ([err], []) if err else validate_note(fm)
        add(rel, "note", fm, probs, warns)

    raw_dir = vault / RAW_DIRNAME
    for p in sorted(raw_dir.glob("*.md")) if raw_dir.is_dir() else []:
        fm, err = _read(p)
        if err or fm is None:
            probs, warns = [err or "no frontmatter"], []
        else:
            probs = [f"missing field: {k}" for k in RAW_FIELDS if k not in fm]
            warns = [f"extra field: {k}" for k in fm if k not in RAW_FIELDS]
        add(p.relative_to(vault), "raw", fm, probs, warns)

    key = lambda r: r["path"]  # noqa: E731
    return sorted(records, key=key), sorted(problems, key=key), sorted(warnings, key=key)


def _write_owned(index_dir: Path, name: str, text: str) -> None:
    # Whitelisted write path: unlink first (never write through a symlink), then create fresh.
    path = index_dir / name
    path.unlink(missing_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as f:
        f.write(text)


def rebuild(vault, index_dir=None) -> dict:
    vault = Path(vault)
    index_dir = Path(index_dir) if index_dir is not None else vault / INDEX_DIRNAME
    check_index_dir(vault, index_dir)
    records, problems, warnings = scan(vault)
    index_dir.mkdir(parents=True, exist_ok=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False, sort_keys=True, indent=1) + "\n"  # noqa: E731
    _write_owned(index_dir, MARKER, "Hēti derived index. Safe to delete; rebuild with `python -m memory index rebuild`.\n")
    _write_owned(index_dir, INDEX_FILE, dump({"records": records}))
    _write_owned(index_dir, PROBLEMS_FILE, dump({"problems": problems, "warnings": warnings}))
    return {"notes": sum(r["kind"] == "note" for r in records), "raw": sum(r["kind"] == "raw" for r in records),
            "problems": len(problems), "warnings": len(warnings)}


def record_date(rec: dict) -> date | None:
    """Calendar date for --since/--until: notes use `created` as written; raw uses UTC date of occurred_at."""
    t = parse_time(rec.get("occurred_at" if rec.get("kind") == "raw" else "created"))
    if isinstance(t, datetime):
        if rec.get("kind") == "raw":
            if t.tzinfo is None:
                return None
            t = t.astimezone(timezone.utc)
        return t.date()
    return t


def query(index_dir, type=None, status=None, since=None, until=None, kind=None) -> list[dict]:
    index_file = Path(index_dir) / INDEX_FILE
    if not index_file.is_file():
        raise FileNotFoundError(f"no index at {index_dir}; run `python -m memory index rebuild` first")
    records = json.loads(index_file.read_text(encoding="utf-8"))["records"]
    lo = date.fromisoformat(since) if since else None
    hi = date.fromisoformat(until) if until else None
    out = []
    for r in records:
        if kind and r.get("kind") != kind:
            continue
        if type and r.get("type") != type:
            continue
        if status and r.get("status") != status:
            continue
        if lo or hi:
            d = record_date(r)
            if d is None or (lo and d < lo) or (hi and d > hi):
                continue
        out.append(r)
    return out
