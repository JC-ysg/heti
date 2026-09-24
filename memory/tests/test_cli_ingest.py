from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from memory.__main__ import main

FIXTURE = Path(__file__).parent / "fixtures" / "claude_export_min.json"
NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_ingest_writes_raw_and_reports(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("HETI_VAULT", raising=False)
    vault = tmp_path / "vault"
    assert main(["ingest-claude", str(FIXTURE), "--vault", str(vault)], now=NOW) == 0
    out = capsys.readouterr().out
    assert "written: 3" in out and "duplicates: 0" in out and "rejected: 0" in out
    assert "non-text items: 1" in out
    assert len(list((vault / "raw").glob("*.md"))) == 3


def test_ingest_twice_reports_duplicates(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("HETI_VAULT", raising=False)
    vault = tmp_path / "vault"
    main(["ingest-claude", str(FIXTURE), "--vault", str(vault)], now=NOW)
    capsys.readouterr()
    main(["ingest-claude", str(FIXTURE), "--vault", str(vault)], now=NOW)
    out = capsys.readouterr().out
    assert "written: 0" in out and "duplicates: 3" in out
    assert len(list((vault / "raw").glob("*.md"))) == 3


def test_ingest_uses_env_vault(tmp_path, capsys, monkeypatch):
    vault = tmp_path / "envvault"
    monkeypatch.setenv("HETI_VAULT", str(vault))
    assert main(["ingest-claude", str(FIXTURE)], now=NOW) == 0
    assert len(list((vault / "raw").glob("*.md"))) == 3


def test_ingest_without_vault_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("HETI_VAULT", raising=False)
    with pytest.raises(SystemExit) as e:
        main(["ingest-claude", str(FIXTURE)], now=NOW)
    assert e.value.code != 0
    assert "vault" in capsys.readouterr().err.lower()
    assert list(tmp_path.iterdir()) == []


def test_ingest_prints_rejection_reasons(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("HETI_VAULT", raising=False)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"uuid": "u1", "name": "Test", "created_at": "not a time", "chat_messages": []}]))
    vault = tmp_path / "vault"
    main(["ingest-claude", str(bad), "--vault", str(vault)], now=NOW)
    out = capsys.readouterr().out
    assert "rejected: 1" in out and "unparseable occurred_at" in out and "u1" in out
