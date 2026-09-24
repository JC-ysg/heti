"""CLI (one-shot only, no daemon). Run `python -m memory -h`."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

VAULT_ENV = "HETI_VAULT"


def resolve_vault(parser: argparse.ArgumentParser, args) -> Path:
    vault = args.vault or os.environ.get(VAULT_ENV)
    if not vault:
        parser.error(f"no vault given: pass --vault or set {VAULT_ENV} (there is no default)")
    return Path(vault)


def cmd_ingest_claude(vault: Path, args, now: datetime) -> int:
    from .adapters.claude_export import read_export
    from .gate import admit

    items, stats = read_export(args.path)
    res = admit(items, vault / "raw", now=now)
    print(f"written: {len(res.written)}")
    print(f"duplicates: {len(res.duplicates)}")
    print(f"rejected: {len(res.rejected)}")
    for item, reason in res.rejected:
        print(f"  - {item.get('source_id')}: {reason}")
    print(f"non-text items: {stats['non_text_items']} (kept in the verbatim JSON block)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m memory", description="Hēti memory layer CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest-claude", help="import a Claude conversation export into <vault>/raw/")
    ing.add_argument("path", help="conversations.json, or a zip/directory containing it")
    ing.add_argument("--vault", help=f"vault directory (or set {VAULT_ENV})")
    return p


def main(argv=None, now: datetime | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    if args.cmd == "ingest-claude":
        return cmd_ingest_claude(resolve_vault(parser, args), args, now)
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
