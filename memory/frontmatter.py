"""Frontmatter parsing/writing. Values always stay strings (yaml BaseLoader)."""
from __future__ import annotations

import yaml

DELIM = "---"


def split(text: str) -> tuple[dict | None, str]:
    """Return (frontmatter dict or None, body).

    Frontmatter = lines between a first line that is exactly '---' and the next line
    that is exactly '---'. Everything after is body, even if it contains '---'.
    """
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != DELIM:
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == DELIM:
            raw = "\n".join(lines[1:i])
            try:
                data = yaml.load(raw, Loader=yaml.BaseLoader) if raw.strip() else {}
            except yaml.YAMLError:
                return None, text
            if not isinstance(data, dict):
                return None, text
            return data, "\n".join(lines[i + 1:])
    return None, text


def parse(text: str) -> dict | None:
    return split(text)[0]


def render(fm: dict, body: str) -> str:
    dumped = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    return f"{DELIM}\n{dumped}{DELIM}\n{body}"
