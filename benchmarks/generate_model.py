"""Deterministic synthetic engineering model generator for benchmarks.

Produces a reproducible Quarto-Needs project text with a fixed seed and
positional, deterministic object IDs. The model mixes requirement,
test, architecture, and evidence objects with relations from several
semantic families (derivation, implementation, verification, evidence,
decomposition, decision-addressing), sized relative to the requested
object count.

Four additional corpus *shapes* stress the graph properties that change
algorithmic cost, per the Phase 8 roadmap: `sparse` (few relations),
`dense` (many), `cyclic` (derivation rings, so cycle detection cannot
terminate early), and `high-fanout` (hub objects concentrating in-degree).
The default `mixed` shape is byte-stable: the recorded benchmark baselines
were produced from it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

SEED = 20260902

SHAPES = ("mixed", "sparse", "dense", "cyclic", "high-fanout")

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
    shape: str = "mixed"


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


def generate_model_text(
    total: int, seed: int = SEED, shape: str = "mixed"
) -> SyntheticModel:
    """Generate one deterministic QMD buffer with *total* objects.

    *shape* selects the graph topology; see ``SHAPES``. Only the relations
    differ between shapes -- the object inventory is identical -- so a
    measured difference is attributable to graph structure alone.
    """
    if shape not in SHAPES:
        raise ValueError(f"unknown shape {shape!r}; expected one of {SHAPES}")

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
    emitted_relations = 0

    def emit(object_id: str, type_name: str, relations: list[tuple[str, str]]) -> None:
        nonlocal emitted_relations
        lines = [f'::: {{.need #{object_id} type="{type_name}"}}']
        for name, target in relations:
            lines.append(f"{name}: {target}")
            emitted_relations += len([t for t in target.split(";") if t.strip()])
        lines.append(f"\n## {object_id}")
        lines.append("Synthetic benchmark object.")
        lines.append(":::")
        blocks.append("\n".join(lines))

    def requirement_relations(index: int) -> list[tuple[str, str]]:
        """Per-shape relations for one requirement.

        The `mixed` branch reproduces the original generator exactly,
        including its `rng` draw order, so its bytes stay pinned.
        """
        if shape == "mixed":
            relations: list[tuple[str, str]] = []
            if index > 0:
                step = 1 + rng.randrange(min(5, index))
                relations.append(("derives-from", requirements[index - step]))
            relations.append(("implemented-by", components[index % len(components)]))
            relations.append(("verified-by", tests[index % len(tests)]))
            return relations

        if shape == "sparse":
            # A single derivation chain and nothing else: the lowest edge
            # count that still leaves the graph connected enough to traverse.
            return [] if index == 0 else [("derives-from", requirements[index - 1])]

        if shape == "dense":
            relations = [
                ("implemented-by", components[index % len(components)]),
                ("verified-by", tests[index % len(tests)]),
            ]
            if index > 0:
                relations.append(("derives-from", requirements[index - 1]))
            # Deterministic wide cross-linking: stride-based, not random, so
            # density does not depend on the rng draw order of other shapes.
            # One semicolon-separated line, not three `references:` lines --
            # a repeated relation key inside one block keeps only its last
            # value, which would silently collapse this to a third of the
            # intended density.
            targets = [
                requirements[(index + stride) % len(requirements)]
                for stride in (7, 13, 29)
            ]
            targets = [t for t in targets if t != requirements[index]]
            if targets:
                relations.append(("references", "; ".join(targets)))
            relations.append(("refines", requirements[(index * 3 + 1) % len(requirements)]))
            return relations

        if shape == "cyclic":
            # Rings of RING_SIZE requirements, each deriving from the next and
            # the last closing back onto the first. Cycle detection cannot
            # terminate early and every ring must be canonicalized.
            ring_size = min(8, len(requirements))
            position = index % ring_size
            base = index - position
            successor = base + (position + 1) % ring_size
            if successor >= len(requirements):
                successor = base
            relations = [("derives-from", requirements[successor])]
            relations.append(("verified-by", tests[index % len(tests)]))
            return relations

        # high-fanout: every requirement points at the same hub component and
        # hub test, so two nodes carry almost the whole in-degree.
        relations = [
            ("implemented-by", components[0]),
            ("verified-by", tests[0]),
        ]
        if index > 0:
            relations.append(("derives-from", requirements[0]))
        return relations

    for index, object_id in enumerate(requirements):
        emit(object_id, "software-requirement", requirement_relations(index))

    for index, object_id in enumerate(tests):
        if shape == "sparse":
            emit(object_id, "test-case", [])
            continue
        target = evidence[0] if shape == "high-fanout" else evidence[index % len(evidence)]
        emit(object_id, "test-case", [("evidences", target)])

    for index, object_id in enumerate(components):
        if shape == "sparse":
            emit(object_id, "component", [])
            continue
        target = containers[0] if shape == "high-fanout" else containers[index % len(containers)]
        emit(object_id, "component", [("part-of", target)])

    for index, object_id in enumerate(containers):
        if shape == "sparse":
            emit(object_id, "container", [])
            continue
        target = systems[0] if shape == "high-fanout" else systems[index % len(systems)]
        emit(object_id, "container", [("part-of", target)])

    for object_id in systems:
        emit(object_id, "system", [])

    for index, object_id in enumerate(decisions):
        if shape == "sparse":
            emit(object_id, "architecture-decision", [])
            continue
        if shape == "high-fanout":
            emit(object_id, "architecture-decision", [("addresses", requirements[0])])
            continue
        targets = "; ".join(
            requirements[(index * 2 + offset) % len(requirements)]
            for offset in range(2)
        )
        emit(object_id, "architecture-decision", [("addresses", targets)])

    for object_id in evidence:
        emit(object_id, "evidence", [])

    return SyntheticModel(
        text="\n".join(blocks),
        requirement_ids=tuple(requirements),
        relation_count=emitted_relations,
        shape=shape,
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
