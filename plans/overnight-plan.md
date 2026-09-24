# Heti Overnight Autonomous Plan: Test Baseline and Quality Hardening

> **Read this before each step, and again after any context summarization**
> 1. You are the executing agent for this plan. The user is asleep, so **do not stop to ask anything**. Make every decision yourself according to this document.
> 2. First read §0 (the north star), §7 (the status table), and the last 3 entries in §8 (the progress log). Then continue with the **first step in §7 whose status is not DONE or BLOCKED**.
> 3. Do only work that is written in this document. Anything outside it goes to §9 (the idea parking lot). Do not start it.

---

## §0 North star (not negotiable)

**Goal: when the user wakes up, running one command reproducibly produces a green, meaningful test suite with no network access, and the real bugs found along the way have been fixed, with a regression test for each one.**

Every decision is judged in this order:
1. Does it keep existing behavior intact? (Tests guard this.)
2. Does it get closer to the "definition of done" in §3?
3. Is it the smallest necessary change?

If the answer to any of these is "no", do not make the change.

---

## §1 Background and baseline (measured at 2026-09-24 06:40 UTC)

| Item | Value |
|---|---|
| Branch | `claude/long-task-autonomous-plan-mhqddg` (repo `JC-ysg/heti`) |
| Python | 3.11 |
| Dependency manifest | **None** (no requirements.txt or pyproject) |
| CI | **None** |
| `pytest` result | **63 passed, 6 skipped, 4 collection errors** |
| Coverage (agent/tools/Heti) | memory_monitor 73%, openmemory_client 77%, Heti/mcp_server 19%, activity_embedder 10%, **TOTAL 70%** |
| Not measured | `heticontrol.py` (2932 lines, Tkinter), `start_heti.py` (587 lines) |

The 4 collection errors and their root causes:

| File | Root cause | Nature |
|---|---|---|
| `test_heticontrol_functionality.py` (repo root) | Imports `heticontrol`, which needs `tkinter`. It is really a **manual script** that expects a live server, not a pytest test | Misclassified |
| `tests/test_eddi_g_invoke.py` | Importing `Heti.mcp_server` → `activity_embedder/handler.py` pulls in `dotenv` and `openai` at module level and **builds the OpenAI client at import time** | Missing dependencies plus a **real bug** (the whole MCP server cannot be imported without `OPENAI_API_KEY`) |
| `tests/test_monitor_embedder.py` | Same as above | Same as above |
| `tests/test_openmemory_api_endpoints.py` | `import main` needs the source of the external backend `mem0/openmemory`, but that directory in the repo is **empty** | External dependency is missing |

Other known risks:
- `Heti/loop_scripts/monitor_embedder.py` imports `win32gui`/`win32process` (Windows only) and `pychrome`.
- The root `test_heticontrol.py` is also a print-style diagnostic script (whether pytest collects it needs to be settled).
- The `mem0/openmemory` backend and Docker are not available in the container, so **every test must run offline** with mocks.

---

## §2 Scope

### In scope
- A dependency manifest (`requirements.txt` and `requirements-dev.txt`) and pytest configuration (`pytest.ini`/`conftest.py`)
- Getting test collection to zero errors and the whole suite green
- Finding and fixing bugs in `agent/`, `tools/`, `Heti/`, and `start_heti.py`. **Each fix comes with a regression test written first.**
- Raising coverage
- A GitHub Actions CI workflow
- A README section on testing, plus the morning report

### Out of scope (**do not touch**)
- Any refactoring of `heticontrol.py`: no splitting it up, renaming, or rearranging the UI. You may only **add tests** for it, plus minimal fixes for bugs you confirm.
- Any content under `mem0/`
- Deleting any test, weakening any assertion, or adding an unconditional `skip`/`xfail` to get green
- Changing public function signatures or config file formats (`config/*.yaml`)
- `git push --force`, rewriting history, or pushing to any branch other than the designated one
- **Creating a PR** (the user did not ask for one)
- Calling real external services (OpenAI, Ollama, OpenMemory, Docker). Never write a real key into the repo.
- Changing the `.cursor/rules` files

---

## §3 Definition of done (DoD): overall acceptance criteria

Each item must be verifiable by a command. Record the actual output as evidence in §8.

