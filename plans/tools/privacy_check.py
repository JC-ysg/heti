"""Privacy gate for the overnight memory-loop run (public repo).

Purpose: block commits that contain text from the user's private seed file.
Integration: run before every commit, per plans/overnight-memory-loop-plan.md §5 rule 6.

Method: NFKC-normalize, strip punctuation/whitespace, and compare 6-grams (>= 4 CJK chars)
from the seed against every changed file since BASELINE, untracked files in memory/ and plans/,
and all commit messages since BASELINE. It prints only file names and hit counts, never the
matched text. FAIL-CLOSED: exits 2 if the seed file or BASELINE is missing.

Usage:
    HETI_SEED=<path to seed-all.md> python plans/tools/privacy_check.py --repo
    HETI_SEED=<path> python plans/tools/privacy_check.py <file> [<file> ...]
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import unicodedata

N = 6
META = ("type:", "created:", "source:")
CJK = re.compile(r"[一-鿿]")


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", s)).lower()


def grams(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(META) or line.startswith("```") or line == "---":
            continue
        for prefix in ("## ", "about:", "status:"):
            if line.startswith(prefix):
                line = line[len(prefix):]
        n = norm(line)
        if not CJK.search(n):
            continue
        for i in range(max(1, len(n) - N + 1)):
            g = n[i:i + N]
            if len(CJK.findall(g)) >= 4:
                out.add(g)
    return out


def check(seed: pathlib.Path, targets: list[tuple[str, str]]) -> int:
    g = grams(seed.read_text(encoding="utf-8"))
    bad = 0
    for name, text in targets:
        t = norm(text)
        hits = sum(1 for x in g if x in t)
        if hits:
            bad += 1
            print(f"{name}: {hits} hits")
    print("PRIVACY CHECK: FAIL" if bad else "PRIVACY CHECK: PASS")
    return 1 if bad else 0


def repo_targets(base: str) -> list[tuple[str, str]]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout

    files = set(git("diff", "--name-only", base).split())
    files |= set(git("ls-files", "--others", "--exclude-standard", "memory", "plans").split())
    targets = [(f, pathlib.Path(f).read_text(encoding="utf-8", errors="ignore"))
               for f in sorted(files) if pathlib.Path(f).is_file()]
    targets.append(("<commit messages>", git("log", f"{base}..HEAD", "--format=%B")))
    return targets


def main(argv: list[str]) -> int:
    seed = pathlib.Path(os.environ.get("HETI_SEED", ""))
    if not os.environ.get("HETI_SEED") or not seed.is_file():
        print("SEED MISSING -> FAIL CLOSED (enter degraded mode, plan §5 rule 6b)")
        return 2
    if argv == ["--repo"]:
        base_file = pathlib.Path(".heti-baseline")
        if not base_file.is_file():
            print(".heti-baseline MISSING -> FAIL CLOSED")
            return 2
        return check(seed, repo_targets(base_file.read_text().strip()))
    return check(seed, [(p, pathlib.Path(p).read_text(encoding="utf-8")) for p in argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
