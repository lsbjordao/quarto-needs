from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from ..relations import DEFAULT_RELATION_CATALOG

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_ATTRIBUTE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Preamble keys the block grammar already consumes, keys the source marker
# owns, and relation names (a preamble key naming a relation declares one
# rather than an attribute). An extra with any of these names stays in the
# plan instead of being authored.
_RESERVED_EXTRA_NAMES = frozenset(
    {"id", "type", "status", "title", "tags", "rationale"}
    | {"source-tool", "source-project", "source-id"}
    | set(DEFAULT_RELATION_CATALOG.names)
)


def _unsafe_attribute_value(value: str) -> bool:
    return '"' in value or "}" in value


def source_tool_slug(tool: str) -> str:
    """The stable slug a migration source is authored and matched by."""
    return re.sub(r"[^a-z0-9]+", "-", tool.casefold()).strip("-")


def _marker_value_problem(label: str, value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"migration provenance {label} must be a non-empty string"
    if _unsafe_attribute_value(value) or "\n" in value or "\r" in value:
        return f"migration provenance {label} cannot be authored as a .need block attribute"
    return None


def source_marker_attributes(provenance: Mapping[str, object] | None) -> list[str]:
    """The authored source-identity marker for a migrated block.

    This is what lets a later run match a changed upstream item to the block
    it created, instead of treating the canonical ID as an implicit update.
    """
    if not provenance:
        return []
    attributes: list[str] = []
    tool = provenance.get("tool")
    if isinstance(tool, str) and tool.strip():
        attributes.append(f'source-tool="{source_tool_slug(tool)}"')
    project = provenance.get("project")
    if isinstance(project, str) and project.strip():
        attributes.append(f'source-project="{project.strip()}"')
    source_id = provenance.get("sourceId")
    if isinstance(source_id, str) and source_id.strip():
        attributes.append(f'source-id="{source_id.strip()}"')
    return attributes


def marker_problems(provenance: Mapping[str, object] | None) -> list[str]:
    """Whether a provenance mapping can be rendered as a source marker."""
    if not provenance:
        return []
    problems: list[str] = []
    tool = provenance.get("tool")
    if not isinstance(tool, str) or not source_tool_slug(tool):
        problems.append("migration provenance tool has no usable slug")
    else:
        problem = _marker_value_problem("tool", tool)
        if problem:
            problems.append(problem)
    project = provenance.get("project")
    if project is not None:
        problem = _marker_value_problem("project", project)
        if problem:
            problems.append(problem)
    source_id = provenance.get("sourceId")
    problem = _marker_value_problem("sourceId", source_id)
    if problem:
        problems.append(problem)
    return problems


def _authorable_value(value: object) -> str | None:
    """The authored text for one scalar extra value, or None if unrepresentable."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return repr(value)
    if isinstance(value, str):
        if not value.strip() or value != value.strip():
            return None
        if "\n" in value or "\r" in value:
            return None
        return value
    return None


def authorable_extras(
    extras: Mapping[str, object] | None,
) -> tuple[tuple[str, str], ...]:
    """Scalar extras the `.need` grammar can author, sorted by name.

    Lists, mappings, nulls, multi-line strings and values with surrounding
    whitespace cannot round-trip through the grammar; they stay in the plan's
    ``extras`` for review rather than being silently altered. Reserved names
    and relation names stay there too, because the grammar would consume them
    as something other than an attribute.
    """
    if not extras:
        return ()
    authored: list[tuple[str, str]] = []
    for name, value in sorted(extras.items()):
        if not isinstance(name, str) or not _ATTRIBUTE_NAME_RE.match(name):
            continue
        if name in _RESERVED_EXTRA_NAMES:
            continue
        text = _authorable_value(value)
        if text is None:
            continue
        authored.append((name, text))
    return tuple(authored)


def need_block_problems(
    *,
    canonical_id: str,
    target_type: str,
    target_status: str | None,
    title: str,
    body: str,
    tags: Sequence[str],
    relations: Sequence[Mapping[str, str]],
    provenance: Mapping[str, object] | None = None,
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

    problems.extend(marker_problems(provenance))

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
    provenance: Mapping[str, object] | None = None,
    extras: Mapping[str, object] | None = None,
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
    attrs.extend(source_marker_attributes(provenance))

    grouped: dict[str, list[str]] = {}
    for relation in relations:
        grouped.setdefault(relation["relation"], []).append(relation["target"])
    relation_lines = [
        f"{name}: {';'.join(targets)}" for name, targets in grouped.items()
    ]

    lines = [f"::: {{.need #{canonical_id} {' '.join(attrs)}}}"]
    lines.extend(f"{name}: {value}" for name, value in authorable_extras(extras))
    lines.extend(relation_lines)
    lines.append("")
    lines.append(f"## {title}")
    lines.append("")
    lines.append(body.strip("\n"))
    lines.append(":::")
    return "\n".join(lines) + "\n"