| # | Criterion | How to verify |
|---|---|---|
| D1 | A fresh virtualenv can install dependencies | `python -m venv /tmp/v && /tmp/v/bin/pip install -r requirements-dev.txt` succeeds |
| D2 | **0 collection errors, 0 failed** | `python -m pytest -q` exits with 0 |
| D3 | No new unconditional skips. Every conditional skip has a specific `reason=` and is listed in the report | `grep -rn "skip" tests/` compared against the report |
| D4 | Test count ≥ 63 + the number of new tests (no test was deleted) | Compare the passed count with the baseline |
| D5 | Coverage: `agent/memory_monitor.py` ≥ 85%, `tools/openmemory_client.py` ≥ 85%, `Heti/` ≥ 70%, `start_heti.py` ≥ 50% | `pytest --cov=... --cov-report=term` |
| D6 | The suite passes with no network access | Run pytest with `HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=` set; it still passes |
| D7 | The CI workflow exists and has run green on this branch at least once | Query with `mcp__github__actions_list` / `actions_get` |
| D8 | Every bug fix has a regression test, and that test was confirmed **red before the fix and green after** | Recorded in §8 |
| D9 | All work is committed and pushed. `git status` is clean | `git status`, `git log origin/<branch>..HEAD` is empty |
| D10 | `plans/overnight-report.md` is complete | File exists and contains every section listed in §10 |

**Minimum acceptable result (in case time or problems cut the night short):** D1, D2, D8, and D9 are met, and the report is written. D5 and D7 are stretch goals.

---

## §4 Execution environment and bootstrap (run first in every new container)

The container is ephemeral and **may be rebuilt partway through**, so bootstrap must be idempotent:

```bash
cd /home/user/heti
git fetch origin claude/long-task-autonomous-plan-mhqddg && git checkout claude/long-task-autonomous-plan-mhqddg && git pull --ff-only origin claude/long-task-autonomous-plan-mhqddg
apt-get install -y -q python3-tk xvfb >/dev/null 2>&1 || echo "tk/xvfb unavailable -> GUI tests fall back to skip-if"
if [ -f requirements-dev.txt ]; then pip install -q -r requirements-dev.txt; else pip install -q pytest pytest-asyncio pytest-cov httpx fastapi python-dotenv openai pyyaml requests; fi
python -m pytest -q 2>&1 | tail -5     # Compare with the latest result in §8
```

- Scratch files go in the scratchpad directory, not the repo.
- Do not commit `__pycache__`, `.coverage`, or `logs/*` (they are already covered by .gitignore).

---

## §5 Rules to prevent drift (**must be followed**)

1. **Execution loop for each step:**
   `Reread §0/§7/§8 → mark the step IN_PROGRESS in §7 → do the work → run the step's verification commands → commit the code (one thing per commit) → update §7/§8 → commit the plan file → push`
2. **Stop-loss:** A step can be attempted **at most 3 times** or for about **60 minutes**. If it is still not solved, mark it `BLOCKED`, write the cause and what was tried in §8, **roll back any half-finished changes** (`git restore`/`git revert`), and move on to the next step. Never let the whole night stall on one step.
3. **Full check:** After each phase, and after each context summarization, run the complete `python -m pytest -q`. If something breaks that passed before, fixing it comes first.
4. **Scope check:** Before each commit, ask: "Is every file in this diff within the scope of the current step?" If not, split the commit or revert.
5. **Commit convention:** `<type>(<area>): <summary>`, with type ∈ {test, fix, build, ci, docs, chore}. This follows the project rule in `.cursor/rules` of "one change per commit". End each commit message with the attribution lines the system requires.
6. **Push frequency:** Push at least once per completed step. On a network failure, retry with backoff (2s/4s/8s/16s).
7. **Bug fix procedure:** Write a failing test first → run it and confirm it is red (paste the key failure lines into §8) → apply the smallest fix → confirm it is green → run the full suite.
8. **When unsure whether something is a bug:** Do not change the code. Write it into the "needs human judgment" list in §9 and in the report.
9. **Do not "optimize" things for the sake of it:** Renaming, reformatting, and adding type annotations all count as scope creep.
10. **Keeping the session going:** If the environment offers `send_later`, schedule a check-in for 60 minutes later at the end of each phase with this message: "Continue executing plans/overnight-plan.md. First read §0/§7/§8." This ensures that even if the conversation turn ends, work resumes automatically. Once every step is DONE or BLOCKED, stop scheduling.

---

## §6 Steps

Each step lists its **goal / actions / done criteria / verification**.

### Phase A: Foundation

**A1. Dependency manifest**
- Actions: Build `requirements.txt` (runtime: pyyaml, requests, fastapi, uvicorn, httpx, python-dotenv, openai) and `requirements-dev.txt` (`-r requirements.txt` + pytest, pytest-asyncio, pytest-cov) from the actual imports. Windows-only packages (pywin32, pychrome, psutil) get their own `requirements-windows.txt`, or are marked with an environment marker such as `; sys_platform == "win32"`.
- Done: D1 passes.
- Verify: Install into a fresh venv and run `python -c "import agent.memory_monitor, tools.openmemory_client"`.

