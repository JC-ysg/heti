from __future__ import annotations

from datetime import datetime, timezone

from memory import raw_store
from memory.gate import admit

NOW = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)


def item(**kw):
    base = {
        "source": "test",
        "source_id": "c1",
        "source_sha256": "11" * 32,
        "occurred_at": "2026-01-02T03:04:05Z",
        "text": "Hello test\n",
    }
    base.update(kw)
    return base


def only_reason(res):
    assert len(res.rejected) == 1
    return res.rejected[0][1]


def test_legal_item_written(tmp_path):
    res = admit([item()], tmp_path, now=NOW)
    assert len(res.written) == 1 and res.duplicates == [] and res.rejected == []
    fm = next(raw_store.iter_raw(tmp_path))[1]
    assert fm["ingested_at"] == NOW.isoformat()


def test_empty_text_rejected(tmp_path):
    res = admit([item(text="  \n ")], tmp_path, now=NOW)
    assert "empty text" in only_reason(res)
    assert list(tmp_path.iterdir()) == []


def test_illegal_source_rejected(tmp_path):
    for bad in ("Test", "a/b", "", "x y"):
        res = admit([item(source=bad)], tmp_path, now=NOW)
        assert "illegal source" in only_reason(res)


def test_naive_time_rejected(tmp_path):
    assert "timezone" in only_reason(admit([item(occurred_at="2026-01-02T03:04:05")], tmp_path, now=NOW))


def test_date_only_rejected(tmp_path):
    assert "timezone" in only_reason(admit([item(occurred_at="2026-01-02")], tmp_path, now=NOW))


def test_unparseable_time_rejected(tmp_path):
    assert "unparseable" in only_reason(admit([item(occurred_at="last week")], tmp_path, now=NOW))


def test_out_of_bounds_time_rejected(tmp_path):
    assert "out of bounds" in only_reason(admit([item(occurred_at="1999-12-31T23:59:59Z")], tmp_path, now=NOW))
    assert "out of bounds" in only_reason(admit([item(occurred_at="2026-01-11T00:00:01Z")], tmp_path, now=NOW))


def test_upper_bound_inclusive(tmp_path):
    res = admit([item(occurred_at="2026-01-11T00:00:00Z")], tmp_path, now=NOW)
    assert len(res.written) == 1


def test_missing_key_rejected_not_crash(tmp_path):
    bad = item()
    del bad["source_id"]
    assert "missing" in only_reason(admit([bad], tmp_path, now=NOW))


def test_duplicate_across_runs(tmp_path):
    admit([item()], tmp_path, now=NOW)
    res = admit([item()], tmp_path, now=NOW)
    assert res.written == [] and len(res.duplicates) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_same_id_new_hash_is_not_duplicate(tmp_path):
    admit([item()], tmp_path, now=NOW)
    res = admit([item(source_sha256="22" * 32)], tmp_path, now=NOW)
    assert len(res.written) == 1
    assert len(list(tmp_path.iterdir())) == 2


def test_mixed_batch(tmp_path):
    admit([item(source_id="dup")], tmp_path, now=NOW)
    batch = [
        item(source_id="ok1", source_sha256="aa" * 32),
        item(source_id="dup"),
        item(source_id="bad", text=""),
        item(source_id="ok2", source_sha256="bb" * 32, occurred_at="2026-01-03T00:00:00Z"),
        item(source_id="ok1", source_sha256="aa" * 32),  # duplicate within the same batch
    ]
    res = admit(batch, tmp_path, now=NOW)
    assert len(res.written) == 2
    assert len(res.duplicates) == 2
    assert [r[0]["source_id"] for r in res.rejected] == ["bad"]
    assert len(list(tmp_path.iterdir())) == 3


def test_rejection_reasons_are_readable(tmp_path):
    res = admit([item(source="Bad!", text="")], tmp_path, now=NOW)
    reason = only_reason(res)
    assert isinstance(reason, str) and "empty text" in reason and "illegal source" in reason


def test_filename_collision_is_rejected_not_overwritten(tmp_path):
    admit([item(source_id="c1")], tmp_path, now=NOW)
    p = next(tmp_path.iterdir())
    before = p.read_bytes()
    res = admit([item(source_id="c2", text="Other test\n")], tmp_path, now=NOW)
    assert "collision" in only_reason(res)
    assert p.read_bytes() == before
