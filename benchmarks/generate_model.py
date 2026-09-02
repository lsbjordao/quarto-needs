"""Deterministic synthetic engineering model generator for benchmarks.

Produces a reproducible Quarto-Needs project text with a fixed seed and
positional, deterministic object IDs. The model mixes requirement,
test, architecture, and evidence objects with relations from several
semantic families (derivation, implementation, verification, evidence,
decomposition, decision-addressing), sized relative to the requested
object count.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

SEED = 20260902

# (type, share of the model, id prefix)
TYPE_PLAN = (
    ("software-requirement", 0.55, "REQ"),
    ("test-case", 0.15, "TC"),
    ("component", 0.10, "COMP"),
    ("container", 0.05, "CONT"),
    ("system", 0.05, "SYS"),
    ("architecture-decision", 0.05, "ADR"),
    ("evidence", 0.05, "EVD"),
)


@dataclass(frozen=True)
class SyntheticModel:
    text: str
    requirement_ids: tuple[str, ...]
    relation_count: int


def _counts(total: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    assigned = 0
    for index, (type_name, share, _prefix) in enumerate(TYPE_PLAN):
        if index == len(TYPE_PLAN) - 1:
            counts[type_name] = total - assigned
        else:
            counts[type_name] = max(1, round(total * share))
            assigned += counts[type_name]
    return counts


def generate_model_text(total: int, seed: int = SEED) -> SyntheticModel:
    """Generate one deterministic QMD buffer with *total* objects."""
    counts = _counts(total)
    ids: dict[str, list[str]] = {}
    for type_name, _share, prefix in TYPE_PLAN:
        ids[type_name] = [
            f"{prefix}-{index:06d}" for index in range(counts[type_name])
        ]

    requirements = ids["software-requirement"]
    tests = ids["test-case"]
    components = ids["component"]
    containers = ids["container"]
    systems = ids["system"]
    decisions = ids["architecture-decision"]
    evidence = ids["evidence"]

    rng = random.Random(seed)
    blocks: list[str] = []

    def emit(object_id: str, type_name: str, relations: list[tuple[str, str]]) -> None:
        lines = [f'::: {{.need #{object_id} type="{type_name}"}}']
        for name, target in relations:
            lines.append(f"{name}: {target}")
        lines.append(f"\n## {object_id}")
        lines.append("Synthetic benchmark object.")
        lines.append(":::")
        blocks.append("\n".join(lines))

    for index, object_id in enumerate(requirements):
        relations: list[tuple[str, str]] = []
        if index > 0:
            step = 1 + rng.randrange(min(5, index))
            relations.append(("derives-from", requirements[index - step]))
        relations.append(("implemented-by", components[index % len(components)]))
        relations.append(("verified-by", tests[index % len(tests)]))
        emit(object_id, "software-requirement", relations)

    for index, object_id in enumerate(tests):
        relations = [("evidences", evidence[index % len(evidence)])]
        emit(object_id, "test-case", relations)

    for index, object_id in enumerate(components):
        relations: list[tuple[str, str]] = [
            ("part-of", containers[index % len(containers)])
        ]
        emit(object_id, "component", relations)

    for index, object_id in enumerate(containers):
        emit(object_id, "container", [("part-of", systems[index % len(systems)])])

    for object_id in systems:
        emit(object_id, "system", [])

    for index, object_id in enumerate(decisions):
        targets = "; ".join(
            requirements[(index * 2 + offset) % len(requirements)]
            for offset in range(2)
        )
        emit(object_id, "architecture-decision", [("addresses", targets)])

    for object_id in evidence:
        emit(object_id, "evidence", [])

    relation_count = (
        max(0, len(requirements) - 1)
        + 2 * len(requirements)
        + len(tests)
        + len(components)
        + len(containers)
        + 2 * len(decisions)
    )
    return SyntheticModel(
        text="\n".join(blocks),
        requirement_ids=tuple(requirements),
        relation_count=relation_count,
    )


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("objects", type=int)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    model = generate_model_text(args.objects)
    if args.out is not None:
        args.out.write_text(model.text, encoding="utf-8")
        print(f"wrote {args.objects} objects to {args.out}")
    else:
        print(model.text)
