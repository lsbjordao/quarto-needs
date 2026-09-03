"""OpenFastTrace migration source.

Reads OpenFastTrace specobjects from their Markdown authoring format and
projects them into the shared migration-plan contract, exactly as the
Doorstop and StrictDoc adapters do: a deterministic plan, explicit review
items for everything the mapping cannot express, and no execution of the
source tool.

Specobject syntax (from OpenFastTrace's own user guide): a Markdown
heading followed by a backticked identifier line
``doctype~title-slug~revision``; keyword passages (``Status:``,
``Description:``, ``Rationale:``, ``Comment:``) and keyword lists
(``Covers:``, ``Depends:``) whose entries start with ``+``, ``*`` or
``-``, with one-liner variants (``Covers: id``) accepted as well.

Only catalog names become relations in Quarto-Needs, and OpenFastTrace's
"covers" has no single canonical equivalent — a test covering a
requirement and a feature covering a design want different edges. So, as
in every adapter here, ``relation_map`` is explicit and keyed by the
OpenFastTrace keyword (``covers``, ``depends``); an unmapped keyword's
links are preserved as data and reported for review, never guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .sphinx_needs import (
    MigratedRelation,
    MigrationIssue,
    SphinxNeedCandidate,
    SphinxNeedsMigrationPlan,
)

_ID_LINE_RE = re.compile(r"^`([^`\s]+)~([^`\s]+)~([^`\s]+)`\s*$")
_KEYWORD_RE = re.compile(r"^(Status|Description|Rationale|Comment|Covers|Depends|Needs):(.*)$")
_BULLET_RE = re.compile(r"^[+*-]\s+(.+?)\s*$")
_STATUS_KEYWORD = "status"

_CONSUMED_KEYWORDS = {"status", "description", "rationale", "comment", "covers", "depends", "needs"}
_LIST_KEYWORDS = {"covers", "depends"}


class OpenFastTraceMigrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Specobject:
    id: str
    doctype: str
    revision: str
    title: str
    description: str
    rationale: str
    status: str | None
    covers: tuple[str, ...]
    depends: tuple[str, ...]
    extras: Mapping[str, object]
    path: Path


def _keyword_passages(lines: Sequence[str]) -> dict[str, object]:
    """One specobject's keyword table: scalar keywords and bullet lists.

    OpenFastTrace's description is implicit: any non-empty line that does
    not start with another keyword is description text, whether it sits
    under an explicit ``Description:`` or simply follows the identifier.
    ``Rationale:`` and ``Comment:`` start their own passages, ending at the
    next keyword, heading, identifier, or end of block; ``Covers`` /
    ``Depends`` / ``Needs`` take bullet lists (``+``, ``*``, ``-``) or
    one-liner values.
    """
    fields: dict[str, object] = {}
    description: list[str] = []
    current: str | None = None
    current_items: list[str] = []
    current_text: list[str] = []

    def close() -> None:
        nonlocal current, current_items, current_text
        if current is None:
            return
        if current_items:
            if current_text:
                raise OpenFastTraceMigrationError(
                    f"OpenFastTrace keyword {current!r} mixes a one-liner with a list"
                )
            fields[current] = tuple(current_items)
        elif current_text:
            fields[current] = "\n".join(current_text).strip()
        elif current != "description":
            fields[current] = None
        current = None
        current_items = []
        current_text = []

    for line in lines:
        keyword = _KEYWORD_RE.match(line)
        boundary = keyword or line.lstrip().startswith("#") or _ID_LINE_RE.match(
            line.strip()
        )
        if boundary:
            close()
        if keyword:
            name = keyword.group(1).lower()
            inline = keyword.group(2).strip()
            if name in _LIST_KEYWORDS and inline:
                fields[name] = (inline,)
                continue
            if name == "description":
                if inline:
                    description.append(inline)
                continue
            current = name
            if inline:
                current_text.append(inline)
                close()
            continue
        stripped = line.strip()
        bullet = _BULLET_RE.match(stripped)
        if current in _LIST_KEYWORDS and bullet:
            current_items.append(bullet.group(1))
        elif current is not None:
            current_text.append(line)
        elif stripped:
            description.append(line)

    close()
    if description:
        fields["description"] = "\n".join(description).strip()
    return fields


def _parse_block(path: Path, heading: str, id_line: str, body: Sequence[str]) -> Specobject:
    match = _ID_LINE_RE.match(id_line.strip())
    assert match is not None
    doctype, slug, revision = match.group(1), match.group(2), match.group(3)
    fields = _keyword_passages(list(body))

    status = fields.get(_STATUS_KEYWORD)
    if status is not None and not isinstance(status, str):
        raise OpenFastTraceMigrationError(
            f"OpenFastTrace item {id_line} in {path} has a list-valued Status"
        )
    description = fields.get("description")
    if description is not None and not isinstance(description, str):
        raise OpenFastTraceMigrationError(
            f"OpenFastTrace item {id_line} in {path} has a list-valued Description"
        )
    rationale = fields.get("rationale")
    rationale = rationale if isinstance(rationale, str) else ""
    comment = fields.get("comment")
    comment = comment if isinstance(comment, str) else None

    def targets(keyword: str) -> tuple[str, ...]:
        value = fields.get(keyword, ())
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        return tuple(value)

    extras: dict[str, object] = {}
    if comment:
        extras["comment"] = comment
    needs = fields.get("needs")
    if needs is not None:
        extras["needs"] = needs
    extras["revision"] = revision

    return Specobject(
        id=id_line.strip().strip("`"),
        doctype=doctype,
        revision=revision,
        title=heading.strip(),
        description=description if isinstance(description, str) else "",
        rationale=rationale,
        status=status.strip().casefold() if isinstance(status, str) and status.strip() else None,
        covers=targets("covers"),
        depends=targets("depends"),
        extras=dict(sorted(extras.items())),
        path=path,
    )


def _split_blocks(text: str) -> list[tuple[str, str, list[str]]]:
    """Markdown text → (heading, identifier line, body lines) triples."""
    blocks: list[tuple[str, str, list[str]]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("#"):
            heading = line.lstrip("#").strip()
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            if index < len(lines) and _ID_LINE_RE.match(lines[index].strip()):
                id_line = lines[index].strip()
                index += 1
                body: list[str] = []
                while index < len(lines):
                    if lines[index].lstrip().startswith("#") or _ID_LINE_RE.match(
                        lines[index].strip()
                    ):
                        break
                    body.append(lines[index])
                    index += 1
                blocks.append((heading, id_line, body))
                continue
            continue
        index += 1
    return blocks


def load_specobjects(root: Path) -> tuple[Specobject, ...]:
    """Load every ``.md`` file under *root* as OpenFastTrace specobjects.

    Only heading-plus-identifier blocks are items; other Markdown prose is
    structural presentation. This reads only the on-disk text; it never
    executes OpenFastTrace.
    """
    if root.is_file():
        files: tuple[Path, ...] = (root,)
    else:
        files = tuple(sorted(root.rglob("*.md")))
    items: list[Specobject] = []
    seen: dict[str, Path] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise OpenFastTraceMigrationError(
                f"cannot read OpenFastTrace Markdown {path}: {error}"
            ) from error
        for heading, id_line, body in _split_blocks(text):
            item = _parse_block(path, heading, id_line, body)
            if item.id in seen:
                raise OpenFastTraceMigrationError(
                    f"OpenFastTrace item {item.id} is defined in both "
                    f"{seen[item.id]} and {path}"
                )
            seen[item.id] = path
            items.append(item)
    return tuple(items)


def build_migration_plan(
    items: Sequence[Specobject],
    *,
    type_map: Mapping[str, str] | None = None,
    relation_map: Mapping[str, str] | None = None,
) -> SphinxNeedsMigrationPlan:
    """Build a conservative migration plan from loaded specobjects.

    ``type_map`` is keyed by OpenFastTrace doctype; ``relation_map`` by the
    OpenFastTrace keyword (``covers``, ``depends``). OpenFastTrace's
    "covers" deliberately has no automatic canonical equivalent: a test
    covering a requirement and a feature covering a design want different
    Quarto-Needs edges, so the caller chooses and an unmapped keyword stays
    an explicit review item.
    """
    types = dict(type_map or {})
    relations = dict(relation_map or {})

    candidates: list[SphinxNeedCandidate] = []
    issues: list[MigrationIssue] = []
    all_ids = {item.id for item in items}

    for item in sorted(items, key=lambda entry: (entry.id.casefold(), entry.id)):
        target_type = types.get(item.doctype)
        if target_type is None:
            issues.append(
                MigrationIssue(
                    code="TYPE_UNMAPPED",
                    message=(
                        f"OpenFastTrace doctype {item.doctype!r} has no explicit "
                        "Quarto-Needs type mapping"
                    ),
                    need_id=item.id,
                    field=item.doctype,
                )
            )

        content = item.description
        if item.rationale:
            content = (
                f"{content}\n\n### Rationale\n\n{item.rationale}"
                if content
                else f"### Rationale\n\n{item.rationale}"
            )

        migrated_relations: list[MigratedRelation] = []
        unmapped: dict[str, tuple[str, ...]] = {}
        for keyword, targets in (("covers", item.covers), ("depends", item.depends)):
            canonical_relation = relations.get(keyword)
            unmapped_targets: list[str] = []
            for target in targets:
                if canonical_relation is None:
                    unmapped_targets.append(target)
                    continue
                if target not in all_ids:
                    issues.append(
                        MigrationIssue(
                            code="EXTERNAL_LINK_TARGET",
                            message=(
                                f"OpenFastTrace item {item.id} {keyword} {target!r}, "
                                "which is not defined in the loaded items"
                            ),
                            need_id=item.id,
                            field=target,
                        )
                    )
                    continue
                migrated_relations.append(
                    MigratedRelation(
                        source=item.id,
                        relation=canonical_relation,
                        target=target,
                        source_field=keyword,
                    )
                )
            if unmapped_targets:
                unmapped[keyword] = tuple(unmapped_targets)
                issues.append(
                    MigrationIssue(
                        code="RELATION_UNMAPPED",
                        message=(
                            f"OpenFastTrace keyword {keyword!r} on {item.id} has no "
                            "explicit Quarto-Needs relation mapping"
                        ),
                        need_id=item.id,
                        field=keyword,
                    )
                )

        candidates.append(
            SphinxNeedCandidate(
                source_id=item.id,
                source_type=item.doctype,
                target_type=target_type,
                title=item.title if item.title else item.id,
                content=content,
                status=item.status,
                tags=(),
                relations=tuple(
                    sorted(
                        migrated_relations,
                        key=lambda relation: (relation.relation, relation.target),
                    )
                ),
                unmapped_links=unmapped,
                extras=dict(item.extras),
            )
        )

    return SphinxNeedsMigrationPlan(
        source_project=None,
        source_version="n/a",
        candidates=tuple(candidates),
        issues=tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.need_id or "",
                    issue.code,
                    issue.field or "",
                    issue.message,
                ),
            )
        ),
        tool="OpenFastTrace",
        schema="openfasttrace-migration-plan-v1",
    )
