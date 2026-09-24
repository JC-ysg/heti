# Heti Overnight Autonomous Plan: Test Baseline and Quality Hardening (v2, revised after adversarial review)

> **Read this before each step, and again after any context summarization**
> 1. You are the executing agent for this plan. The user is asleep, so **do not stop to ask anything**. Make every decision yourself according to this document. The user has **authorized in advance**, through this plan, writing inside the repo, committing, and pushing to the designated branch (see §2).
> 2. First read §0 (the north star), §5 (the rules), §7 (the status table), and the last 3 entries in §8 (the progress log).
> 3. **Resume rule:** Continue with the first step in §7 whose status is `TODO` or `IN_PROGRESS`. If it is `IN_PROGRESS`: run `git status` and `git diff` first. If the changes belong to that step and the full test suite is green, carry on. Otherwise run `git restore . && git clean -fd -- tests/`, then redo the step from the beginning (this counts toward the stop-loss limit).
> 4. Check the time with `date -u` and compare it with the **hard deadline** in §5 rule 11. If it has passed, go straight to F2 → F3.
> 5. Do only work that is written in this document. Anything outside it goes to §9. Do not start it.
>
> **Naming convention (to avoid confusion):** acceptance criteria are always written `DoD-n`, and the steps in Phase D are always written `P-D1` through `P-D4`. **This document never uses a bare `Dn`.**

---

## §0 North star (not negotiable)

**Goal: when the user wakes up, running one command reproducibly produces a green, meaningful test suite with no network access; the real bugs found along the way have been fixed, each with a regression test; and a morning report can be read at any point.**

Every decision is judged in this order:
1. Does it keep existing behavior intact? (Tests guard this. **"Degrading gracefully" is also existing behavior. Do not turn it into an error.**)
2. Does it get closer to the DoD in §3?
3. Is it the smallest necessary change?

If the answer to any of these is "no", do not make the change.

---

## §1 Background and baseline (measured at 2026-09-24 06:40 UTC, confirmed again by the review)

| Item | Value |
|---|---|
| Branch | `claude/long-task-autonomous-plan-mhqddg` (repo `JC-ysg/heti`) |
| Python | `python`/`python3` → **3.11.15**; **this interpreter has no tkinter** (the system `python3-tk` is for 3.12) |
| Environment | `xvfb-run` is available; the docker CLI is present but **the daemon is not running**; `unshare -n` works; the GitHub MCP can query Actions |
| Dependency manifest / CI | **None** / **None** |
| `pytest` | **63 passed, 6 skipped, 4 collection errors** |
| Coverage | memory_monitor 73%, openmemory_client 77%, Heti/mcp_server 19%, activity_embedder 10%, **TOTAL 70%** |
| Not measured | `heticontrol.py` (2932 lines, Tkinter), `start_heti.py` (587 lines, **imports tkinter and writes logs at module level**) |

The 4 collection errors:

| File | Root cause |
|---|---|
| `test_heticontrol_functionality.py` (repo root) | A **manual script** (it expects a live server). It imports `heticontrol` → tkinter. Settled in A2 with `testpaths = tests`; **the file is not moved** |
| `tests/test_eddi_g_invoke.py` | Importing `Heti.mcp_server` → `activity_embedder/handler.py:7-13` pulls in dotenv and openai at module level, and **`OpenAI(api_key=None)` is created at import time, which raises `OpenAIError` when there is no key** |
| `tests/test_monitor_embedder.py` | Same as above |
| `tests/test_openmemory_api_endpoints.py` | It needs `mem0/openmemory/openmemory/api/main.py`. **`mem0/openmemory` is a broken gitlink (mode 160000) with no `.gitmodules`**, so the directory is empty |

Confirmed bug candidates (**each still needs a red test written first before it is fixed**):

