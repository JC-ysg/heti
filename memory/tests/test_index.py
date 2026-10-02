from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from memory import index
from memory.adapters.claude_export import read_export
from memory.gate import admit

FIXTURE = Path(__file__).parent / "fixtures" / "claude_export_min.json"
NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def note(type_="open", created="2026-01-05", about="Test note A", status="draft", extra=""):
    return (f"---\ntype: {type_}\ncreated: {created}\nabout: {about}\nsource: test\nstatus: {status}\n{extra}---\n"
            "Hello test\n")


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    admit(read_export(FIXTURE)[0], v / "raw", now=NOW)
    (v / "a.md").write_text(note(), encoding="utf-8")
    (v / "sub").mkdir()
    (v / "sub" / "b.md").write_text(note("fact", "2026-01-07T10:00:00+08:00", "Test note B", "done"), encoding="utf-8")
    (v / "bad.md").write_text(note("idea"), encoding="utf-8")
    (v / "extra.md").write_text(note("learning", extra="tags: x\n"), encoding="utf-8")
    (v / "plain.md").write_text("No frontmatter test\n", encoding="utf-8")
    (v / ".obsidian").mkdir()
    (v / ".obsidian" / "hidden.md").write_text(note(), encoding="utf-8")
    (v / ".trash").mkdir()
    (v / ".trash" / "gone.md").write_text(note(), encoding="utf-8")
    return v


def raw_bytes(v):
    return {p.name: p.read_bytes() for p in (v / "raw").iterdir()}


def paths(records):
    return [r["path"] for r in records]


def test_rebuild_counts_and_default_location(vault):
    summary = index.rebuild(vault)
    idx = vault / ".heti-index"
    assert sorted(p.name for p in idx.iterdir()) == [".heti-index", "index.json", "problems.json"]
    assert summary == {"notes": 3, "raw": 3, "problems": 2, "warnings": 1}


def test_records_have_path_kind_and_fields(vault):
    index.rebuild(vault)
    recs = index.query(vault / ".heti-index")
    assert paths(recs) == sorted(paths(recs))
    by = {r["path"]: r for r in recs}
    assert by["sub/b.md"] == {"path": "sub/b.md", "kind": "note", "type": "fact",
                              "created": "2026-01-07T10:00:00+08:00", "about": "Test note B",
                              "source": "test", "status": "done"}
    raws = [r for r in recs if r["kind"] == "raw"]
    assert len(raws) == 3 and all(r["path"].startswith("raw/") for r in raws)
    assert all("type" not in r for r in raws)


def test_invalid_notes_go_to_problems_not_index(vault):
    index.rebuild(vault)
    recs = paths(index.query(vault / ".heti-index"))
    assert "bad.md" not in recs and "plain.md" not in recs
    assert "extra.md" in recs
    probs = json.loads((vault / ".heti-index" / "problems.json").read_text())
    assert sorted(p["path"] for p in probs["problems"]) == ["bad.md", "plain.md"]
    assert probs["warnings"] == [{"path": "extra.md", "kind": "note", "warnings": ["extra field: tags"]}]
    assert (vault / "bad.md").exists()  # #10: not deleted


def test_dot_dirs_not_indexed(vault):
    index.rebuild(vault)
    recs = paths(index.query(vault / ".heti-index"))
    assert not any(p.startswith(".") for p in recs)


def test_query_filters(vault):
    index.rebuild(vault)
    idx = vault / ".heti-index"
    assert paths(index.query(idx, type="open")) == ["a.md"]
    assert paths(index.query(idx, status="done")) == ["sub/b.md"]
    assert len(index.query(idx, kind="raw")) == 3
    assert paths(index.query(idx, kind="note", since="2026-01-06")) == ["sub/b.md"]
    assert paths(index.query(idx, kind="note", until="2026-01-05")) == ["a.md", "extra.md"]
    assert len(index.query(idx, kind="raw", since="2026-01-03")) == 2
    assert len(index.query(idx, kind="raw", since="2026-01-03", until="2026-01-03")) == 1
    assert index.query(idx, type="decision") == []


def test_dod5a_delete_and_rebuild_identical(vault):
    index.rebuild(vault)
    idx = vault / ".heti-index"
    first = (idx / "index.json").read_bytes(), (idx / "problems.json").read_bytes()
    idx.rename(vault.parent / "old-index")  # the index is gone from the vault
    assert not idx.exists()
    index.rebuild(vault)
    assert ((idx / "index.json").read_bytes(), (idx / "problems.json").read_bytes()) == first


def test_dod5b_derived_not_cache(vault):
    index.rebuild(vault)
    idx = vault / ".heti-index"
    data = json.loads((FIXTURE).read_text())
    data[0]["name"] = "Test conversation A changed"
    grown = vault.parent / "g.json"
    grown.write_text(json.dumps(data))
    admit(read_export(grown)[0], vault / "raw", now=NOW)
    (vault / "new.md").write_text(note("decision"), encoding="utf-8")
    assert len(index.query(idx, kind="raw")) == 3
    assert index.query(idx, type="decision") == []
    index.rebuild(vault)
    assert len(index.query(idx, kind="raw")) == 4
    assert paths(index.query(idx, type="decision")) == ["new.md"]


@pytest.mark.parametrize("where", ["vault", "raw", "raw/sub", "parent"])
def test_dod5c_refuses_dangerous_index_dirs(vault, where):
    before = raw_bytes(vault)
    target = {"vault": vault, "raw": vault / "raw", "raw/sub": vault / "raw" / "sub", "parent": vault.parent}[where]
    with pytest.raises(index.IndexLocationError):
        index.rebuild(vault, target)
    assert raw_bytes(vault) == before
    assert not (target / "index.json").exists()


def test_refuses_nonempty_dir_without_marker(vault, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "keep.txt").write_text("keep")
    with pytest.raises(index.IndexLocationError):
        index.rebuild(vault, other)
    assert (other / "keep.txt").read_text() == "keep"


def test_custom_index_dir_reused_with_marker(vault, tmp_path):
    idx = tmp_path / "idx"
    index.rebuild(vault, idx)
    (idx / "note.txt").write_text("unrelated")
    index.rebuild(vault, idx)
    assert (idx / "note.txt").read_text() == "unrelated"  # only the 3 named files are touched


def test_symlinked_index_file_does_not_write_through_to_raw(vault):
    index.rebuild(vault)
    idx = vault / ".heti-index"
    target = sorted((vault / "raw").iterdir())[0]
    before = raw_bytes(vault)
    (idx / "index.json").rename(vault.parent / "old-index.json")
    (idx / "index.json").symlink_to(target)
    index.rebuild(vault)
    assert raw_bytes(vault) == before
    assert not (idx / "index.json").is_symlink()


def test_query_without_index_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        index.query(tmp_path / "nope")
