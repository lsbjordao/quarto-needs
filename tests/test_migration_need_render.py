from __future__ import annotations

from quarto_needs.migrations.render import (
    authorable_extras,
    need_block_problems,
    render_need_block,
)
from quarto_needs.parser import parse_qmd_text_declarations


def test_render_need_block_round_trips_through_the_real_parser() -> None:
    text = render_need_block(
        canonical_id="REQ_001",
        target_type="system-requirement",
        target_status="approved",
        title="Authenticate users",
        body="The system shall authenticate users.",
        tags=("security", "auth"),
        relations=({"relation": "verified-by", "target": "TC_001"},),
    )

    batch = parse_qmd_text_declarations(text, "generated.qmd")

    assert batch.findings == ()
    assert len(batch.declarations) == 1
    declaration = batch.declarations[0]
    assert declaration.id == "REQ_001"
    assert declaration.type == "system-requirement"
    assert declaration.status == "approved"
    assert declaration.title == "Authenticate users"
    assert declaration.body == "The system shall authenticate users."
    assert declaration.attributes["tags"] == "security;auth"
    assert [(r.authored_name, r.target) for r in declaration.relations] == [
        ("verified-by", "TC_001"),
    ]


def test_render_need_block_groups_multiple_targets_for_the_same_relation() -> None:
    text = render_need_block(
        canonical_id="REQ_002",
        target_type="system-requirement",
        target_status=None,
        title="Two verifications",
        body="Body text.",
        tags=(),
        relations=(
            {"relation": "verified-by", "target": "TC_001"},
            {"relation": "verified-by", "target": "TC_002"},
        ),
    )

    assert 'status="' not in text
    batch = parse_qmd_text_declarations(text, "generated.qmd")
    declaration = batch.declarations[0]
    assert [(r.authored_name, r.target) for r in declaration.relations] == [
        ("verified-by", "TC_001"),
        ("verified-by", "TC_002"),
    ]


def test_render_need_block_omits_tags_attribute_when_there_are_no_tags() -> None:
    text = render_need_block(
        canonical_id="REQ_007",
        target_type="system-requirement",
        target_status="approved",
        title="No tags",
        body="Body text.",
        tags=(),
        relations=(),
    )

    assert "tags=" not in text
    batch = parse_qmd_text_declarations(text, "generated.qmd")
    assert batch.declarations[0].attributes.get("tags", "") == ""


def test_need_block_problems_flags_colon_fence_line_in_body() -> None:
    problems = need_block_problems(
        canonical_id="REQ_003",
        target_type="system-requirement",
        target_status="approved",
        title="Title",
        body="line one\n:::\nline three",
        tags=(),
        relations=(),
    )
    assert any("prematurely close" in problem for problem in problems)


def test_need_block_problems_flags_double_quote_in_tag() -> None:
    problems = need_block_problems(
        canonical_id="REQ_004",
        target_type="system-requirement",
        target_status="approved",
        title="Title",
        body="Body",
        tags=('bad"tag',),
        relations=(),
    )
    assert any("tag" in problem for problem in problems)


def test_need_block_problems_flags_semicolon_in_tag() -> None:
    problems = need_block_problems(
        canonical_id="REQ_004B",
        target_type="system-requirement",
        target_status="approved",
        title="Title",
        body="Body",
        tags=("bad;tag",),
        relations=(),
    )
    assert any("tag" in problem for problem in problems)


def test_need_block_problems_flags_invalid_canonical_id_characters() -> None:
    problems = need_block_problems(
        canonical_id="REQ 005!",
        target_type="system-requirement",
        target_status="approved",
        title="Title",
        body="Body",
        tags=(),
        relations=(),
    )
    assert any("canonical ID" in problem for problem in problems)


def test_need_block_problems_flags_newline_in_title() -> None:
    problems = need_block_problems(
        canonical_id="REQ_008",
        target_type="system-requirement",
        target_status="approved",
        title="Two\nlines",
        body="Body",
        tags=(),
        relations=(),
    )
    assert any("title" in problem for problem in problems)


def test_need_block_problems_flags_double_quote_in_target_type() -> None:
    problems = need_block_problems(
        canonical_id="REQ_009",
        target_type='bad"type',
        target_status="approved",
        title="Title",
        body="Body",
        tags=(),
        relations=(),
    )
    assert any("target type" in problem for problem in problems)


def test_need_block_problems_is_empty_for_well_formed_input() -> None:
    problems = need_block_problems(
        canonical_id="REQ_006",
        target_type="system-requirement",
        target_status="approved",
        title="Title",
        body="Body text.",
        tags=("a", "b"),
        relations=({"relation": "verified-by", "target": "TC_001"},),
    )
    assert problems == []


def test_authorable_extras_keeps_only_scalars_with_grammar_safe_names() -> None:
    authored = authorable_extras(
        {
            "priority": "high",
            "effort": 3,
            "ratio": 1.5,
            "urgent": True,
            "tags": ["a", "b"],
            "verified-by": "TC-1",
            "source-id": "REQ_1",
            "nested": {"a": 1},
            "missing": None,
            "multi\nline": "x",
            " leading": "x",
            "trailing ": "x",
            "empty": "  ",
        }
    )

    assert authored == (
        ("effort", "3"),
        ("priority", "high"),
        ("ratio", "1.5"),
        ("urgent", "true"),
    )


def test_render_need_block_authors_extras_that_round_trip() -> None:
    text = render_need_block(
        canonical_id="REQ_007",
        target_type="system-requirement",
        target_status="approved",
        title="Audit authentication events",
        body="The system shall record authentication events.",
        tags=("audit",),
        relations=({"relation": "verified-by", "target": "TC_001"},),
        extras={"priority": "high", "effort": 3},
    )

    declaration = parse_qmd_text_declarations(text, "generated.qmd").declarations[0]

    assert declaration.attributes["priority"] == "high"
    assert declaration.attributes["effort"] == "3"
    assert "priority: high" in text
    assert "verified-by: TC_001" in text
