from quarto_needs.graph import RequirementsGraph
from quarto_needs.model import EngineeringObject, Relation


def test_traceability():
    a = EngineeringObject("A", "need", "A", relations=[Relation("derives-from", "A", "B")])
    b = EngineeringObject("B", "need", "B", relations=[Relation("verified-by", "B", "C")])
    c = EngineeringObject("C", "test-case", "C")
    graph = RequirementsGraph.build([a, b, c])
    assert graph.downstream("A") == {"B", "C"}
    assert graph.upstream("C") == {"A", "B"}