**A2. pytest configuration**
- Actions: Add `pytest.ini` (`testpaths = tests`, `asyncio_mode = auto` if needed, register markers `gui` and `integration`) and `tests/conftest.py` (add the repo root to `sys.path`, provide a shared `tmp_path` config fixture, and **block real network access** with a fixture that stubs `socket.socket.connect` to only allow 127.0.0.1/ASGI).
- Done: `pytest --co -q` collects only the test files under `tests/`.
- Verify: The collected-count output. Record the before and after numbers.

**A3. Handle the root-level scripts that aren't tests**
- Actions: Move the root `test_heticontrol.py` and `test_heticontrol_functionality.py` into `scripts/manual/` with `git mv`, and rename them `check_heticontrol.py` / `check_heticontrol_functionality.py` so pytest does not pick them up by mistake. Update any references to them in the README or `run_tests.py`.
- Done: `grep -rn "test_heticontrol" .` has no dangling references (except in the report).
- Note: This is a **move, not a deletion**. The contents do not change.

### Phase B: Getting collection to zero errors

**B1. activity_embedder can be imported without a key** (**real bug**)
- Symptom: At import time, `openai_client = OpenAI(api_key=os.getenv(...))` raises an error when the key is missing, so the whole `Heti.mcp_server` fails to import.
- Actions: First write `tests/test_activity_embedder_import.py` (with `OPENAI_API_KEY` removed, import `Heti.mcp_server` and expect success) → confirm it is red → change the client to lazy creation (for example `_get_openai_client()` builds and caches it on first use; without a key the handler returns a clear error instead of crashing) → confirm it is green.
- Done: `tests/test_eddi_g_invoke.py` and `tests/test_monitor_embedder.py` collect and pass.

**B2. Handle the external backend's absence in `test_openmemory_api_endpoints.py`**
- Actions: At the top of the file, check whether the backend source (`main.py`) is importable. If it is not, use `pytest.importorskip`, or `pytest.skip(allow_module_level=True, reason="needs mem0/openmemory backend source (directory is empty in this repo)")`. **Do not change any test content in the file.**
- Done: The file shows 1 conditional skip with a clear reason, and the report lists it.
- Note: This is a skip conditioned on the environment, and it becomes active again automatically once the backend is in place. It is not a skip added to force green.

**B3. Full suite check**
- Done: D2 passes. Record the new passed/skipped counts in §8.

### Phase C: Bug hunt and fixes (**the core value of the night; spend the most time here**)

**C1. Systematic review (read only, no changes)**
- Target: Review `agent/memory_monitor.py`, `tools/openmemory_client.py`, `Heti/**/*.py`, and `start_heti.py` function by function.
- Checklist: exception handling that swallows errors, resource leaks (files, threads, sessions), race conditions (the polling thread vs. `stop()`), timezone mixing (naive vs. aware `datetime`), inconsistent timestamp parsing, missing timeouts, hard-coded paths, falsy-value checks (`if x:` misjudging 0 or ""), SSE string escaping (`mcp_server.py` has `"data: heartbeat\\n\\n"`, which **looks like a real bug**: it sends a literal backslash-n instead of a newline), environment variable interpolation such as the `${WEBHOOK_SECRET}` placeholder never being substituted, and so on.
- Output: A candidate list in §8, each rated **Confirmed / Suspected** with a severity of **High / Medium / Low**.
- Done: The list covers every function in the four areas above (at the function level, not line by line).

**C2…Cn. Fix the confirmed bugs one at a time** (up to 10, ordered High → Low)
- Each bug is its own sub-step, `C2`, `C3`, and so on. Before starting, add it to §7.
- Follow the procedure in §5 rule 7. Each bug is **one commit** containing its test and fix together.
- Suspected items and behavior changes that need product judgment go to §9 only. Do not fix them.

### Phase D: Coverage

**D1. `agent/memory_monitor.py` → ≥ 85%**
- Actions: Use `--cov-report=term-missing` to find uncovered lines. Prioritize error paths, `_parse_timestamp`, `_apply_env_overrides`, `stop()` edge cases, and `_get_current_poll_interval` backoff. Mock the client. Do not start real threads, or if you must, use short timeouts plus `join`.
- Constraints: Tests must be deterministic (no `sleep` > 0.1s, no dependence on wall-clock time. Inject or patch `datetime` instead).

**D2. `tools/openmemory_client.py` → ≥ 85%**
- Actions: Use `unittest.mock.patch("requests.Session.request")` or equivalent to cover HTTP errors, timeouts, retries, and malformed JSON.