| ID | Location | Description |
|---|---|---|
| K1 | `Heti/mcp/tools/activity_embedder/handler.py:13` | The OpenAI client is created at import time, so the MCP server cannot be imported without a key (B1 fixes this) |
| K2 | `Heti/mcp_server.py:19` | SSE sends `"data: heartbeat\\n\\n"`, which is a **literal backslash-n**, so the event format is broken |
| K3 | `activity_embedder/handler.py:66-81` | In the retry loop, `last_exc` is not reset before `break`, so "fail on attempt 1, succeed on attempt 2" still returns `status: error` |
| K4 | `activity_embedder/handler.py:11,13,45` | It uses `await` on the **synchronous** `OpenAI` client. It first sends a real, blocking HTTP request, then the `TypeError` gets swallowed, so it always gets the zero vector |
| K5 | `Heti/mcp/tools/eddi_g/handler.py:15-37` | It doesn't catch `FileNotFoundError` when `ollama` is missing (resulting in a 500); it uses a blocking `subprocess.run` without a timeout inside an async function |
| K6 | `tests/test_eddi_g_invoke.py:7-9`, `tests/test_monitor_embedder.py:11-13` | Rewriting the global `server.tool_dispatcher` at import time **pollutes other tests** (to fix: switch to `monkeypatch`. This is a test-only change and does not weaken any assertion) |

Needs human judgment (do not change these): the stub vector is 768 dimensions, while the default model ada-002 is 1536; `eddi_g`'s `--json-input` may not be a valid ollama parameter.

---

## §2 Scope and authorization

### Authorization (addresses `.cursor/rules/heti-project-rules.mdc`)
- Rule 6 (sensitive operations need permission): **the user has authorized in advance, through this plan**, writing inside the repo, committing, and pushing to the designated branch. Anything outside that scope (deleting files, external APIs, other branches) is still not allowed.
- Rules 1 and 2: every new file (including conftest and new test files) gets a **module docstring** (purpose / integration points). Each bug fix includes a mini-spec (Purpose / I/O / Limits) in the function docstring or the commit body.
- Rule 5: failure lessons are written into the report. **Do not write to `.cursor/`.**
- Rule 10 (ambiguity must be clarified first): anything ambiguous goes to §9 and is deferred. Do not stop to wait.

### In scope
- Dependency manifests, pytest configuration, and CI
- Getting collection to zero errors, and the full suite green
- Fixing K1–K6, plus other bugs **confirmed** in C1, in `agent/`, `tools/`, `Heti/`, and `start_heti.py`
- Raising coverage (**meaningful** tests only; see DoD-5)
- The README testing section and the morning report

### Out of scope (**do not touch**)
- Refactoring `heticontrol.py`, or any change to it whatsoever (it gets no tests tonight either)
- `mem0/` (including trying to repair the gitlink)
- Moving or renaming existing files (including the root-level `test_heticontrol*.py`)
- Deleting any test, weakening an assertion, or adding an unconditional `skip`/`xfail`
- **Setting a fake `OPENAI_API_KEY` in conftest or tests to get collection to pass**
- Changing public signatures, `config/*.yaml`, or `.cursor/`
- `git push --force`, rewriting pushed history, pushing to other branches, **creating a PR**
- Calling real external services (OpenAI, Ollama, OpenMemory, Docker). Never writing a real key.

---

## §3 Definition of done (DoD)

