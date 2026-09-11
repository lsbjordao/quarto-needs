"""Release-rehearsal performance budget check.

CI deliberately asserts no timings (see ``tests/test_benchmarks.py``); this
script is the executable form of the roadmap's performance-budget gate. Run it
on the release machine against the recorded budgets before publishing:

    .venv/bin/python benchmarks/check_budgets.py --sizes 1000,10000,50000

Budgets are recorded evidence plus a documented headroom (``budgets.json``),
never an arbitrary target: a violation means either a real complexity
regression or a machine slower than the headroom allows. Recalibrating means
recording a new baseline with the measurement harness, not widening the budget
silently.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BENCHMARKS = Path(__file__).resolve().parent
REPO = BENCHMARKS.parent
sys.path.insert(0, str(BENCHMARKS))
sys.path.insert(0, str(REPO / "src"))

from benchmark_analysis import measure_size  # noqa: E402

DEFAULT_BUDGETS = BENCHMARKS / "budgets.json"


def load_budgets(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "performance-budgets-v1":
        raise ValueError(f"{path} is not a performance-budgets-v1 document")
    return payload


def evaluate(row: dict[str, object], budgets: dict[str, object]) -> list[str]:
    """Return one message per stage whose measurement exceeds its budget."""
    size = str(row["objects"])
    violations: list[str] = []
    for stage, by_size in budgets["stages"].items():  # type: ignore[union-attr]
        limit = by_size.get(size)
        if limit is None:
            continue
        actual = row.get(stage)
        if actual is None:
            continue
        if actual > limit:
            violations.append(f"{stage} at {size} objects: {actual} ms exceeds {limit} ms")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="1000,10000,50000")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--shape", default="mixed")
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    args = parser.parse_args()

    budgets = load_budgets(args.budgets)
    sizes = [int(value) for value in args.sizes.split(",") if value]
    failures = 0
    for size in sizes:
        row = measure_size(size, args.repeats, shape=args.shape)
        violations = evaluate(row, budgets)
        status = "FAIL" if violations else "PASS"
        print(f"[{status}] {size} objects on the {args.shape} corpus")
        for stage, by_size in budgets["stages"].items():  # type: ignore[union-attr]
            limit = by_size.get(str(size))
            if limit is None:
                continue
            print(f"        {stage}: {row[stage]} ms (budget {limit} ms)")
        for violation in violations:
            print(f"        ! {violation}")
            failures += 1
    if failures:
        print(f"{failures} budget violation(s); record a new baseline or fix the regression")
        return 1
    print("every measured stage is within its release budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
