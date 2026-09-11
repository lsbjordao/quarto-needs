"""Release gate: the recorded performance evidence fits its budgets.

Timing assertions are deliberately kept out of CI (see ``tests/test_benchmarks.py``):
what CI can verify deterministically is that the budget document is honest —
every recorded measurement, including the slower topologies, fits inside the
budget derived from the evidence, and the checker flags a violation. Running
the fresh measurement is ``make check-performance-budgets``.
"""
from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
BUDGETS = BENCHMARKS / "budgets.json"


def budget_module():
    spec = spec_from_file_location("check_budgets", BENCHMARKS / "check_budgets.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def budget_document() -> dict[str, object]:
    return json.loads(BUDGETS.read_text(encoding="utf-8"))


def reference_rows() -> list[tuple[Path, dict[str, object]]]:
    document = budget_document()
    shape = document["shape"]
    sources = [
        BENCHMARKS / str(entry).split(" (", 1)[0]
        for entry in document["derivedFrom"]
    ]
    rows = []
    for path in sources:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["results"]:
            if row.get("shape", shape) == shape:
                rows.append((path, row))
    return rows


def measured_stages(row: dict[str, object]) -> set[str]:
    return {
        key
        for key, value in row.items()
        if key.endswith("_ms") and isinstance(value, (int, float))
    }


def test_budget_document_names_its_evidence_and_headroom() -> None:
    document = budget_document()
    assert document["schemaVersion"] == "performance-budgets-v1"
    assert document["derivedFrom"]
    assert document["shape"]
    assert document["headroom"] > 1
    assert document["floorMs"] > 0
    assert document["stages"]
    for stage, by_size in document["stages"].items():
        assert by_size, f"{stage} has no size budgets"


def test_every_recorded_measurement_fits_its_budget() -> None:
    document = budget_document()
    for path, row in reference_rows():
        size = str(row["objects"])
        for stage in measured_stages(row):
            limit = document["stages"].get(stage, {}).get(size)
            if limit is None:
                continue
            assert row[stage] <= limit, (
                f"{path.name}: {stage} at {size} objects recorded {row[stage]} ms "
                f"but the budget is {limit} ms"
            )


def test_budgets_cover_every_stage_measured_on_the_reference_shape() -> None:
    document = budget_document()
    recorded = {stage for _, row in reference_rows() for stage in measured_stages(row)}
    assert recorded <= set(document["stages"]), "a measured stage has no budget"


def test_budgets_cover_every_recorded_size() -> None:
    document = budget_document()
    recorded_sizes = {str(row["objects"]) for _, row in reference_rows()}
    for stage, by_size in document["stages"].items():
        assert recorded_sizes <= set(by_size), f"{stage} is missing a recorded size"


def test_checker_flags_over_budget_and_accepts_compliant_rows() -> None:
    module = budget_module()
    document = budget_document()
    stage = next(iter(document["stages"]))
    size = "100"
    limit = document["stages"][stage][size]

    compliant = {"objects": int(size), stage: limit}
    assert module.evaluate(compliant, document) == []

    violation = {"objects": int(size), stage: limit + 1}
    messages = module.evaluate(violation, document)
    assert messages and stage in messages[0]


def test_checker_ignores_sizes_it_has_no_budget_for() -> None:
    module = budget_module()
    document = budget_document()
    stage = next(iter(document["stages"]))
    assert module.evaluate({"objects": 7, stage: 10_000}, document) == []