| ID | Criterion | How to verify |
|---|---|---|
| DoD-1 | Dependencies install in a fresh venv, with **versions pinned with `==`** | `python -m venv $SCRATCH/v && $SCRATCH/v/bin/pip install -r requirements-dev.txt` succeeds |
| DoD-2 | **0 collection errors, 0 failed**, the full run takes < 120s | `python -m pytest -q` exits with 0 |
| DoD-3 | No new unconditional skips. Every conditional skip has a `reason=` and is listed in the report | `git diff <baseline>..HEAD -- tests/ \| grep -n "skip\|xfail"`, checked one by one |
| DoD-4 | No test was deleted. passed ≥ 63 + the number of new tests | Compare with the baseline |
| DoD-5 | Coverage: memory_monitor ≥ 85%, openmemory_client ≥ 85%, `Heti/` (excluding loop_scripts) ≥ 70%, `start_heti.py` ≥ 50%; **and every new test has at least one assert on a return value or side effect** (no `assert True`, and "doesn't raise" or `is not None` cannot be the only assertion) | `--cov-report=term`; the report explains what behavior 3 randomly chosen new tests protect |
| DoD-6 | The suite passes with **real network isolation** | `unshare -n python -m pytest -q` exits with 0 |
| DoD-7 | CI has run green on this branch at least once | `mcp__github__actions_list` / `actions_get` |
| DoD-8 | Each bug fix: the regression test was **red before and green after** (the red failure lines are pasted into §8). The report states "fixed N bugs" | §8 |
| DoD-9 | All work pushed; `git status` is clean; **`git status --porcelain config/ logs/` is empty** | Commands |
| DoD-10 | `plans/overnight-report.md` is complete (every section in §10) | File |

**Minimum acceptable result:** DoD-1, 2, 8, 9, and 10. DoD-5 and DoD-7 are stretch goals.

---

## §4 Environment bootstrap (idempotent; run first in every new container)

```bash
cd /home/user/heti
git fetch origin claude/long-task-autonomous-plan-mhqddg && git checkout claude/long-task-autonomous-plan-mhqddg && git pull --ff-only origin claude/long-task-autonomous-plan-mhqddg
apt-get install -y -q python3.11-tk xvfb >/dev/null 2>&1 || true
python -c "import tkinter" && echo TK_OK || echo "TK_UNAVAILABLE"   # Trust this line's output
if [ -f requirements-dev.txt ]; then pip install -q -r requirements-dev.txt; else pip install -q pytest pytest-asyncio pytest-cov pytest-timeout httpx fastapi python-dotenv openai pyyaml requests; fi
unset OPENAI_API_KEY
python -m pytest -q 2>&1 | tail -5     # Compare with the latest result in §8
date -u
```

- Scratch files go in the scratchpad directory (`$SCRATCH`), not the repo.
- The repo has no `.env`. If one appears, do not commit it (`load_dotenv()` would read it).

---

## §5 Rules to prevent drift (**must be followed**)

1. **Execution loop for each step:** reread §0/§5/§7/§8 → `date -u` and write the **start time** into the step's note column in §7, mark it `IN_PROGRESS` → schedule a check-in (rule 10) → do the work → run the verification commands → commit the code (one thing per commit) → update §7/§8 and **the matching section of the report** → commit the plan and the report → push.
2. **Stop-loss:** at most **3 attempts** or **60 minutes** (counted from the start time in §7) per step. If it is still not solved: roll back the half-finished changes, mark it `BLOCKED`, record what was tried in §8, and move on to the next step.
3. **Full check:** after each phase and each context summarization, run the complete `python -m pytest -q` + `git status --porcelain config/ logs/`. If something breaks that passed before, fixing it comes first.
4. **Scope check:** before each commit, check the diff. Every file must be within the scope of the current step.
5. **Commits:** `<type>(<area>): <summary>`, with type ∈ {test, fix, build, ci, docs, chore}; one thing per commit; end with the attribution lines the system requires.
6. **Push:** at least once per completed step; on network failure, retry with backoff (2s/4s/8s/16s). **Before pushing, `git log origin/<branch>..HEAD` must not contain a commit that is stuck** (see E1).
7. **Bug fix procedure:** write a failing test first → confirm it is red, with the right kind of failure (for example, K1 must fail with `OpenAIError`, not `ModuleNotFoundError`) → apply the smallest fix → green → full suite. **One bug per commit. Do not fix another bug as a side effect of this one.**
8. **When unsure whether something is a bug:** do not change it. Write it in §9.
9. **Test-quality rules (global):** no `sleep` > 0.1s (patch `time.sleep`/`asyncio.sleep`); no dependence on wall-clock time; no real network access (the conftest blocks it); tests must not write inside the repo (use `tmp_path` + `monkeypatch.chdir`); do not change global state at module level (use `monkeypatch`).
10. **Keeping the session going:** at the start of each step, call `send_later(delay_minutes=45, message="Continue executing plans/overnight-plan.md: read the top resume rule and §0/§5/§7/§8 first")` and record the `trigger_id` in §8. When the next step starts, `delete_trigger` the previous one first, then schedule a new one. When everything is done, delete the last one. If the tool is not available, write that down in §8 and continue.
11. **Hard deadline:** at the start of A1, record **T0** = `date -u` in §8.
    - From **T0 + 6h**, do not start any new step. Go straight to F2 → F3.
    - **F3 must be pushed before T0 + 7h.**
