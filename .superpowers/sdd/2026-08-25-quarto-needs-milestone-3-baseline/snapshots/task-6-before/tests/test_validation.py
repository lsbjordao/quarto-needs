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
