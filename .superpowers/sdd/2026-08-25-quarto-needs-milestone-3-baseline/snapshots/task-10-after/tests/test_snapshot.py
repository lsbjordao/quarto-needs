from pathlib import Path
from types import MappingProxyType

import pytest

from quarto_needs.snapshot import freeze_json, thaw_json


def test_freeze_json_is_recursive_and_round_trips() -> None:
    source = {"tags": ["security", "login"], "nested": {"rank": 1}}

    frozen = freeze_json(source)
    source["tags"].append("mutated")

    assert isinstance(frozen, MappingProxyType)
    assert frozen["tags"] == ("security", "login")
    with pytest.raises(TypeError):
        frozen["nested"]["rank"] = 2
    assert thaw_json(frozen) == {
        "nested": {"rank": 1},
        "tags": ["security", "login"],
    }


def test_snapshot_records_reference_date_and_fingerprints(tmp_path: Path) -> None:
    """Baselines need every comparison axis from the snapshot itself."""
    from quarto_needs.analysis import analyze_project
    from quarto_needs.config import reference_date

    (tmp_path / "a.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )

    snapshot = analyze_project(tmp_path).snapshot

    assert snapshot is not None
    assert snapshot.reference_date == reference_date().isoformat()
    assert len(snapshot.configuration_fingerprint) == 64
    assert len(snapshot.semantic_graph_fingerprint) == 64
    assert len(snapshot.representation_fingerprint) == 64