12. **The report is always deliverable:** after A1, immediately create the skeleton of `plans/overnight-report.md` (the section headings from §10). From then on, update the relevant section after each step. **F3 only fills in the summary and does the final check.**

---

## §6 Steps (goal / actions / done criteria / verification)

### Phase A: Foundation

**A1. Dependency manifest + report skeleton**
- Actions:
  - `requirements.txt` (runtime): pyyaml, requests, fastapi, uvicorn, httpx, python-dotenv, openai, psutil
  - `requirements-dev.txt`: `-r requirements.txt` + pytest, pytest-asyncio, pytest-cov, pytest-timeout
  - Pin every package with `==` to **the version you actually verified installs**
  - Windows-only packages (pywin32, pychrome) use `; sys_platform == "win32"`
  - Create the report skeleton (§5 rule 12) and record T0
- Done: DoD-1.

**A2. pytest configuration + safety net**
- `pytest.ini`: `testpaths = tests`, `timeout = 60`, `asyncio_mode = auto` (confirm it doesn't break the existing async tests; if it does, use `strict` instead), and register the markers `gui` and `integration`.
- `.coveragerc`: `omit = Heti/loop_scripts/*` (it's Windows-only and not importable on Linux; explain this in the report).
- `tests/conftest.py` (with a module docstring):
  - Add the repo root to `sys.path`
  - An autouse fixture `monkeypatch.delenv("OPENAI_API_KEY", raising=False)`
  - An autouse fixture that blocks network access: patch `socket.socket.connect` to allow only `127.0.0.1`, `::1`, and `AF_UNIX`, and raise a clear error for everything else
- Done: `pytest --co -q` collects only `tests/`, and the 3 remaining collection errors are still exactly the ones known from §1 (no new ones).

**A3. (Canceled: moving the root-level scripts is no longer done. `testpaths` already avoids collecting them. See §9)**

### Phase B: Getting collection to zero errors

**B1. K1: lazy creation of the OpenAI client** (**do not change any other behavior**)
- Regression test: `tests/test_activity_embedder_import.py`, using `subprocess.run([sys.executable, "-c", "import Heti.mcp_server"], env=<environment with OPENAI_API_KEY removed>, cwd=<repo>)` and asserting returncode == 0 (this avoids a false green from the `sys.modules` cache). **The red run must show `OpenAIError`.**
- Fix: create the client only on first use inside the `if api_key:` branch (a module-level cache).
  - **Behavior with no key stays the same** (use the stub vector and POST as usual). Add another test to lock that behavior in.
  - **Do not switch sync/async** (that is K4, which gets its own commit).
- Done: `test_eddi_g_invoke.py` and `test_monitor_embedder.py` collect and pass.

**B2. Conditional skip for `test_openmemory_api_endpoints.py`**
- **Right after the first import and before any `sys.modules` rewriting** (before line 15), check `os.path.isfile(<the api path the file already computes>/main.py)`.
- If the file is not there, `pytest.skip(reason="needs mem0/openmemory backend source; mem0/openmemory is a gitlink without .gitmodules, so it is empty in this repo", allow_module_level=True)`.
- **Do not change any test content.**
- Done: 1 module-level conditional skip; collection has 0 errors.

**B3. Full suite check** (DoD-2). Record the new passed/skipped/duration in §8.

### Phase E (moved up): CI

**E1. GitHub Actions** (done right after B3, so every later push is also verified by CI)
- `.github/workflows/tests.yml`:
  - Trigger on `push` + `pull_request`
  - `ubuntu-latest`, Python 3.11, `timeout-minutes: 15`
  - `actions/checkout` **without submodules** (because the gitlink is broken)
  - `pip install -r requirements-dev.txt`, then `pytest -q --cov=agent --cov=tools --cov=Heti --cov=start_heti --cov-report=term`
  - Do not use secrets
- **Push it as a standalone commit**, and make sure there are no other unpushed commits locally before pushing.
- If the push is rejected for lacking permission on workflows:
  1. `git reset --soft HEAD~1` (only for this unpushed local commit)
  2. Move the file to `plans/ci/tests.yml` and commit it again
  3. Mark E1 as `BLOCKED (needs the user to move it into place manually)` and note it in the report
- Verify: `mcp__github__actions_list` → the run for this branch. If it fails, read the logs with `get_job_logs`, fix, and push (this counts toward the stop-loss). If you can't query it, write "not verified". **Never claim it is green.**
- From then on, check the CI result of the previous push at the end of each phase.

### Phase C: Bug fixes (**the core value of the night**)

**C1. Systematic review (read only)**
- Scope: `agent/memory_monitor.py`, `tools/openmemory_client.py`, `Heti/**/*.py` (excluding loop_scripts), and `start_heti.py`.
- Checklist:
  - Exception handling that swallows errors
  - Resource leaks, and races between the polling thread and `stop()`
  - Mixing naive and aware datetimes, and timestamp parsing
  - Missing timeouts
  - Falsy-value checks
  - Blocking calls inside async functions
  - Retry logic
  - Whether the `${WEBHOOK_SECRET}` placeholder ever gets substituted
  - Writes to relative paths
- Output: in §8, paste the output of `grep -n "def " <file>`, and mark each function `OK` or with a problem ID. Add new issues to the §1 candidate list (as K7 and onward), each marked **Confirmed/Suspected** with a severity of **High/Medium/Low**.

**C2…Cn. Fix each confirmed bug in order: K2 → K3 → K4 → K5 → K6 → K7 onward (High before Low; up to 10 in total)**
- **Before starting each one, add a row to §7.**
- Follow §5 rule 7.
- K4 uses `asyncio.to_thread` to wrap the synchronous client, or switches to `AsyncOpenAI`. Pick one, and the test must use a mock (no real OpenAI requests).
- K6 changes only how the tests are written (module-level assignment → a `monkeypatch` fixture), and **must not change what the assertions check**.
- K5's regression test must mock `subprocess.run` / `shutil.which`.
- Suspected items go only into §9.

### Phase D: Coverage (meaningful tests only; see DoD-5)

**P-D1. `agent/memory_monitor.py` → ≥ 85%**
- Use `--cov-report=term-missing` to find gaps.
- Priorities: error paths, `_parse_timestamp`, `_apply_env_overrides`, `stop()` edge cases, and `_get_current_poll_interval` backoff.
- Mock the client. Don't start real threads, or if you must, use a short timeout + `join`.

**P-D2. `tools/openmemory_client.py` → ≥ 85%**
- Mock the request layer to cover HTTP errors, timeouts, retries, and malformed JSON.

**P-D3. `Heti/` → ≥ 70%**
- Use `httpx.ASGITransport` to test `invoke_tool` (known tool, unknown tool 404, payload merging).
- **The SSE endpoint must never be read through ASGITransport/TestClient** (the infinite stream hangs). Instead:
  1. Call `resp = await sse_endpoint("c", "u")` directly
  2. Take the first chunk with `await anext(resp.body_iterator)`
  3. Then call `await resp.body_iterator.aclose()`
  4. Patch `asyncio.sleep`

**P-D4. `start_heti.py` → ≥ 50%**
- **Before importing or calling anything, `monkeypatch.chdir(tmp_path)`.** The module writes `logs/heti_startup.log` at import time, and its paths are relative to the working directory.
- If there's no tkinter, inject stub `tkinter`, `tkinter.messagebox`, and `tkinter.scrolledtext` into `sys.modules` **inside the test only** (use a `monkeypatch.setitem` fixture; do not change the source).
- Test targets in `StartupValidator`:
  - `validate_config_files`
  - `create_default_config`
  - `ensure_directories_exist`
  - `is_port_in_use`
  - `check_docker_*` (mock `subprocess.run`)
- Afterwards, `git status --porcelain config/ logs/` must be empty.

### Phase F: Wrap-up

**F1. README**: update only the "Running Tests" section (install commands, the one-line command, markers, conditional skips, and that the network is blocked).

**F2. DoD acceptance**: verify DoD-1 through DoD-10 one by one, pasting evidence into §8 (including `unshare -n python -m pytest -q`).

**F3. Morning report**: fill in the summary, do a final check, commit, and push. `git status` must be clean. Delete the last `send_later`.

---

## §7 Status table

Status: `TODO` / `IN_PROGRESS` / `DONE` / `BLOCKED` / `SKIPPED (reason)` / `PLACEHOLDER`. **Only `TODO` and `IN_PROGRESS` get executed.**

| Step | Status | Start time (UTC) | Commit | Note |
|---|---|---|---|---|
| A1 Dependencies + report skeleton + T0 | TODO | | | |
| A2 pytest configuration / safety net | TODO | | | |
| A3 (canceled) | SKIPPED (moved to §9 after review) | | | |
| B1 K1 lazy OpenAI client | TODO | | | |
| B2 Conditional skip for the backend tests | TODO | | | |
| B3 Full suite check | TODO | | | |
| E1 CI | TODO | | | |
| C1 Systematic review | TODO | | | |
| C2…Cn (one row per bug, replaced after C1) | PLACEHOLDER | | | |
| P-D1 memory_monitor coverage | TODO | | | |
| P-D2 openmemory_client coverage | TODO | | | |
| P-D3 Heti coverage | TODO | | | |
| P-D4 start_heti coverage | TODO | | | |
| F1 README | TODO | | | |
| F2 DoD acceptance | TODO | | | |
| F3 Morning report | TODO | | | |

---

## §8 Progress log (append-only)

```
### [UTC time] <step ID> <DONE|BLOCKED|NOTE>
- What was done:
- Verification command and key output (real output, not paraphrased):
- Test counts: passed=?, skipped=?, failed=?, errors=?
- send_later trigger_id:
- Next step:
```

### [2026-09-24 06:40] BASELINE NOTE
- What was done: Planning phase. Measured the baseline.
- Verification: `python3 -m pytest -q --continue-on-collection-errors` → `63 passed, 6 skipped, 1 warning, 4 errors`; coverage TOTAL 70%.
- Next step: A1 (record T0 at the start)

---

## §9 Parking lot / needs human judgment (write it down, do not do it)

- The root `test_heticontrol.py` / `test_heticontrol_functionality.py` are manual diagnostic scripts. Should they be moved to `scripts/manual/`?
- `heticontrol.py` (2932 lines) has no tests at all. Whether to split it up or add GUI tests is for the user to decide.
- The `mem0/openmemory` gitlink is broken (there is no `.gitmodules`). Should it be turned into a real submodule, or removed?
- activity_embedder's stub vector is 768 dimensions, but ada-002 is 1536. Which is intended?
- Whether eddi_g's `--json-input` is a valid ollama parameter.
- (The executing agent adds more here)

---

## §10 Morning report format (`plans/overnight-report.md`; skeleton created in A1 and updated as you go)

1. **One-sentence summary** (how many DoD items met, how many bugs fixed)
2. **DoD checklist**: DoD-1 through DoD-10, each with ✅/⚠️/❌ and one line of evidence
3. **Before/after numbers**: passed/skipped/errors/duration, and coverage per module
4. **Bugs fixed**: symptom → cause → fix → regression test name → commit
5. **Conditional skips / coverage exclusions**: reason and how to turn them back on
6. **Test quality spot-check**: 3 randomly chosen new tests and what behavior each protects
7. **BLOCKED items**: what was tried, and the suggested next step
8. **Needs your decision** (copied from §9)
9. **Lessons learned** (replaces `.cursor/failure_cases.md`)
10. **How to verify**: 3–5 commands to copy and paste
11. **Commit list**: `git log --oneline <baseline>..HEAD`

---

## Appendix: adversarial review record (v1 → v2)

The review was run by a subagent (it was meant to use Fable, but Fable was out of usage credits, so Opus ran it instead). It raised 15 findings, and all of them were adopted:

| # | Severity | Finding | How it was handled in v2 |
|---|---|---|---|
| 1 | Critical | Reading SSE through ASGITransport hangs forever; no timeout protection | P-D3 now calls the endpoint directly + `anext`; added pytest-timeout, `timeout=60`, and CI `timeout-minutes: 15` |
| 2 | High | B1's "return an error when there's no key" changes the existing degrade-gracefully behavior | B1 now only does lazy creation, and a test locks in the no-key behavior |
| 3 | High | Confirmed bugs in activity_embedder/eddi_g were missing | Added K3–K6 to §1; B1 is limited to not touching sync/async |
| 4 | High | Step D1–D5 names collided with the DoD's D1–D10 | Renamed to `DoD-n` / `P-Dn`, with a convention stated at the top |
| 5 | High | No hard deadline; report written only at the end | §5 rules 11/12: T0+6h / T0+7h; report skeleton created in A1 and updated as work goes |
| 6 | High | CI came too late; a rejected workflow push would block every later push | E1 moved to right after B3, pushed as a standalone commit, with a reset-soft rollback procedure |
| 7 | High | start_heti imports tkinter and writes logs at import time; tests could overwrite the real config | P-D4: chdir(tmp_path), tkinter stub, check `git status config/ logs/` |
| 8 | Medium | The apt command installed the wrong package (3.12's tk) | Changed to `python3.11-tk`, verified with `import tkinter` |
| 9 | Medium | DoD could be gamed (empty-assert coverage, weak offline check, fake key) | DoD-5 assert requirement, DoD-6 `unshare -n`, fake keys banned + autouse delenv, subprocess-based test |
| 10 | Medium | Status table didn't exclude SKIPPED; no recovery procedure after summarization | Only TODO/IN_PROGRESS get executed; IN_PROGRESS recovery procedure; PLACEHOLDER |
| 11 | Medium | send_later only per phase | Scheduled at the start of each step, delete-then-reschedule |
| 12 | Medium | mem0 is a broken gitlink; the skip check has to come before the sys.modules rewrites | B2 wording corrected; CI does not enable submodules |
| 13 | Medium | Unaddressed conflicts with `.cursor/rules` | §2 authorization and compliance notes |
| 14 | Low | A3 was unnecessary and its done criterion could never be met | Canceled, moved to §9 |
| 15 | Low | Unpinned versions, psutil misclassified, incomplete network allowlist, real sleeps | `==` pins, psutil moved to runtime, allowlist includes `::1`/AF_UNIX, global no-sleep rule |
