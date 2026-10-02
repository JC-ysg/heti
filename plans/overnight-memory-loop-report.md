# Hēti Overnight Report: The First Memory-Layer Loop

> Branch: `claude/goal-xh1iiw`. The plan was written for `claude/long-task-autonomous-plan-mhqddg`; this session may only push to `claude/goal-xh1iiw`, so the plan's commits were fast-forwarded here and all work continued on this branch. Nothing was pushed to any other branch and no PR was opened.
> Run window: T0 = 2026-09-24 07:31 UTC → F2 ≈ 08:45 UTC (well inside the 5.5h / 6.5h limits).

## 1. One-sentence summary

The first memory-layer loop runs end to end on synthetic data (Claude export → gate → append-only lossless raw → rebuildable index → structural query with paths), with 75 tests passing on Python 3.9 and 3.11 and offline; the only gap is S2 (real seeds), which is **BLOCKED because the seed file was not present in this container**.

## 2. Try it now

Needs Python ≥ 3.9 and PyYAML. Run from the repo root. **Use a throwaway vault first**: anything imported into raw has no deletion mechanism yet (#30), and exports contain other people's words (#42).

```bash
python3 -m pip install pyyaml
export HETI_VAULT=/tmp/heti-try            # throwaway vault
python3 -m memory ingest-claude <path to the Claude export zip, folder, or conversations.json>
python3 -m memory index rebuild
python3 -m memory query --kind raw --since 2026-01-01
python3 -m memory query --type open
python3 -m memory validate                 # counts only; add --details for item-by-item output
```

Full usage (in Chinese): `memory/README.md`.

## 3. DoD checklist

Evidence was captured on 2026-09-24 ~08:40 UTC; full output is in plan §8 under `[F2]`.

| ID | Result | Evidence |
|---|---|---|
| DoD-1 | ✅ | `python -m pytest memory/tests -q` → `75 passed in 0.34s` (wall clock 0.59s, well under 30s). Also `75 passed` on Python 3.9 via `uv run --python 3.9`. |
| DoD-2 | ✅ | `unshare -n python -m pytest memory/tests -q` → `75 passed`; the network really is off inside it (`OSError: [Errno 101] Network is unreachable`). |
| DoD-3 | ✅ | `test_e2e.py::test_dod3_end_to_end` passes; manual run on synthetic data pasted in §8 `[I2]`: `query --kind raw --since 2026-01-03` lists 2 `raw/...md` paths, `query --type open` lists `open-note.md  note  open  todo  Test open question`; none of the 3 raw files has a `type:` line. |
| DoD-4 | ✅ | (a) `test_second_write_same_path_fails_and_bytes_unchanged`; (b) `test_dod4b_import_twice_adds_zero`; (c) `test_dod4c_grown_conversation_adds_one_file_old_unchanged`; (d) `test_dod4d_original_json_recoverable_from_raw` (all 3 conversations `json.loads` back equal); (e) the grep hits only `memory/index.py:100` (comment) and `memory/index.py:102` (`path.unlink(missing_ok=True)` on the index's own 3 files, the whitelisted spot). Also: `S_IMODE == 0o444`, and a filename collision is rejected rather than overwritten. |
| DoD-5 | ✅ | (a) `test_dod5a_delete_and_rebuild_identical` (byte-identical); (b) `test_dod5b_derived_not_cache`; (c) `test_dod5c_refuses_dangerous_index_dirs[vault/raw/raw/sub/parent]` + `test_cli_rebuild_refuses_raw_index` (raw bytes unchanged). Extra: a symlinked index file does not write through to raw. |
| DoD-6 | ✅ | `test_gate.py` → `14 passed`: empty text, illegal source, naive time, date-only time, unparseable time, out of bounds on both sides, a missing key, duplicates, a mixed batch; every rejection carries a readable reason, and the CLI prints `rejected: N` plus `source_id: reason` for each one. |
| DoD-7 | ✅ | `test_contract.py` → `12 passed`: missing field / illegal type / `decision, open` / list type / bad date / no frontmatter → problem; extra field → warning only (still indexed, see `test_invalid_notes_go_to_problems_not_index`); `status: no` stays `"no"` and is never judged. |
| DoD-8 | ⚠️ degraded | The seed file is missing, so `privacy_check.py --repo` exits 2 (fail-closed). The rule 6b degraded checks were run instead, before every commit and again over the full diff since BASELINE: 0 files outside `memory/`/`plans/` (besides the plan-setup `.heti-baseline`); the only file with CJK is `memory/README.md`; 0 commit messages with CJK. **No seed content could have entered the repo: the seed was never present in this container.** Re-run `HETI_SEED=<seed> python plans/tools/privacy_check.py --repo` on a machine that has it to get the full PASS. |
| DoD-9 | ✅ | `grep -rnE "/Users/\|/home/\|expanduser\|Path\.home\|['\"]~" memory/ --include=*.py` → no output. |
| DoD-10 | ✅ | An AST scan finds 70 test functions, 0 without an `assert`/`pytest.raises`. 3 randomly chosen tests (seed 20260924), see below. |
| DoD-11 | ✅ | Everything is pushed; `git status` is clean after the final commit; `git diff $(cat .heti-baseline) -- agent tools ui Heti tests config mem0 .cursor heticontrol.py start_heti.py | wc -l` → `0`. |
| DoD-12 | ✅ | This file. |

**DoD-10: what 3 random tests protect**
- `test_claude_export.py::test_transcript_rendering`: protects the human-readable half of a raw item. If the adapter stops rendering the title, `## sender · time` headings, text-only messages, or the "(no messages)" marker, raw stops being readable by eye (#02 L0 requirement), even though the JSON block would still be lossless.
- `test_seed_split.py::test_cli_prints_only_count`: protects the privacy red line. The CLI must print exactly `3 files written\n` and nothing else, so running it on the real seed can never echo seed content into an agent's context or a log.
- `test_contract.py::test_illegal_type`: protects #07's "exactly one of 4 types" rule. A note typed `idea` must produce exactly one type problem, so it gets surfaced in `problems.json` instead of silently entering the index.

## 4. What was built

| Module | What it does | Source |
|---|---|---|
| `memory/contract.py` | `FIELDS`, `TYPES`, `validate_note` → (problems, warnings), `parse_time` | #07, #35 |
| `memory/frontmatter.py` | Explicit `---` boundaries, `yaml.BaseLoader` (everything stays a string), `safe_dump` for writing | #02 |
| `memory/raw_store.py` | `write_raw` (`open "x"` + `chmod 0444`, timestamp filename), `iter_raw` (read-only), `RAW_FIELDS`; no update/delete | #08/#14 |
| `memory/gate.py` | `admit` → `GateResult(written, duplicates, rejected)`; format, time bounds, tz required, dedup on `(source, source_id, source_sha256)` | #37 |
| `memory/adapters/claude_export.py` | json/zip/folder → items; transcript + verbatim JSON; hash of the source object | #38/#39, #08 |
| `memory/index.py` | `rebuild` (location safety, marker, only 3 owned files, no rmtree), `query` with type/status/since/until/kind, path on every record | #10/#11, #12/#13 |
| `memory/seed_split.py` | Seed collection → one file per entry, `"x"` open, count-only output | (seed tooling) |
| `memory/__main__.py` | One-shot CLI: `ingest-claude`, `index rebuild`, `query`, `validate`, `seed-split` | #06 (no default vault), #20 (no daemon) |
| `memory/tests/` | 75 tests (70 functions + parametrizations), synthetic data only | — |
| `memory/README.md` | Chinese user docs with the throwaway-vault warning | — |

## 5. What was deliberately not built, and why

- Correction/deletion (#29/#30), backup (#31), where derived data lives (#32), queue timeouts (#33), import scope and other people's data (#42): open items, not the agent's decisions (red line 4).
- Daemons/watchers (#20): the CLI is one-shot only.
- Chunking (#46), semantic search, the extraction layer (waits on #32/#40), any LLM or network call: out of tonight's scope (red line 3).
- Plugin systems, base classes, provider interfaces, adapter registries (#04): one adapter is imported directly by the CLI.
- "Only show the newest version of a grown conversation" in queries: tied to #29, left to you.

## 6. Seed validation results

**BLOCKED: seed file missing.** `/root/.claude/uploads/` does not exist in this container, and a whole-filesystem search found no seed file, so no counts can be reported. The pipeline was dry-run on a synthetic 4-entry fake seed (4 files written, all 4 types counted, 0 problems), so it is ready.

To produce the local zip yourself (output stays on your machine; do not commit it):

```bash
python3 -m memory seed-split <seed-all.md> --out <out>/vault-seed
HETI_VAULT=<out>/vault-seed python3 -m memory validate            # counts
HETI_VAULT=<out>/vault-seed python3 -m memory validate --details  # item by item
HETI_VAULT=<out>/vault-seed python3 -m memory index rebuild
HETI_VAULT=<out>/vault-seed python3 -m memory query --type open
```

## 7. Things you need to verify

1. **The Claude export format was written from memory and has not been checked against a real export** (`uuid`, `name`, `created_at`, `chat_messages[].sender/created_at/text/content[]/attachments/files`). Try a real export on a throwaway vault. If the structure differs, conversations are still stored losslessly (the whole object goes into the JSON block), but the transcript half may read "(no text)", or items may be rejected with a reason (for example, a missing `uuid`).
2. On Python 3.9/3.10, `datetime.fromisoformat` only accepts 3 or 6 fractional-second digits. A timestamp with other precision is rejected by the gate with an "unparseable occurred_at" reason (not silently).
3. Whether the raw form (readable transcript + `## Source JSON (verbatim)` block) is acceptable as L0.
4. Run the full privacy gate with the seed present (DoD-8 was degraded).

## 8. Needs your decision

From plan §9:
- The raw frontmatter format (draft L1): `source/source_id/source_sha256/occurred_at/ingested_at`.
- The raw form for imports = transcript + verbatim JSON. Is that acceptable?
- Whether a conversation that keeps growing should show only its newest version in queries (#29).
- The allowed values for `status`.
- Whether extra frontmatter fields (such as `tags`) are allowed. Right now they only produce a warning.
- Whether `--since` for raw should compare `occurred_at` (current) or `ingested_at`; notes compare the calendar date of `created` as written.
- Import scope and filtering (#42/#30).
- The repo is public. Move Hēti to a private repo? Archive the old OpenMemory code?
- Next steps: semantic search, chunking (#46), the extraction layer (#32/#40), the next source.

## 9. BLOCKED items

- **S2 (real seeds)**: the seed file is not present in this container. Supply it (or run §6 above locally) to finish.
- **DoD-8** is ⚠️ degraded for the same reason (not blocked; the rule 6b checks passed).

## 10. Commit list

Since BASELINE (`e2ae87a`):

- `0f1fc0b` chore(plans): record BASELINE for overnight run (plan setup)
- `295f5a3` feat(memory): [R1] frontmatter parsing and note contract validation
- `ecb1e08` docs(plans): [R1] progress and report skeleton
- `dbc22d5` feat(memory): [R2] append-only raw store
- `842c7b0` docs(plans): [R2] progress
- `f2a9308` feat(memory): [R3] normalization gate with dedup and time checks
- `89afb4a` docs(plans): [R3] progress
- `d823c11` feat(memory): [G1] lossless Claude export adapter
- `c13f780` docs(plans): [G1] progress
- `65acb08` feat(memory): [G2] ingest-claude CLI
- `36ae1a5` docs(plans): [G2] progress
- `40acaf6` feat(memory): [I1] rebuildable structural index and query
- `3d7ec73` docs(plans): [I1] progress
- `8adef0c` feat(memory): [I2] index/query/validate CLI and end-to-end test
- `c4b8b7f` docs(plans): [I2] progress
- `06908ca` feat(memory): [S1] seed-split tool
- `616a582` docs(plans): [S1] progress
- `10bb2d2` docs(plans): [S2] blocked, seed file missing
- `ee214d7` docs(memory): [F1] README
- `adc941f` docs(plans): [F1] progress
- (final) docs(plans): [F2] DoD acceptance and morning report
