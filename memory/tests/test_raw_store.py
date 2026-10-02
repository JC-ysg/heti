from __future__ import annotations

import stat
from datetime import datetime, timezone

import pytest

from memory import frontmatter, raw_store

NOW = datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
ITEM = {
    "source": "test",
    "source_id": "conv-1",
    "source_sha256": "abcdef0123456789" * 4,
    "occurred_at": "2026-01-02T03:04:05+08:00",
    "text": "Hello test\n",
}


def test_write_then_read_back(tmp_path):
    p = raw_store.write_raw(tmp_path, ITEM, now=NOW)
    assert p.name == "20260101T190405Z-test-abcdef01.md"
    items = list(raw_store.iter_raw(tmp_path))
    assert len(items) == 1
    path, fm, body = items[0]
    assert path == p
    assert body == "Hello test\n"
    assert tuple(fm) == raw_store.RAW_FIELDS
    assert fm["source_id"] == "conv-1"
    assert fm["ingested_at"] == "2026-01-03T12:00:00+00:00"
    assert "type" not in fm


def test_second_write_same_path_fails_and_bytes_unchanged(tmp_path):
    p = raw_store.write_raw(tmp_path, ITEM, now=NOW)
    before = p.read_bytes()
    other = dict(ITEM, text="Different test\n")
    with pytest.raises(FileExistsError):
        raw_store.write_raw(tmp_path, other, now=NOW)
    assert p.read_bytes() == before


def test_file_mode_is_readonly(tmp_path):
    p = raw_store.write_raw(tmp_path, ITEM, now=NOW)
    assert stat.S_IMODE(p.stat().st_mode) == 0o444


def test_no_mutating_public_names():
    names = [n.lower() for n in dir(raw_store) if not n.startswith("_")]
    for bad in ("update", "delete", "remove", "overwrite"):
        assert not any(bad in n for n in names), bad


def test_bad_source_rejected_for_filename(tmp_path):
    with pytest.raises(ValueError):
        raw_store.write_raw(tmp_path, dict(ITEM, source="../x"), now=NOW)


def test_iter_raw_missing_dir_is_empty(tmp_path):
    assert list(raw_store.iter_raw(tmp_path / "nope")) == []


def test_written_file_is_plain_markdown(tmp_path):
    p = raw_store.write_raw(tmp_path, ITEM, now=NOW)
    fm, body = frontmatter.split(p.read_text(encoding="utf-8"))
    assert fm["occurred_at"] == "2026-01-02T03:04:05+08:00"
