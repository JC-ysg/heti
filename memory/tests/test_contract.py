from __future__ import annotations

from memory import frontmatter
from memory.contract import FIELDS, TYPES, validate_note

GOOD = "---\ntype: fact\ncreated: 2026-01-02\nabout: Test note A\nsource: test\nstatus: draft\n---\nHello test\n"


def test_fields_and_types_constants():
    assert FIELDS == ("type", "created", "about", "source", "status")
    assert TYPES == {"decision", "learning", "fact", "open"}


def test_valid_note():
    fm = frontmatter.parse(GOOD)
    assert validate_note(fm) == ([], [])


def test_missing_field():
    fm = frontmatter.parse(GOOD.replace("about: Test note A\n", ""))
    problems, _ = validate_note(fm)
    assert problems == ["missing field: about"]


def test_extra_field_is_warning_only():
    fm = frontmatter.parse(GOOD.replace("status: draft\n", "status: draft\ntags: x\n"))
    problems, warnings = validate_note(fm)
    assert problems == []
    assert warnings == ["extra field: tags"]


def test_illegal_type():
    problems, _ = validate_note(frontmatter.parse(GOOD.replace("type: fact", "type: idea")))
    assert len(problems) == 1 and "type" in problems[0]


def test_multiple_types_comma_and_list():
    p1, _ = validate_note(frontmatter.parse(GOOD.replace("type: fact", "type: decision, open")))
    p2, _ = validate_note(frontmatter.parse(GOOD.replace("type: fact", "type: [decision, open]")))
    assert p1 and "type" in p1[0]
    assert p2 and "type" in p2[0]


def test_bad_date():
    problems, _ = validate_note(frontmatter.parse(GOOD.replace("2026-01-02", "yesterday")))
    assert problems == ["unparseable created: 'yesterday'"]


def test_datetime_with_z_is_ok():
    problems, _ = validate_note(frontmatter.parse(GOOD.replace("2026-01-02", "2026-01-02T03:04:05Z")))
    assert problems == []


def test_no_frontmatter():
    assert frontmatter.parse("Hello test\n") is None
    assert validate_note(None) == (["no frontmatter"], [])


def test_status_no_stays_string_and_is_not_judged():
    fm = frontmatter.parse(GOOD.replace("status: draft", "status: no"))
    assert fm["status"] == "no"
    assert fm["created"] == "2026-01-02"
    assert validate_note(fm) == ([], [])


def test_body_containing_delimiter_is_not_cut():
    text = GOOD + "---\nmore body\n"
    fm, body = frontmatter.split(text)
    assert fm["type"] == "fact"
    assert body == "Hello test\n---\nmore body\n"


def test_render_roundtrip():
    fm = {"type": "open", "created": "2026-01-02", "about": "Test note ü é", "source": "t", "status": "x"}
    text = frontmatter.render(fm, "body\n")
    fm2, body = frontmatter.split(text)
    assert fm2 == fm and body == "body\n"
