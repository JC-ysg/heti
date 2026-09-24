"""Split a seed collection file into one markdown file per entry.

Format: a heading line "## `<filename>`" followed by a ```markdown fenced block.
File content = the block's contents + "\n". Output files are opened with "x" (never overwritten).
Errors name line numbers only, never content (seed files are private).
"""
from __future__ import annotations

import re
from pathlib import Path

from .raw_store import check_filename

HEADING_RE = re.compile(r"^## `([^`]+)`\s*$")
FENCE_OPEN = "```markdown"
FENCE_CLOSE = "```"


def parse_seed(text: str) -> list[tuple[str, str]]:
    lines = text.split("\n")
    entries = []
    i = 0
    while i < len(lines):
        m = HEADING_RE.match(lines[i])
        if not m:
            i += 1
            continue
        heading_line = i + 1
        try:
            name = check_filename(m.group(1))
        except ValueError:
            raise ValueError(f"illegal filename in heading at line {heading_line}") from None
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or lines[j].strip() != FENCE_OPEN:
            raise ValueError(f"heading at line {heading_line} is not followed by a ```markdown block")
        k = j + 1
        while k < len(lines) and lines[k] != FENCE_CLOSE:
            k += 1
        if k >= len(lines):
            raise ValueError(f"unterminated ```markdown block starting at line {j + 1}")
        entries.append((name, "\n".join(lines[j + 1:k]) + "\n"))
        i = k + 1
    return entries


def split_seed(seed_path, out_dir) -> int:
    entries = parse_seed(Path(seed_path).read_text(encoding="utf-8"))
    names = [n for n, _ in entries]
    if len(set(names)) != len(names):
        raise ValueError("duplicate filenames in seed")
    out_dir = Path(out_dir)
    existing = [n for n in names if (out_dir / n).exists()]
    if existing:
        raise FileExistsError(f"{len(existing)} target files already exist in {out_dir}; nothing written")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in entries:
        with open(out_dir / name, "x", encoding="utf-8", newline="\n") as f:
            f.write(content)
    return len(entries)
