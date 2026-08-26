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