**D3. `Heti/` → ≥ 70%**
- Actions: Use `httpx.ASGITransport` to test `invoke_tool` (known tool, unknown tool 404, payload merging) and the handlers (mock the HTTP calls and OpenAI). For the SSE endpoint, read only the first event and then close.
- `loop_scripts/monitor_embedder.py`: If it cannot be imported on Linux, **exclude it from coverage** with `.coveragerc` `omit` and explain why in the report. Do not change it.

**D4. `start_heti.py` → ≥ 50%**
- Actions: Test the non-GUI logic in `StartupValidator` (`validate_config_files`, `create_default_config`, `ensure_directories_exist`, `is_port_in_use`, and `check_docker_available` with a mocked `subprocess.run`), using `tmp_path` so the real repo is untouched.

**D5 (stretch). Smoke tests for `heticontrol.py`**
- Only if tkinter and xvfb are available: add 1–3 tests marked `@pytest.mark.gui` that confirm the module imports and the main class can be instantiated and then destroyed under `xvfb-run`. **Skip it if it doesn't work, mark it BLOCKED, and do not change heticontrol.py to accommodate it.**

### Phase E: CI

**E1. GitHub Actions**
- Actions: `.github/workflows/tests.yml`: triggered on `push` + `pull_request`, ubuntu-latest, Python 3.11, `pip install -r requirements-dev.txt`, `pytest -q --cov=agent --cov=tools --cov=Heti --cov-report=term`. Do not use secrets.
- Verify: After pushing, use `mcp__github__actions_list` to query this branch's run. If it fails, read the logs with `get_job_logs`, fix, and push again (this counts toward the §5 stop-loss). If you cannot query GitHub Actions (permission error), write down "not verified" and why in the report. Do not claim it is green.
- Done: D7.

### Phase F: Wrap-up

**F1. README testing section**: Update the "Running Tests" section (install commands, the one-line pytest command, marker descriptions, and the fact that the backend-dependent tests skip automatically). Change only that section.

**F2. Full DoD acceptance**: Verify D1–D10 one by one and paste the evidence into §8.

**F3. Morning report**: Write `plans/overnight-report.md` (format in §10), commit, and push. **This step must be done even if the night was cut short.** If you notice you are running low on time or context, jump straight to F3.

---

## §7 Status table (update this as you go)

Status values: `TODO` / `IN_PROGRESS` / `DONE` / `BLOCKED` / `SKIPPED (reason)`

| Step | Status | Commit | Note |
|---|---|---|---|
| A1 Dependency manifest | TODO | | |
| A2 pytest configuration | TODO | | |
| A3 Move the manual scripts | TODO | | |
| B1 Lazy creation of the OpenAI client | TODO | | |
| B2 Conditional skip for the backend tests | TODO | | |
| B3 Full suite check | TODO | | |
| C1 Systematic review | TODO | | |
| C2…Cn (added after C1) | — | | |
| D1 memory_monitor coverage | TODO | | |
| D2 openmemory_client coverage | TODO | | |
| D3 Heti coverage | TODO | | |
| D4 start_heti coverage | TODO | | |
| D5 heticontrol GUI smoke (stretch) | TODO | | |
| E1 CI | TODO | | |
| F1 README | TODO | | |
| F2 DoD acceptance | TODO | | |
| F3 Morning report | TODO | | |

---

## §8 Progress log (append-only. Do not edit past entries)

Format for each entry:

```
### [UTC time] <step ID> <DONE|BLOCKED|NOTE>
- What was done:
- Verification command and key output: (paste real output. Do not paraphrase)
- Test counts: passed=?, skipped=?, failed=?, errors=?
- Next step:
```

### [2026-09-24 06:40] BASELINE NOTE
- What was done: Planning phase. Installed pytest and related tools and measured the baseline.
- Verification: `python3 -m pytest -q --continue-on-collection-errors` → `63 passed, 6 skipped, 1 warning, 4 errors`
- Coverage TOTAL 70% (agent/tools/Heti)
- Next step: A1

---

## §9 Idea parking lot / needs human judgment (write it down, do not do it)

- (The executing agent adds items here: refactoring ideas, suspected bugs, behavior changes that need product decisions, and so on.)

---

## §10 Morning report format (`plans/overnight-report.md`)

1. **One-sentence summary** (how many DoD items met, main outcomes)
2. **DoD checklist**: D1–D10, each with ✅/⚠️/❌ and one line of evidence
3. **Before/after numbers**: passed/skipped/errors, and coverage per module
4. **Bugs fixed**: symptom → cause → fix → regression test name → commit
5. **Conditional skips**: each with its reason and how to turn it back on
6. **BLOCKED items**: what was tried, and the suggested next step
7. **Needs your decision** (copied from §9)
8. **How to verify**: 3–5 commands the user can copy and paste
9. **Commit list**: `git log --oneline <baseline>..HEAD`
