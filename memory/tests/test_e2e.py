"""DoD-3 end to end, through the CLI only: export → ingest → raw → rebuild → query."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from memory import frontmatter
from memory.__main__ import main

FIXTURE = Path(__file__).parent / "fixtures" / "claude_export_min.json"
NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)
OPEN_NOTE = ("---\ntype: open\ncreated: 2026-01-20\nabout: Test open question\nsource: test\n"
             "status: todo\n---\nHello test\n")


def run(capsys, *argv):
    code = main(list(argv), now=NOW)
    return code, capsys.readouterr().out


def test_dod3_end_to_end(tmp_path, capsys, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("HETI_VAULT", str(vault))

    code, out = run(capsys, "ingest-claude", str(FIXTURE))
    assert code == 0 and "written: 3" in out
    raw_files = sorted((vault / "raw").glob("*.md"))
    assert len(raw_files) == 3
    for p in raw_files:
        assert "type" not in frontmatter.parse(p.read_text(encoding="utf-8"))

    (vault / "open-note.md").write_text(OPEN_NOTE, encoding="utf-8")

    code, out = run(capsys, "index", "rebuild")
    assert code == 0 and "raw: 3" in out and "notes: 1" in out

    code, out = run(capsys, "query", "--kind", "raw", "--since", "2026-01-03")
    lines = out.strip().splitlines()
    assert code == 0 and len(lines) == 2
    assert all(line.startswith("raw/") and "  raw  " in line for line in lines)
    for line in lines:
        assert (vault / line.split("  ")[0]).is_file()

    code, out = run(capsys, "query", "--type", "open")
    assert out.strip().splitlines() == ["open-note.md  note  open  todo  Test open question"]

    code, out = run(capsys, "query", "--kind", "raw", "--type", "open")
    assert out.strip() == "no matches"


def test_cli_query_no_matches_and_missing_index(tmp_path, capsys, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("HETI_VAULT", str(vault))
    code, out = run(capsys, "query")
    assert code != 0
    run(capsys, "index", "rebuild")
    code, out = run(capsys, "query", "--type", "fact")
    assert code == 0 and out.strip() == "no matches"


def test_cli_rebuild_refuses_raw_index(tmp_path, capsys, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("HETI_VAULT", str(vault))
    run(capsys, "ingest-claude", str(FIXTURE))
    before = {p.name: p.read_bytes() for p in (vault / "raw").iterdir()}
    for target in (vault, vault / "raw"):
        code = main(["index", "rebuild", "--index", str(target)], now=NOW)
        err = capsys.readouterr().err
        assert code != 0 and "refusing" in err
    assert {p.name: p.read_bytes() for p in (vault / "raw").iterdir()} == before


def test_cli_custom_index_dir(tmp_path, capsys, monkeypatch):
    vault = tmp_path / "vault"
    idx = tmp_path / "idx"
    monkeypatch.setenv("HETI_VAULT", str(vault))
    run(capsys, "ingest-claude", str(FIXTURE))
    run(capsys, "index", "rebuild", "--index", str(idx))
    code, out = run(capsys, "query", "--kind", "raw", "--index", str(idx))
    assert code == 0 and len(out.strip().splitlines()) == 3


def test_cli_validate_counts_and_details(tmp_path, capsys, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("HETI_VAULT", str(vault))
    (vault / "a.md").write_text(OPEN_NOTE, encoding="utf-8")
    (vault / "b.md").write_text(OPEN_NOTE.replace("type: open", "type: fact").replace("todo", "done"), encoding="utf-8")
    (vault / "c.md").write_text(OPEN_NOTE.replace("type: open", "type: idea"), encoding="utf-8")
    (vault / "d.md").write_text(OPEN_NOTE.replace("status: todo\n", "status: todo\ntags: x\n"), encoding="utf-8")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "x.md").write_text("ignored", encoding="utf-8")
    code, out = run(capsys, "validate")
    assert code == 0
    assert out.splitlines() == [
        "files: 4",
        "type decision: 0",
        "type learning: 0",
        "type fact: 1",
        "type open: 2",
        "type other or missing: 1",
        "distinct status values: 2",
        "problems: 1",
        "warnings: 1",
    ]
    assert "todo" not in out and "Test open question" not in out  # counts only by default
    code, out = run(capsys, "validate", "--details")
    assert "c.md: problem: illegal or multiple type: 'idea'" in out
    assert "d.md: warning: extra field: tags" in out
