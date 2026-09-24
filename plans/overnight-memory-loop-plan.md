# Hēti Overnight Autonomous Plan: The First Memory-Layer Loop (v2, revised after adversarial review)

> **Read this before each step, and again after any context summarization**
> 1. You are the executing agent for this plan. The user is asleep, so **do not stop to ask anything**. Make every decision yourself according to this document. Anything this document does not cover goes to §9 "Needs the user's decision". Do not decide it for them.
> 2. First read §0, §2 (especially the red lines), §5, §7, and the last 3 entries of §8.
> 3. **Resume rule:** find the first step in §7 whose status is `TODO` or `IN_PROGRESS`.
>    - If it is `IN_PROGRESS`, first run `git log --oneline $(cat .heti-baseline)..HEAD | grep "\[<step ID>\]"`.
>      - **The step's code commit already exists and the tests are green**: only do the remaining wrap-up (update §7/§8/the report, commit, push).
>      - **No code commit, but the uncommitted changes in `memory/` belong to this step and the tests are green**: carry on.
>      - **Otherwise**: run `git restore memory/ && git clean -fd memory/` (**never restore `plans/`**), then redo the step from the beginning. This counts toward the stop-loss limit.
> 4. Run `date -u` and compare it with the hard deadline in §5 rule 11.
> 5. **This repo is public.** Before every commit, follow §5 rule 6 (the privacy gate).
>
> **Path convention:** shell variables do not carry over between calls. Everywhere in this plan, the scratchpad is written out as the full path `/tmp/claude-0/-home-user-heti/a9426af1-021b-5f32-a6a9-ae111fb2cf9e/scratchpad` (**abbreviated below as `SP`. When you run a command, you must substitute the full path yourself. Never write `$SCRATCH`**).

---

## §0 North star

**When the user wakes up, there is a first memory-layer loop that runs end to end, and it loses nothing:**
- A Claude conversation export passes through the normalization gate.
- It goes into the append-only raw layer, which **keeps the original JSON in full**.
- The index can be rebuilt from scratch.
- A structural query returns answers with file paths.

**Plus:** a tool that splits the seed file into 49 files, and a validation report of the 49 seeds against the L1 contract. **Both are local only and never pushed.**

The user's architecture decisions (the seed file is not in the repo; the code numbers them `#NN`), and the constraints they put on the code:

| # | Constraint on the code |
|---|---|
| #02 | Value lives only in L0 (plain markdown) and L1 (fields and rules). The L2 code must be replaceable within a day. L0 must be readable by eye after all the code is deleted. |
| #04 | **Do not build anything in advance for "being able to do everything later"**: no plugin systems, abstract base classes, or provider interfaces. |
| #06 | Single user. No hard-coded personal paths, keys, or vault locations. |
| #07 | Note contract: 5 fields `type/created/about/source/status`; `type` ∈ {decision, learning, fact, open}; exactly one type per note. It is still being tested by hand: **when something doesn't fit, surface it, don't drop it.** |
| #08/#14 | The raw layer's only job is to **lose nothing**; losing original text is a fatal error. It is append-only, no program may modify it, and models never write back to it. One file per item, named by timestamp. |
| #10/#11 | Anything unusable is not deleted, only left out of the index. The index can be deleted and rebuilt at any time. |
| #12/#13 | Query answers must include the source path, and must not be made up. Tonight only builds structural queries (type/status/time). |
| #35 | A note's `created` = the time it was written into the vault. **This definition does not change tonight.** |
| #37 | Adapters (L2, one per source) and the normalization gate (L1, the only one, which checks format, duplicates, and time). |
| #38/#39 | Connect one source at a time, starting with AI conversations. Claude conversations can be exported. |
| #46 | Scale is solved by chunking in the index layer. |

Every decision is judged in this order:
1. Does it break any of the constraints above?
2. Is it the smallest thing that gets this loop working?
3. Could it be deleted and replaced within a day?

---

## §1 Current state (confirmed 2026-09-24)

