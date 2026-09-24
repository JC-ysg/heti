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


def cmd_index_rebuild(vault: Path, args) -> int:
    from . import index

    try:
        summary = index.rebuild(vault, args.index)
    except index.IndexLocationError as e:
        print(str(e), file=sys.stderr)
        return 1
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"index: {args.index or vault / index.INDEX_DIRNAME}")
    return 0


def cmd_query(vault: Path, args) -> int:
    from . import index

    try:
        records = index.query(args.index or vault / index.INDEX_DIRNAME, type=args.type, status=args.status,
                              since=args.since, until=args.until, kind=args.kind)
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    if not records:
        print("no matches")
    for r in records:
        print("  ".join(r.get(k) or "-" for k in ("path", "kind", "type", "status", "about")))
    return 0


def cmd_validate(vault: Path, args) -> int:
    from . import frontmatter
    from .contract import TYPES, validate_note
    from .index import note_paths

    type_order = ("decision", "learning", "fact", "open")
    assert set(type_order) == TYPES
    files = 0
    types = dict.fromkeys(type_order, 0)
    other = 0
    statuses = set()
    details = []
    n_problems = n_warnings = 0
    for p, rel in note_paths(vault):
        files += 1
        try:
            fm = frontmatter.parse(p.read_text(encoding="utf-8"))
            problems, warnings = validate_note(fm)
        except UnicodeDecodeError:
            fm, problems, warnings = None, ["not valid utf-8"], []
        t = (fm or {}).get("type")
        if isinstance(t, str) and t in types:
            types[t] += 1
        else:
            other += 1
        if fm and "status" in fm:
            statuses.add(str(fm["status"]))
        n_problems += bool(problems)
        n_warnings += bool(warnings)
        details += [f"{rel.as_posix()}: problem: {x}" for x in problems]
        details += [f"{rel.as_posix()}: warning: {x}" for x in warnings]
    print(f"files: {files}")
    for t in type_order:
        print(f"type {t}: {types[t]}")
    print(f"type other or missing: {other}")
    print(f"distinct status values: {len(statuses)}")
    print(f"problems: {n_problems}")
    print(f"warnings: {n_warnings}")
    if args.details:
        for line in details:
            print(line)
    return 0


def cmd_seed_split(args) -> int:
    from .seed_split import split_seed

    print(f"{split_seed(args.seed, args.out)} files written")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m memory", description="Hēti memory layer CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest-claude", help="import a Claude conversation export into <vault>/raw/")
    ing.add_argument("path", help="conversations.json, or a zip/directory containing it")
    ing.add_argument("--vault", help=f"vault directory (or set {VAULT_ENV})")

    idx = sub.add_parser("index", help="derived index commands")
    idx_sub = idx.add_subparsers(dest="index_cmd", required=True)
    rb = idx_sub.add_parser("rebuild", help="rebuild the index from the vault (safe to delete any time)")
    rb.add_argument("--index", help="index directory (default <vault>/.heti-index)")
    rb.add_argument("--vault", help=f"vault directory (or set {VAULT_ENV})")

    q = sub.add_parser("query", help="structural query; prints path  kind  type  status  about")
    q.add_argument("--type")
    q.add_argument("--status")
    q.add_argument("--since", help="YYYY-MM-DD, calendar date, inclusive")
    q.add_argument("--until", help="YYYY-MM-DD, calendar date, inclusive")
    q.add_argument("--kind", choices=("raw", "note"))
    q.add_argument("--index", help="index directory (default <vault>/.heti-index)")
    q.add_argument("--vault", help=f"vault directory (or set {VAULT_ENV})")

    v = sub.add_parser("validate", help="check notes against the contract; prints counts only by default")
    v.add_argument("--details", action="store_true", help="also print each problem and warning")
    v.add_argument("--vault", help=f"vault directory (or set {VAULT_ENV})")

    ss = sub.add_parser("seed-split", help="split a seed collection file into one file per entry")
    ss.add_argument("seed")
    ss.add_argument("--out", required=True, help="output directory (existing files are never overwritten)")
    return p


def main(argv=None, now: datetime | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    if args.cmd == "ingest-claude":
        return cmd_ingest_claude(resolve_vault(parser, args), args, now)
    if args.cmd == "seed-split":
        return cmd_seed_split(args)
    if args.cmd == "index":
        return cmd_index_rebuild(resolve_vault(parser, args), args)
    if args.cmd == "query":
        return cmd_query(resolve_vault(parser, args), args)
    if args.cmd == "validate":
        return cmd_validate(resolve_vault(parser, args), args)
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
