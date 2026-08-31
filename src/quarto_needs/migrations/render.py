from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _unsafe_attribute_value(value: str) -> bool:
    return '"' in value or "}" in value


def need_block_problems(
    *,
    canonical_id: str,
    target_type: str,
    target_status: str | None,
    title: str,
    body: str,
    tags: Sequence[str],
    relations: Sequence[Mapping[str, str]],
) -> list[str]:
    """Detect content that cannot be represented in the authored .need grammar.

    The grammar (``parser.py``) has no escape mechanism: a double quote or
    ``}`` inside an attribute value corrupts the attribute list, a tag
    containing ``;`` is indistinguishable from two tags, and any body line
    that is exactly ``:::`` closes the block early. Rather than silently
    producing text that fails to round-trip, every such case is reported so
    the apply plan can refuse to mark the item ready-create.
    """
    problems: list[str] = []

    if not _ID_RE.match(canonical_id):
        problems.append(
            f"canonical ID {canonical_id!r} cannot be authored as a .need block id "
            "(allowed characters: letters, digits, '_', '.', ':', '-')"
        )

    if _unsafe_attribute_value(target_type):
        problems.append(
            f"target type {target_type!r} cannot be authored as a .need block attribute"
        )

    if target_status is not None and _unsafe_attribute_value(target_status):
        problems.append(
            f"target status {target_status!r} cannot be authored as a .need block attribute"
        )

    for tag in tags:
        if _unsafe_attribute_value(tag) or ";" in tag:
            problems.append(
                f"tag {tag!r} cannot be represented in a .need block tags attribute"
            )

    if "\n" in title:
        problems.append(
            "title contains a newline and cannot be authored as a single heading line"
        )

    if any(line.strip() == ":::" for line in body.splitlines()):
        problems.append(
            "source content contains a line that is exactly ':::', "
            "which would prematurely close the rendered .need block"
        )

    for relation in relations:
        target = relation["target"]
        if not _ID_RE.match(target):
            problems.append(
                f"relation target {target!r} cannot be authored as a .need block id"
            )

    return problems


def render_need_block(
    *,
    canonical_id: str,
    target_type: str,
    target_status: str | None,
    title: str,
    body: str,
    tags: Sequence[str],
    relations: Sequence[Mapping[str, str]],
) -> str:
    """Render a candidate as authored ``.need`` block text.

    Callers must first confirm ``need_block_problems(...)`` is empty; this
    function performs no escaping and assumes every value is already safe
    for the grammar's fence/attribute/heading syntax.
    """
    attrs = [f"type=\"{target_type}\""]
    if target_status is not None:
        attrs.append(f'status="{target_status}"')
    if tags:
        attrs.append('tags="' + ";".join(tags) + '"')

    grouped: dict[str, list[str]] = {}
    for relation in relations:
        grouped.setdefault(relation["relation"], []).append(relation["target"])
    relation_lines = [
        f"{name}: {';'.join(targets)}" for name, targets in grouped.items()
    ]

    lines = [f"::: {{.need #{canonical_id} {' '.join(attrs)}}}"]
    lines.extend(relation_lines)
    lines.append("")
    lines.append(f"## {title}")
    lines.append("")
    lines.append(body.strip("\n"))
    lines.append(":::")
    return "\n".join(lines) + "\n"
