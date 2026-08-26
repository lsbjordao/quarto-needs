import pytest

from quarto_needs import graph
from quarto_needs.graph import RequirementsGraph
from quarto_needs.model import EngineeringObject, Relation, SourceLocation


def test_traceability():
    a = EngineeringObject("A", "need", "A", relations=[Relation("derives-from", "A", "B")])
    b = EngineeringObject("B", "need", "B", relations=[Relation("verified-by", "B", "C")])
    c = EngineeringObject("C", "test-case", "C")
    graph = RequirementsGraph.build([a, b, c])
    assert graph.downstream("A") == {"B", "C"}
    assert graph.upstream("C") == {"A", "B"}


def test_graph_rejects_duplicate_ids_instead_of_overwriting() -> None:
    first = EngineeringObject(
        "REQ-1", "need", "First", source=SourceLocation("a.qmd", 1, "REQ-1")
    )
    second = EngineeringObject(
        "REQ-1", "need", "Second", source=SourceLocation("b.qmd", 7, "REQ-1")
    )

    with pytest.raises(getattr(graph, "DuplicateIdError", ValueError)) as caught:
        RequirementsGraph.build([second, first])

    assert caught.value.duplicate_id == "REQ-1"
    assert [(item.file, item.line) for item in caught.value.locations] == [
        ("a.qmd", 1),
        ("b.qmd", 7),
    ]


def test_graph_sorts_adjacency_lists_deterministically() -> None:
    source = EngineeringObject(
        "SOURCE",
        "need",
        "Source",
        relations=[
            Relation("zeta", "SOURCE", "M"),
            Relation("alpha", "SOURCE", "Z"),
            Relation("alpha", "SOURCE", "a"),
        ],
    )
    first = EngineeringObject(
        "FIRST",
        "need",
        "First",
        relations=[Relation("zeta", "Z", "TARGET")],
    )
    second = EngineeringObject(
        "SECOND",
        "need",
        "Second",
        relations=[Relation("alpha", "a", "TARGET")],
    )

    graph = RequirementsGraph.build([source, first, second])

    assert [(item.type, item.target) for item in graph.outgoing["SOURCE"]] == [
        ("alpha", "a"),
        ("alpha", "Z"),
        ("zeta", "M"),
    ]
    assert [(item.type, item.source) for item in graph.incoming["TARGET"]] == [
        ("alpha", "a"),
        ("zeta", "Z"),
    ]
