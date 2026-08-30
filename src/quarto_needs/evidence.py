from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import quarto_needs


EVIDENCE_SCHEMA_VERSION = "1"


def _text_key(value: str) -> tuple[str, str]:
    return (value.casefold(), value)


def build_pytest_evidence(
    records: Iterable[Mapping[str, Any]], *, provider_version: str
) -> dict[str, object]:
    """Build a deterministic pytest evidence artifact.

    Runtime-only values such as timestamps and durations are intentionally
    excluded. A later attestation layer may add signed run metadata without
    changing the stable semantic evidence payload.
    """

    tests: list[dict[str, object]] = []
    for raw in records:
        nodeid = str(raw["nodeid"])
        outcome = str(raw["outcome"])
        requirements = tuple(
            sorted({str(value) for value in raw.get("requirements", ())}, key=_text_key)
        )
        test_cases = tuple(
            sorted({str(value) for value in raw.get("testCases", ())}, key=_text_key)
        )
        tests.append(
            {
                "nodeid": nodeid,
                "outcome": outcome,
                "requirements": list(requirements),
                "testCases": list(test_cases),
            }
        )

    tests.sort(key=lambda item: _text_key(str(item["nodeid"])))
    counts = Counter(str(item["outcome"]) for item in tests)
    return {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "provider": "pytest",
        "providerVersion": provider_version,
        "generator": {
            "name": "quarto-needs",
            "version": quarto_needs.__version__,
        },
        "summary": {
            "total": len(tests),
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0),
        },
        "tests": tests,
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON artifact atomically and deterministically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