- Repo `JC-ysg/heti` is **public**. The branch is `claude/long-task-autonomous-plan-mhqddg`.
- The existing code is the old OpenMemory/mem0 monitor. **It has nothing to do with this plan. Do not touch it.**
- **BASELINE** = the sha in `.heti-baseline` at the repo root (the commit where this plan went in). It is the base for DoD-11, the privacy gate, and resuming.
- Python in the container is 3.11, with PyYAML 6.0.1 and pytest. **The code must also run on Python ≥ 3.9**, because the Mac's built-in python3 may be 3.9.
- Seed file: `SP/seed-all.md` (the original is in `/root/.claude/uploads/*/*heti-vault-seed-all.md`). **It may disappear if the container is rebuilt.** If it is gone, enter degraded mode (§5 rule 6b), and mark S2 as `BLOCKED (seed file missing)`.
- Checks already done on the seed file:
  - 49 `` ## ` `` headings, with one ` ```markdown ` block under each. The blocks are not nested, and there is no CRLF.
  - All 49 have exactly the 5 fields, and every `type` is one of the 4 legal values.
  - `status` has **12 different free-text values** (#07 does not define status values).
- The container runs as **root**. root can overwrite files set to 0444.
- Mac file systems are **case-insensitive**, and the repo already has `Heti/`, so the new package is fixed as `memory/`.

---

## §2 Scope

### Deliverables
1. The `memory/` package (stdlib + PyYAML only, Python ≥ 3.9):
   - `contract.py`
   - `frontmatter.py`
   - `raw_store.py`
   - `gate.py`
   - `adapters/claude_export.py`
   - `index.py`
   - `seed_split.py`
   - `__main__.py` (CLI)
2. `memory/tests/`, using **only synthetic data**.
3. `memory/README.md`: in Chinese.
4. `plans/overnight-memory-loop-report.md`: the morning report.
5. **Local only (never committed):** `SP/out/heti-vault-seed.zip` (the 49 split files + the validation report), sent with `SendUserFile`.

### 🔴 Red lines (breaking one counts as failing the night)
1. **No personal content in the repo or in commit messages.**
   - This covers seed text and filenames, `about`/`status` values, and any real conversation.
   - This covers paraphrases too. When you describe an architecture decision, **only use the wording from the §0 table**.
   - Fixtures must be synthetic and obviously fake (for example "Test note A", "Hello test").
2. **Never read the seed file's content yourself, or anything under `SP/out/`** (no cat, Read, head, or grep printing lines). Handle them only with commands whose output is redirected to a file, or scripts that **print only integers**. This is what keeps seed content out of your context, and so out of anything you write.
3. **No LLM calls, no network access, no API keys, no extraction layer** (the extraction layer waits on #32/#40).
4. **Do not decide open items:**
   - correction and deletion (#29/#30)
   - backup (#31)
   - where derived data goes (#32)
   - queue timeouts (#33)
   - resident processes (#20; **CLI one-shot only, no daemon/watcher**)
   - other people's data and import scope (#42)
5. **The raw layer has no update, delete, or overwrite path**, and that includes the side door through the index rebuild (see I1).
6. **Do not touch the old code** (`agent/ tools/ ui/ Heti/ heticontrol.py start_heti.py tests/ config/ mem0/ .cursor/`).
7. **No PR, no force-push, no pushing to other branches, no new dependencies** (other than pytest).
8. **No speculative abstractions** (#04): no base classes, registries, or plugin loaders.

---

## §3 Definition of done (DoD)

| ID | Criterion | How to verify |
|---|---|---|
| DoD-1 | New tests are all green and take < 30s | `python -m pytest memory/tests -q` |
| DoD-2 | Passes offline | `unshare -n python -m pytest memory/tests -q` |
| DoD-3 | **End-to-end:** synthetic export → `ingest-claude` → raw files appear → `index rebuild` → `query --kind raw --since <date>` lists the imported conversations **with paths**; and a synthetic hand-written note with `type: open` placed in the vault is listed by `query --type open`. **Raw items never get a `type` field.** | `test_e2e.py` + a manual run on synthetic data, with the output pasted into §8 |
| DoD-4 | **Raw is lossless and append-only:** (a) a second write to the same path → `FileExistsError`, original bytes unchanged; (b) importing the same export twice adds 0 files; (c) when a conversation grows, one file is added and the old file is byte-for-byte unchanged; (d) the full original JSON object for each conversation can be recovered from the raw file (`json.loads` equals the original); (e) `grep -rnE "os\.remove\|unlink\|rmtree\|shutil\.move\|open\([^)]*['\"][wa]" memory/ --include=*.py` only hits whitelisted spots in `index.py` | Tests + grep |
| DoD-5 | **The index is derived, not a cache:** (a) delete → rebuild → identical results; (b) after adding a raw file and a note **without rebuilding**, the query does not show them; after rebuilding, it does; (c) `rebuild --index <vault>` or `--index <vault>/raw` → refuses, and raw bytes are unchanged | Tests |
| DoD-6 | The gate rejects empty text, an illegal source, and time that is naive, unparseable, or out of bounds. **Rejections don't disappear silently** (they get a count and a reason) | Tests |
| DoD-7 | Contract validation: missing fields, illegal or multiple types, and an unparseable `created` → problem (not indexed); **extra fields → warning (still indexed)**; `status` is only counted, never judged | Tests |
| DoD-8 | Privacy gate: `HETI_SEED=SP/seed-all.md python plans/tools/privacy_check.py --repo` → `PASS` (exit 0), or the degraded-mode checks in rule 6b pass | Command |
| DoD-9 | Nothing hard-coded | `grep -rnE "/Users/\|/home/\|expanduser\|Path\.home\|['\"]~" memory/ --include=*.py` outputs nothing |
| DoD-10 | Every new test has at least one assertion about a return value or side effect; the report explains what 3 randomly chosen tests protect | Report |
| DoD-11 | All work is pushed, `git status` is clean, and the old code is unchanged | `git diff $(cat .heti-baseline) -- agent tools ui Heti tests config mem0 .cursor heticontrol.py start_heti.py` is empty |
| DoD-12 | The report is complete (§10) | File |

**Minimum acceptable result:** DoD-1, 4, 8, 11, and 12.

---

## §4 Environment bootstrap (idempotent; run first in every new container)

```bash
cd /home/user/heti
git fetch origin claude/long-task-autonomous-plan-mhqddg && git checkout claude/long-task-autonomous-plan-mhqddg && git pull --ff-only origin claude/long-task-autonomous-plan-mhqddg
pip install -q pytest pyyaml
mkdir -p SP && { test -f SP/seed-all.md || cp /root/.claude/uploads/*/*heti-vault-seed-all.md SP/seed-all.md 2>/dev/null; } ; test -f SP/seed-all.md && echo SEED_OK || echo SEED_MISSING
cat .heti-baseline ; python -m pytest memory/tests -q 2>&1 | tail -3 ; date -u
```
(Replace `SP` with the full path.)

---

## §5 Rules to prevent drift

1. **Loop for each step (in this order):**
   1. Reread §0/§2/§7/§8.
   2. `date -u` → write it into the start-time column in §7, and set the status to `IN_PROGRESS`.
   3. Schedule a check-in (rule 10).
   4. **Write the tests first**, then implement.
   5. Run all of `memory/tests`.
   6. `git add -A memory/` → privacy gate (rule 6).
   7. Commit the code. **The message must include the step ID**: `feat(memory): [R2] append-only raw store`.
   8. Update §7/§8 and the report → `git add plans/` → privacy gate → commit `docs(plans): [R2] progress`.
   9. Push.
2. **Stop-loss:** at most 3 attempts or 60 minutes per step. If it is still not done: roll back `memory/` only, mark it `BLOCKED`, write down the reason, and move on to the next step.
3. **Full check:** after each step, run `python -m pytest memory/tests -q`.
4. **Scope check:** every file in the diff must be in `memory/` or `plans/`.
5. **Commits:** type ∈ {feat, test, fix, docs, chore}. End with the attribution lines the system requires. **Commit messages must not contain anything from the seeds.**
6. **Privacy gate (fail-closed):** first `git add`, then run `HETI_SEED=SP/seed-all.md python plans/tools/privacy_check.py --repo`. It checks:
   - the full contents of every file changed since BASELINE
   - untracked files in `memory/` and `plans/`
   - every commit message since BASELINE
   
   Exit codes:
   - exit 0 = you may commit
   - exit 1 = forbidden. Strip out the flagged content and check again. **The tool only prints filenames. Do not try to see what it matched.**
   - exit 2 = the seed file or baseline is missing → rule 6b
   
   **The commit message itself also has to pass the check.** Write it into `SP/msg.txt` first, and run `python plans/tools/privacy_check.py SP/msg.txt`.
   
   **6b. Degraded mode (no seed file):**
   - Commits may only touch `memory/**` and `plans/**`.
   - `git diff --cached | grep -P '[\x{4e00}-\x{9fff}]'` may only hit `memory/README.md` and `plans/` files, and wording about the architecture may only use the §0 table.
   - Write "privacy gate degraded" in §8.
7. **Bugs:** write a red test first, then fix.
8. **When unsure:** do not decide. Write it in §9, and write the code so it is easy to change (formats and field names are centralized in constants).
9. **Test quality:** no sleeps, no network, no writes inside the repo (use `tmp_path`), and inject time with a `now=` parameter. **Do not test read-only status by trying to write (root bypasses it). Use `stat.S_IMODE(mode) == 0o444`.**
10. **Keeping the session going:** at the start of each step, `send_later(delay_minutes=45, message="Continue executing plans/overnight-memory-loop-plan.md: read the top resume rule first")`. Record the `trigger_id` in §8, and delete the previous one. When everything is done, delete the last one. If the tool isn't available, write that down and continue.
11. **Hard deadline:** T0 = the time R1 starts (record it in §8).
    - From T0 + 5.5h, do not start any new step. Go straight to F1 → F2.
    - **F2 must be pushed before T0 + 6.5h.**
12. **The report is always deliverable:** create its skeleton in R1, and update it after each step.

---

## §6 Steps

### Shared technical conventions (every step follows them)
- **Frontmatter parsing** (`memory/frontmatter.py`):
  - The frontmatter is the content between a first line of exactly `---` and the **next** line that is exactly `---`. Everything after that is the body, even if the body contains `---`.
  - Parse with `yaml.load(text, Loader=yaml.BaseLoader)`, so every value stays a string (this avoids dates, `no`, and `12:30` getting auto-converted).
  - When writing, use `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)`.
- **Time:**
  - Before parsing, normalize a trailing `Z` to `+00:00`, then use `datetime.fromisoformat`.
  - Use `timezone.utc`, **not `datetime.UTC`**.
  - Every module has `from __future__ import annotations`.
  - No `match` statements.
- **Filenames:** reject `/`, `..`, and anything starting with `.`.

### Phase R: Foundation

**R1. Package skeleton + frontmatter + contract validation (#07) + report skeleton + T0**
- `memory/__init__.py` (a docstring on the purpose and the L0/L1/L2 split), plus `frontmatter.py` and `contract.py`:
  - `FIELDS = ("type","created","about","source","status")`, `TYPES = {"decision","learning","fact","open"}`
  - `validate_note(fm) -> (problems: list[str], warnings: list[str])`
    - problems: missing fields, illegal or multiple types (a comma or a list), an unparseable `created` (`date.fromisoformat` or `datetime.fromisoformat`)
    - warnings: extra fields
    - `status` is not judged
- Tests:
  - valid; missing fields; extra fields → warning; illegal type; `type: decision, open`
  - bad date; no frontmatter; `status: no` stays the string `"no"`
  - a body containing `---` is not cut off
- Also create `plans/overnight-memory-loop-report.md` (the skeleton of §10), and record T0 in §8.

**R2. Append-only raw layer (#08)**
- `memory/raw_store.py`:
  - `RAW_FIELDS = ("source","source_id","source_sha256","occurred_at","ingested_at")` (**draft L1 format; everything is centralized here**)
  - `write_raw(raw_dir, item, now) -> Path`:
    - Opens with `open(path, "x", encoding="utf-8", newline="\n")` (never overwrites).
    - Then `os.chmod(path, 0o444)`.
    - Filename: `YYYYMMDDTHHMMSSZ-<source>-<source_sha256[:8]>.md`, using the time from `occurred_at` (UTC).
  - `iter_raw(raw_dir)` reads only. **There are no update, delete, or overwrite functions.**
- Tests:
  - write then read back with identical content
  - a second write to the same path → `FileExistsError`, original bytes unchanged
  - `S_IMODE == 0o444`
  - the module's public names contain no update, delete, remove, or overwrite
- Record in §9: "Raw frontmatter format draft (L1). It separates `occurred_at` and `ingested_at` for raw only (the situation #35 anticipated for imports), and **does not change the note `created` definition**."

**R3. Normalization gate (#37)**
- `memory/gate.py`: `admit(items, raw_dir, now) -> GateResult(written, duplicates, rejected)`
  - Input item (**the single contract adapters produce**): `{source, source_id, occurred_at, text, source_sha256}`
    - `text`: the readable body, including the verbatim JSON block
    - `source_sha256`: the hash of the original object from the source, independent of rendering
  - Checks:
    - `text.strip()` is not empty
    - `source` matches `^[a-z0-9_-]+$`
    - `occurred_at` is parseable and has a timezone (naive → reject)
    - 2000-01-01 ≤ `occurred_at` ≤ now + 1 day
  - **Dedup key = `(source, source_id, source_sha256)`**, collected from the frontmatter of existing raw files. A match counts as a duplicate and is not written.
  - `ingested_at = now`.
- Tests: DoD-6 case by case; duplicates; a batch with legal, illegal, and duplicate items mixed; rejection reasons are readable.

### Phase G: The first source

**G1. Claude conversation export adapter (#38)**
- `memory/adapters/claude_export.py`: `read_export(path) -> (items, stats)`
  - Input: `conversations.json`, or a zip or directory containing it.
  - Assumed structure (**written from memory, not verified against a real export; the report must list this as something the user needs to verify**): a list, each conversation `{uuid, name, created_at, updated_at, chat_messages:[{uuid, sender, created_at, text, content:[{type, text?...}], attachments?, files?}]}`.
  - **Lossless body format:**
    ```
    # <name>

    ## <sender> · <created_at>
    <text content of the message: joined content items with type=="text"; if there are none, use text>
    ...

    ## Source JSON (verbatim)
    ```json
    <json.dumps(conv, ensure_ascii=False, indent=1)>
    ```
    ```
    Nothing is dropped from the JSON block: tool_use, thinking, attachments, and files are all there. The transcript part only makes it easy to read by eye.
  - `source_sha256 = sha256(json.dumps(conv, sort_keys=True, ensure_ascii=False))`. `occurred_at` = the conversation's `created_at`. `source_id` = its uuid.
  - Conversations with no messages still go in (**lose nothing**); their transcript part is "(no messages)". `stats` counts the non-text content items that aren't shown in the transcript.
  - Record in §9:
    - The raw form for imports = transcript + verbatim JSON. Confirm this, or pick another lossless form.
    - When a conversation grows and is re-imported, a new raw item is created. Whether queries should show only the newest is tied to #29.
- Tests:
  - A synthetic fixture `memory/tests/fixtures/claude_export_min.json`: 3 conversations, including an empty conversation, a message with only `text`, a `tool_use` item, and an attachment.
  - The DoD-4 (b)(c)(d) tests.

**G2. CLI ingest**
- `python -m memory ingest-claude <path> --vault <path>`, or the `HETI_VAULT` env var. **If neither is given, error out. There is no default.**
- Raw goes into `<vault>/raw/`.
- Output: number written / duplicates / rejected (with reasons) / number of non-text items.
- Test: call `main([...])` directly and assert on the output and the files.

### Phase I: Index and query

**I1. Rebuildable structural index (#11/#13)**
- `memory/index.py`:
  - `rebuild(vault, index_dir=None)`:
    - The default `index_dir` is `<vault>/.heti-index/`.
    - **Safety:** it refuses if `index_dir` is the vault, an ancestor of the vault, or inside `raw/`. If `index_dir` already exists, is not empty, and **has no `.heti-index` marker file**, it refuses.
    - It only deletes and rewrites three files: `index.json`, `problems.json`, and `.heti-index`. **No rmtree.**
  - Scan scope:
    - Notes: `*.md` in the vault, **excluding every directory whose name starts with `.`** (`.obsidian`, `.trash`, `.heti-index`) **and `raw/`**
    - Raw: `raw/*.md`
  - Contents of `index.json`: sorted and deterministic. Each record has `path` (relative to the vault), `kind` (note or raw), and all frontmatter fields (strings).
  - `problems.json`: notes that failed validation (#10: not deleted, only left out of the index) + warnings.
- `query(index_dir, type=None, status=None, since=None, until=None, kind=None)`:
  - Every record includes `path`.
  - `since`/`until` take a date and **compare calendar dates only** (notes use `created`, raw uses the UTC date of `occurred_at`; recorded in §9).
- Tests: DoD-5 (a)(b)(c); invalid notes don't crash it; files in dot directories are not indexed.
- **No chunking or semantic search tonight** (listed in §9 as next steps).

**I2. CLI index / query / validate + E2E**
- `python -m memory index rebuild [--index DIR]`
- `python -m memory query [--type T] [--status S] [--since D] [--until D] [--kind raw|note]`: one line per item, `path  kind  type  status  about`. When nothing matches, print "no matches" (#12).
- `python -m memory validate`: contract validation for the whole vault. **By default it prints only counts** (number of files, type distribution counts, number of distinct status values, number of problems, number of warnings). `--details` prints item by item.
- `memory/tests/test_e2e.py`: the full DoD-3.

### Phase S: Seeds (local only)

**S1. `seed_split.py`** (the tool is committed; its output is not)
- `python -m memory seed-split <seed-all.md> --out <dir>`
  - Extracts each `` ## `<filename>` `` and the ` ```markdown ` block right after it. **File content = the block's contents + `"\n"`**.
  - Opens files with `"x"` (refuses to overwrite).
  - Rejects illegal filenames.
  - Output: only "N files written".
- Tests: a **synthetic** 3-entry mini seed file (content obviously fake) → 3 files, byte-for-byte identical.

**S2. Run it on the real seed file** (**all output is redirected. Only integers may be read**)
```bash
cd SP && rm -rf out && mkdir out
python -m memory seed-split SP/seed-all.md --out SP/out/vault-seed > SP/out/split.log 2>&1   # run from the repo root
HETI_VAULT=SP/out/vault-seed python -m memory validate > SP/out/seed-validation.txt 2>&1
HETI_VAULT=SP/out/vault-seed python -m memory validate --details >> SP/out/seed-validation.txt 2>&1
HETI_VAULT=SP/out/vault-seed python -m memory index rebuild > /dev/null 2>&1
HETI_VAULT=SP/out/vault-seed python -m memory query --type open > SP/out/seed-open.txt 2>&1
python -c "import pathlib;print(len(list(pathlib.Path('SP/out/vault-seed').glob('*.md'))))"   # Expect 49
HETI_VAULT=SP/out/vault-seed python -m memory validate   # Prints counts only; this is the only output you may read
```
- Write `SP/out/README-status-note.md` (a template for a new `open` note). Its wording is limited to: "The `status` field has no defined values in the contract, and the seeds use N different values in practice (N from the counts above). Please decide the allowed values." **Do not list the values themselves.**
- Zip it with Python `zipfile` into `SP/out/heti-vault-seed.zip`, then send it with `SendUserFile` (status=proactive). If that fails, write down the path.
- **In the repo's report, write only integers:** file count, per-type counts, number of distinct status values, number of problems, number of warnings.

### Phase F: Wrap-up

**F1. `memory/README.md`** (in Chinese):
- Minimum Python version, `python3 -m pip install pyyaml`, and the 3 commands to use it.
- Env vars and the directory structure.
- What it does and doesn't do.
- Architecture sources (**only the wording from the §0 table**).
- **⚠️ Warning:** "Before your first real import, try it on a throwaway `--vault`. Anything imported into raw has no deletion mechanism yet (#30), and exports contain other people's words (#42)."

**F2. DoD acceptance + morning report:** check DoD-1 to DoD-12 one by one and paste the evidence into §8. Complete the report, then run the privacy gate, commit, and push. `git status` must be clean. Delete the last `send_later`.

---

## §7 Status table

Status: `TODO` / `IN_PROGRESS` / `DONE` / `BLOCKED` / `SKIPPED (reason)`. **Only `TODO` and `IN_PROGRESS` get executed.**

| Step | Status | Start (UTC) | Code commit | Note |
|---|---|---|---|---|
| R1 frontmatter + contract + report skeleton + T0 | DONE | 2026-09-24 07:31 | 295f5a3 | T0=07:31Z; privacy gate degraded (seed missing) |
| R2 Append-only raw layer | DONE | 2026-09-24 07:42 | dbc22d5 |  |
| R3 Normalization gate | DONE | 2026-09-24 07:47 | f2a9308 |  |
| G1 Claude export adapter (lossless) | DONE | 2026-09-24 07:54 | d823c11 | export format unverified |
| G2 CLI ingest | DONE | 2026-09-24 08:01 | 65acb08 |  |
| I1 Rebuildable index + query | TODO | | | |
| I2 CLI index/query/validate + E2E | TODO | | | |
| S1 seed_split tool | TODO | | | |
| S2 Real seeds (local only) | TODO | | | |
| F1 README | TODO | | | |
| F2 DoD acceptance + report | TODO | | | |

---

## §8 Progress log (append-only. **Never paste seed-related output. Integers only**)

```
### [UTC] [<step>] <DONE|BLOCKED|NOTE>
- What was done:
- Verification command and real output (synthetic data only):
- Tests: passed=? failed=?
- Privacy gate: PASS / degraded (reason)
- send_later trigger_id:
- Next step:
```

### [2026-09-24] PLAN NOTE
- The plan (v2) is written. The user asked to "do Heti" and let the agent pick the direction; based on the seed file, it is set to "the first memory-layer loop". The repo is public, so there is a privacy red line and a fail-closed gate (`plans/tools/privacy_check.py`, which was confirmed to catch a leak, pass clean files, and block when the seed is missing).
- Next step: R1

### [2026-09-24 07:31 UTC] [SETUP] NOTE
- Executed in a new container/session. The branch this session may push to is `claude/goal-xh1iiw`, so `origin/claude/long-task-autonomous-plan-mhqddg` (plan + BASELINE) was fast-forwarded into it, and all work happens there (red line 7: no pushing to other branches).
- This session's scratchpad (SP) = `/tmp/claude-0/-home-user-heti/ec61c7be-75d4-593e-a9a1-1107fae05646/scratchpad`.
- **Seed file missing:** `/root/.claude/uploads/` doesn't exist and a whole-filesystem search found no seed file → **privacy gate degraded** (§5 rule 6b). The gate script `SP/gate.sh`: runs `privacy_check.py --repo` (exit 2 = degraded), checks that staged files are only in `memory/`/`plans/`, checks that staged CJK only hits `memory/README.md`/`plans/`, and checks that the commit message has no CJK.
- The first version of the gate script used `grep -P '\x{4e00}'`, which failed silently under this locale (fail-open). It was found and replaced with a Python regex detector (self-tested: CJK → detected). Afterwards, the R1 commit's diff and message were checked retroactively: no CJK.
- Environment: Python 3.11.15, PyYAML 6.0.1, pytest 9.1.1 (installed with pip).
- send_later trigger_id: trig_014t9eEJqwjmyDQbkcxaLfcf

### [2026-09-24 07:40 UTC] [R1] DONE
- What was done: `memory/__init__.py`, `frontmatter.py` (BaseLoader, explicit `---` boundaries), `contract.py` (`FIELDS`/`TYPES`/`validate_note`/`parse_time`), and the report skeleton `plans/overnight-memory-loop-report.md`. **T0 = 2026-09-24 07:31 UTC** → no new steps start after 13:01, and F2 must be pushed before 14:01.
- Verification: `python -m pytest memory/tests -q` → `12 passed in 0.05s`
- Tests: passed=12 failed=0
- Privacy gate: degraded (seed missing); DEGRADED GATE: PASS
- Next step: R2

### [2026-09-24 07:46 UTC] [R2] DONE
- What was done: `memory/raw_store.py`: `RAW_FIELDS`, `write_raw` (`open(..., "x")` + `chmod 0o444`, filename `YYYYMMDDTHHMMSSZ-<source>-<sha8>.md`), read-only `iter_raw`, and `check_filename` (rejects `/`, `..`, and a leading `.`). No update/delete/overwrite functions.
- Verification: `python -m pytest memory/tests -q` → `19 passed in 0.06s`
- Tests: passed=19 failed=0 (new: read back after write, second write raises FileExistsError with bytes unchanged, S_IMODE==0o444, no mutating public names, illegal source filename)
- Privacy gate: degraded; DEGRADED GATE: PASS
- Code commit: dbc22d5
- Next step: R3

### [2026-09-24 07:52 UTC] [R3] DONE
- What was done: `memory/gate.py`: `admit(items, raw_dir, now) -> GateResult(written, duplicates, rejected)`. Checks: text is not empty, `source` matches `^[a-z0-9_-]+$`, `source_sha256` is hex, `occurred_at` is parseable, has a timezone (naive or date-only → reject), and falls in 2000-01-01 ≤ t ≤ now+1d. Dedup key = `(source, source_id, source_sha256)` (from existing raw frontmatter + seen within this batch). Filename collisions are rejected with a reason, never overwritten. Every rejection carries a readable reason (DoD-6).
- Verification: `python -m pytest memory/tests -q` → `33 passed`
- Tests: passed=33 failed=0
- Privacy gate: degraded; DEGRADED GATE: PASS
- Code commit: f2a9308
- Next step: G1

### [2026-09-24 08:00 UTC] [G1] DONE
- What was done: `memory/adapters/claude_export.py`: `read_export(path)` takes json/directory/zip; body = transcript + verbatim JSON; `source_sha256` = sha256(json.dumps(conv, sort_keys=True, ensure_ascii=False)); `extract_source_json(body)` recovers the original object; empty conversations still go in ("(no messages)"); stats count non-text items/attachments/files. Synthetic fixture `memory/tests/fixtures/claude_export_min.json` (3 conversations: empty conversation, text-only message, tool_use, attachment).
- Verification: `python -m pytest memory/tests -q` → `42 passed`
- Tests: passed=42 failed=0 (includes DoD-4 b: re-import adds 0; c: a grown conversation adds 1 and the old one is byte-for-byte unchanged; d: json.loads equals the original for all 3; the hash doesn't depend on key order; a malformed conversation gets rejected with a reason)
- Privacy gate: degraded; DEGRADED GATE: PASS
- Code commit: d823c11
- Next step: G2

### [2026-09-24 08:05 UTC] [G2] DONE
- What was done: `memory/__main__.py`: `python -m memory ingest-claude <path> [--vault V]` (or `HETI_VAULT`; **if neither is given, error out, no default**); raw goes into `<vault>/raw/`; output: number written / duplicates / rejected (source_id + reason for each) / number of non-text items. `main(argv, now=)` can be called directly from tests.
- Verification (synthetic fixture, manual run):
  ```
  $ python -m memory ingest-claude memory/tests/fixtures/claude_export_min.json --vault SP/demo
  written: 3
  duplicates: 0
  rejected: 0
  non-text items: 1 (kept in the verbatim JSON block)
  $ python -m memory ingest-claude memory/tests/fixtures/claude_export_min.json
  python -m memory: error: no vault given: pass --vault or set HETI_VAULT (there is no default)
  $ ls SP/demo/raw
  20260102T030405Z-claude-2711c963.md
  20260103T000000Z-claude-0aa20d53.md
  20260104T000000Z-claude-213a9dd1.md
  ```
- Tests: `python -m pytest memory/tests -q` → `47 passed`; failed=0
- Privacy gate: degraded; DEGRADED GATE: PASS
- Code commit: 65acb08
- Next step: I1

---

## §9 Needs the user's decision (write it down, do not do it)

- The raw-layer frontmatter format (draft L1): `source/source_id/source_sha256/occurred_at/ingested_at`.
- The raw form for imports = readable transcript + verbatim source JSON. Is that acceptable?
- Whether a conversation that keeps growing should show only its newest version in queries (tied to #29).
- The allowed values for `status` (the seeds contain several distinct values).
- Whether extra frontmatter fields (such as Obsidian's `tags`) are allowed. Right now they only produce a warning.
- Whether `--since` for raw should compare `occurred_at` (the current implementation) or `ingested_at`.
- Import scope and filtering (other people's data, private content; #42/#30).
- The repo is **public**. Should Hēti move to a private repo? Should the old OpenMemory code be archived?
- Next steps: semantic search (embedding choice), chunking (#46), the extraction layer (waits on #32/#40), the next source.
- [R2] Raw frontmatter format draft (L1). It separates `occurred_at` and `ingested_at` for raw only (the situation #35 anticipated for imports), and **does not change the note `created` definition**. Filename = UTC time of `occurred_at` + source + first 8 hex chars of `source_sha256`; the fields are centralized in `memory/raw_store.RAW_FIELDS`.
- [G1] The raw form for imports = transcript + verbatim JSON (`## Source JSON (verbatim)` + a ```json block, `json.dumps(conv, ensure_ascii=False, indent=1)`). Confirm this, or pick another lossless form.
- [G1] When a conversation grows and is re-imported, a new raw item is created (the old one is unchanged). Whether queries should show only the newest is tied to #29.
- [G1] The Claude export structure was written from memory and **has not been checked against a real export**. Before a real import, check it on a throwaway vault first. Note: on Python 3.9/3.10, `datetime.fromisoformat` only accepts 3 or 6 fractional digits; any other precision gets rejected by the gate as unparseable (with a reason, not silently).
- (The executing agent adds more here)

---

## §10 Morning report format (`plans/overnight-memory-loop-report.md`)

1. **One-sentence summary**
2. **Try it now**: minimum Python version, installing pyyaml, 3–5 commands (**try a throwaway vault first**)
3. **DoD checklist**: DoD-1 to DoD-12, each with ✅/⚠️/❌ and evidence
4. **What was built**: each module and its matching #NN
5. **What was deliberately not built, and why**
6. **Seed validation results** (integers only) + where the local zip is
7. **Things you need to verify**: whether the real export format matches; whether the raw format is acceptable
8. **Needs your decision** (from §9)
9. **BLOCKED items**
10. **Commit list**

---

## Appendix: adversarial review record

- **v0** (test hardening for the old OpenMemory code): scrapped once the user provided the seed file, because it didn't match the architecture decisions.
- **v1 → v2:** the review was meant to use Fable, but Fable was out of usage credits (429), so an Opus subagent ran the same adversarial prompt. Everything it raised was adopted:

| # | Severity | Finding | How it was handled |
|---|---|---|---|
| C1 | Critical | `$SCRATCH` doesn't expand inside a quoted heredoc, so the privacy check never actually ran (and the comment said to skip it) | Full paths everywhere; the check became `plans/tools/privacy_check.py`, which is fail-closed |
| C2 | Critical | 12-character prefix matching misses things; it only checks staged changes; it doesn't check commit messages; S2 output would leak through §8 | n-gram checking over full file contents + commit messages; git add before checking; ban on reading seed content or `out/`; S2 only reads integers; degraded mode |
| H1 | High | DoD-3 was impossible by design (raw has no type) | DoD-3 now uses `--kind raw` + a synthetic note; raw never gets a type |
| H2 | High | The adapter dropped non-text content, going against #08/#14 | A verbatim JSON block goes into the body, so nothing is lost |
| H3 | High | Dedup used a hash of the rendered body, so changing the adapter would cause permanent duplicates | Dedup key = source + source_id + hash of the source JSON |
| H4 | High | rmtree in rebuild could delete the raw layer | Location checks + marker file + deleting only 3 named files; tested |
| M1 | Medium | root bypasses 0444, so the test would always fail | Check with `S_IMODE` instead |
| M2 | Medium | Resume rule and commit order conflicted | Step ID in commit messages; resume by checking git log; never restore `plans/` |
| M3 | Medium | BASELINE undefined; plan not committed | `.heti-baseline` + committed before launch |
| M4 | Medium | YAML auto-conversion; `---` in the body getting cut | BaseLoader + explicit frontmatter boundaries + tests |
| M5 | Medium | The Mac may only have Python 3.9 | ≥ 3.9 compatibility rules |
| M6 | Medium | Excluding notes with extra fields was stricter than #07 | Extra fields → warning, still indexed |
| M7 | Medium | Time semantics for `--since` were undefined | Compare calendar dates only; notes use `created`, raw uses `occurred_at`; recorded in §9 |
| M8 | Medium | Risks of real imports (#30/#42) weren't flagged | Warnings in the README and report; import scope added to §9 |
| M9 | Medium | Several DoD items were cheap to pass | Stronger DoD-4/5/9 |
| L1–L3 | Low | seed_split's trailing newline, filename validation, dot directories | All adopted |
