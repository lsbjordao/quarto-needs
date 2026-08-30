from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from .evidence import build_pytest_evidence, write_json_atomic


_OPTION = "--quarto-needs-evidence"
_ENV = "QUARTO_NEEDS_PYTEST_EVIDENCE"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("quarto-needs")
    group.addoption(
        _OPTION,
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "write deterministic Quarto-Needs pytest evidence JSON to PATH; "
            f"can also be set with {_ENV}"
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requirement(*ids): link this executable test to one or more Quarto-Needs requirement IDs",
    )
    config.addinivalue_line(
        "markers",
        "quarto_need_test_case(*ids): bind this executable test to one or more modeled Quarto-Needs test-case IDs",
    )
    config._quarto_needs_links = {}  # type: ignore[attr-defined]
    config._quarto_needs_results = defaultdict(dict)  # type: ignore[attr-defined]


def _marker_ids(item: pytest.Item, name: str) -> tuple[str, ...]:
    values: set[str] = set()
    for marker in item.iter_markers(name=name):
        for raw in marker.args:
            value = str(raw).strip()
            if not value:
                raise pytest.UsageError(f"@pytest.mark.{name} IDs must not be empty")
            values.add(value)
    return tuple(sorted(values, key=lambda value: (value.casefold(), value)))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    links: dict[str, dict[str, tuple[str, ...]]] = {}
    for item in items:
        requirements = _marker_ids(item, "requirement")
        test_cases = _marker_ids(item, "quarto_need_test_case")
        if requirements or test_cases:
            links[item.nodeid] = {
                "requirements": requirements,
                "testCases": test_cases,
            }
    config._quarto_needs_links = links  # type: ignore[attr-defined]


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    config = getattr(report, "config", None)
    # Pytest reports do not normally carry Config. The canonical collector is
    # therefore populated through pytest_runtest_makereport below. This hook is
    # intentionally a no-op and exists only to document that logreport is not
    # used as a semantic source.
    del config


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    outcome = yield
    report = outcome.get_result()
    results = item.config._quarto_needs_results  # type: ignore[attr-defined]
    results[item.nodeid][report.when] = report.outcome


def _combined_outcome(phases: dict[str, str]) -> str:
    if any(value == "failed" for value in phases.values()):
        return "failed"
    if phases.get("call") == "skipped" or (
        "call" not in phases and any(value == "skipped" for value in phases.values())
    ):
        return "skipped"
    if phases.get("call") == "passed":
        return "passed"
    if phases and all(value == "passed" for value in phases.values()):
        return "passed"
    return "skipped"


def _destination(config: pytest.Config) -> Path | None:
    raw = config.getoption("quarto_needs_evidence") or os.environ.get(_ENV)
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    return Path(str(config.rootpath)) / path


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del exitstatus
    destination = _destination(session.config)
    if destination is None:
        return

    links: dict[str, dict[str, tuple[str, ...]]] = session.config._quarto_needs_links  # type: ignore[attr-defined]
    results = session.config._quarto_needs_results  # type: ignore[attr-defined]
    records: list[dict[str, object]] = []
    for nodeid in sorted(links, key=lambda value: (value.casefold(), value)):
        linked = links[nodeid]
        records.append(
            {
                "nodeid": nodeid,
                "outcome": _combined_outcome(dict(results.get(nodeid, {}))),
                "requirements": linked["requirements"],
                "testCases": linked["testCases"],
            }
        )

    payload = build_pytest_evidence(records, provider_version=pytest.__version__)
    write_json_atomic(destination, payload)
