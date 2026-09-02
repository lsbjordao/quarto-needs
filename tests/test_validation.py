from quarto_needs.model import EngineeringObject, Relation, SourceLocation
from quarto_needs.snapshot import LocationRecord
from quarto_needs.validation import validate


def test_validation_reports_duplicate_and_unknown_target_without_throwing() -> None:
    first = EngineeringObject(
        "REQ-1",
        "need",
        "First",
        relations=[Relation("references", "REQ-1", "MISSING")],
    )
    second = EngineeringObject("REQ-1", "need", "Second")

    findings = validate([second, first])

    assert [(item.code, item.object_id) for item in findings if item.severity == "error"] == [
        ("REQ004", "REQ-1"),
        ("REQ005", "REQ-1"),
    ]


def test_validation_uses_first_duplicate_and_relation_owner_locations() -> None:
    first = EngineeringObject(
        "REQ-1",
        "need",
        "First",
        relations=[Relation("references", "REQ-1", "MISSING")],
        source=SourceLocation("z.qmd", 9, "REQ-1"),
    )
    second = EngineeringObject(
        "REQ-1",
        "need",
        "Second",
        source=SourceLocation("a.qmd", 3, "REQ-1"),
    )

    findings = validate([first, second])

    assert [(item.code, item.location) for item in findings if item.severity == "error"] == [
        ("REQ004", LocationRecord("z.qmd", 9, "REQ-1")),
        ("REQ005", LocationRecord("z.qmd", 9, "REQ-1")),
    ]


def test_missing_rationale_and_unverified_approval_are_ordered_warnings() -> None:
    # Characterization: REQ002/REQ006 carry no location and sort by code.
    obj = EngineeringObject("REQ-1", "system-requirement", "T", status="approved")

    findings = validate([obj])

    assert [
        (item.code, item.severity, item.object_id, item.message, item.location)
        for item in findings
    ] == [
        ("REQ002", "warning", "REQ-1", "REQ-1 has no rationale", None),
        (
            "REQ006",
            "warning",
            "REQ-1",
            "REQ-1 is approved but has no verification relation",
            None,
        ),
    ]


def test_rationale_field_or_body_heading_or_other_type_satisfy_req002() -> None:
    # Characterization: the predicate is `not rationale AND heading not in
    # body`; only the default rationale-governed types are checked.
    with_field = EngineeringObject(
        "REQ-1", "software-requirement", "T", rationale="Because."
    )
    with_heading = EngineeringObject(
        "REQ-2", "system-requirement", "T", body="Text.\n### Rationale\nWhy.\n"
    )
    ungoverned_type = EngineeringObject("REQ-3", "need", "T", status="approved")

    assert validate([with_field, with_heading, ungoverned_type]) == []


def test_verification_check_matches_resolved_v1_relation_names() -> None:
    verified = EngineeringObject(
        "REQ-1",
        "system-requirement",
        "T",
        status="approved",
        relations=[Relation("verified-by", "REQ-1", "TC-1")],
    )
    alias_verified = EngineeringObject(
        "REQ-2",
        "system-requirement",
        "T",
        status="approved",
        relations=[Relation("validated-by", "REQ-2", "TC-2")],
    )
    implemented_only = EngineeringObject(
        "REQ-3",
        "system-requirement",
        "T",
        status="approved",
        relations=[Relation("implements", "REQ-3", "COMP-1")],
    )

    findings = validate([verified, alias_verified, implemented_only])

    assert [item.object_id for item in findings if item.code == "REQ006"] == ["REQ-3"]


def test_validation_output_is_deterministically_ordered() -> None:
    broken = EngineeringObject(
        "REQ-1",
        "system-requirement",
        "T",
        status="approved",
        relations=[Relation("references", "REQ-1", "GHOST")],
    )
    duplicate = EngineeringObject("REQ-1", "need", "Dup")

    findings = validate([duplicate, broken])

    assert [(item.severity, item.code, item.object_id) for item in findings] == [
        ("error", "REQ004", "REQ-1"),
        ("error", "REQ005", "REQ-1"),
        ("warning", "REQ002", "REQ-1"),
        ("warning", "REQ006", "REQ-1"),
    ]
