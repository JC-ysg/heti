from __future__ import annotations

import pytest

from memory.__main__ import main
from memory.seed_split import split_seed

A = "---\ntype: fact\ncreated: 2026-01-01\nabout: Fake seed A\nsource: test\nstatus: x\n---\nFake body A\n---\nstill body"
B = "---\ntype: open\ncreated: 2026-01-02\nabout: Fake seed B\nsource: test\nstatus: y\n---\n"
C = "Fake seed C without frontmatter\n\n## not a heading inside the block"

SEED = (
    "# Fake seed collection\n\nIntro text, ignored.\n\n"
    f"## `test-a.md`\n\n```markdown\n{A}\n```\n\n"
    f"## `test-b.md`\n```markdown\n{B}\n```\n\nSome commentary between blocks.\n\n"
    f"## `test-c.md`\n\n```markdown\n{C}\n```\n"
)


def test_split_three_files_byte_identical(tmp_path):
    seed = tmp_path / "seed.md"
    seed.write_text(SEED, encoding="utf-8")
    out = tmp_path / "out"
    assert split_seed(seed, out) == 3
    assert sorted(p.name for p in out.iterdir()) == ["test-a.md", "test-b.md", "test-c.md"]
    assert (out / "test-a.md").read_bytes() == (A + "\n").encode()
    assert (out / "test-b.md").read_bytes() == (B + "\n").encode()
    assert (out / "test-c.md").read_bytes() == (C + "\n").encode()


def test_refuses_to_overwrite(tmp_path):
    seed = tmp_path / "seed.md"
    seed.write_text(SEED, encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    (out / "test-b.md").write_text("keep")
    with pytest.raises(FileExistsError):
        split_seed(seed, out)
    assert (out / "test-b.md").read_text() == "keep"


@pytest.mark.parametrize("bad", ["../evil.md", ".hidden.md", "sub/x.md"])
def test_rejects_illegal_filenames(tmp_path, bad):
    seed = tmp_path / "seed.md"
    seed.write_text(f"## `{bad}`\n```markdown\nFake\n```\n", encoding="utf-8")
    with pytest.raises(ValueError):
        split_seed(seed, tmp_path / "out")
    assert not (tmp_path / "evil.md").exists()


def test_heading_without_block_is_an_error(tmp_path):
    seed = tmp_path / "seed.md"
    seed.write_text("## `test-a.md`\nno block here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        split_seed(seed, tmp_path / "out")


def test_unterminated_block_is_an_error(tmp_path):
    seed = tmp_path / "seed.md"
    seed.write_text("## `test-a.md`\n```markdown\nFake\n", encoding="utf-8")
    with pytest.raises(ValueError):
        split_seed(seed, tmp_path / "out")


def test_cli_prints_only_count(tmp_path, capsys):
    seed = tmp_path / "seed.md"
    seed.write_text(SEED, encoding="utf-8")
    assert main(["seed-split", str(seed), "--out", str(tmp_path / "o")]) == 0
    assert capsys.readouterr().out == "3 files written\n"
