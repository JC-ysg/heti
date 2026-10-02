from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from memory import raw_store
from memory.adapters.claude_export import SOURCE, extract_source_json, items_from_conversations, read_export
from memory.gate import admit

FIXTURE = Path(__file__).parent / "fixtures" / "claude_export_min.json"
NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def original():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_items_shape_and_stats():
    items, stats = read_export(FIXTURE)
    assert [i["source_id"] for i in items] == [c["uuid"] for c in original()]
    assert all(i["source"] == SOURCE == "claude" for i in items)
    assert items[0]["occurred_at"] == "2026-01-02T03:04:05.123Z"
    assert stats == {"conversations": 3, "messages": 3, "empty_conversations": 1,
                     "non_text_items": 1, "attachments": 1, "files": 0}


def test_transcript_rendering():
    items, _ = read_export(FIXTURE)
    a, b, c = (i["text"] for i in items)
    assert a.startswith("# Test conversation A\n")
    assert "## human · 2026-01-02T03:04:05.123Z\nHello test\n" in a
    assert "Hello back, test." in a
    assert "Only text field, test ü" in b
    assert "(no messages)" in c


def test_empty_conversation_still_admitted(tmp_path):
    items, _ = read_export(FIXTURE)
    res = admit(items, tmp_path, now=NOW)
    assert len(res.written) == 3 and res.rejected == []


def test_zip_and_directory_inputs(tmp_path):
    d = tmp_path / "exp"
    d.mkdir()
    shutil.copy(FIXTURE, d / "conversations.json")
    z = tmp_path / "exp.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(FIXTURE, "data-2026/conversations.json")
    base = read_export(FIXTURE)
    assert read_export(d) == base
    assert read_export(z) == base


def test_dod4b_import_twice_adds_zero(tmp_path):
    items, _ = read_export(FIXTURE)
    admit(items, tmp_path, now=NOW)
    res = admit(read_export(FIXTURE)[0], tmp_path, now=NOW)
    assert res.written == [] and len(res.duplicates) == 3
    assert len(list(tmp_path.iterdir())) == 3


def test_dod4c_grown_conversation_adds_one_file_old_unchanged(tmp_path):
    raw = tmp_path / "raw"
    admit(read_export(FIXTURE)[0], raw, now=NOW)
    before = {p.name: p.read_bytes() for p in raw.iterdir()}
    data = original()
    data[1]["chat_messages"].append({"uuid": "x", "sender": "assistant", "created_at": "2026-01-03T00:02:00Z",
                                     "text": "Grown test reply", "content": []})
    grown = tmp_path / "grown.json"
    grown.write_text(json.dumps(data), encoding="utf-8")
    res = admit(read_export(grown)[0], raw, now=NOW)
    assert len(res.written) == 1 and len(res.duplicates) == 2
    after = {p.name: p.read_bytes() for p in raw.iterdir()}
    assert len(after) == len(before) + 1
    for name, b in before.items():
        assert after[name] == b


def test_dod4d_original_json_recoverable_from_raw(tmp_path):
    admit(read_export(FIXTURE)[0], tmp_path, now=NOW)
    by_id = {c["uuid"]: c for c in original()}
    recovered = 0
    for _, fm, body in raw_store.iter_raw(tmp_path):
        assert extract_source_json(body) == by_id[fm["source_id"]]
        recovered += 1
    assert recovered == 3


def test_sha_independent_of_rendering():
    items, _ = read_export(FIXTURE)
    reordered = [{k: c[k] for k in reversed(list(c))} for c in original()]
    items2, _ = items_from_conversations(reordered)
    assert [i["source_sha256"] for i in items] == [i["source_sha256"] for i in items2]
    assert len({i["source_sha256"] for i in items}) == 3


def test_malformed_conversation_rejected_with_reason_not_dropped(tmp_path):
    items, stats = items_from_conversations([{"name": "Test no uuid", "chat_messages": []}])
    assert stats["conversations"] == 1 and len(items) == 1
    res = admit(items, tmp_path, now=NOW)
    assert len(res.rejected) == 1 and "source_id" in res.rejected[0][1]
