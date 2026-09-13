from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING

from .diagnostics import Finding
from .relations import DEFAULT_RELATION_CATALOG, RelationCatalog
from .snapshot import ObjectDeclaration

if TYPE_CHECKING:
    from .model import EngineeringObject


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

DEFAULT_RATIONALE_TYPES = frozenset(
    {"system-requirement", "software-requirement"}
)
VERIFICATION_RELATION_NAMES = frozenset({"verified-by", "validated-by"})


def finding_key(item: Finding) -> tuple[object, ...]:
    location = item.location
    return (
        SEVERITY_ORDER.get(item.severity, 99),
        item.code,
        (item.object_id or "").casefold(),
        item.object_id or "",
        location.file.casefold() if location else "",
        location.file if location else "",
        location.line if location else 0,
        item.message,
    )


def _one_edit_apart(left: str, right: str) -> bool:
    """Return whether two names differ by exactly one conservative typo edit.

    The accepted edits are one insertion, deletion, substitution, or adjacent
    transposition. This deliberately stops at one edit: project-specific
    attributes remain an open namespace, so a fuzzy matcher must not turn every
    relation-looking attribute into a warning.
    """
    if left == right or abs(len(left) - len(right)) > 1:
        return False

    if len(left) == len(right):
        mismatches = [
            index
            for index, (left_char, right_char) in enumerate(zip(left, right))
            if left_char != right_char
        ]
        if len(mismatches) == 1:
            return True
        if len(mismatches) != 2:
            return False
        first, second = mismatches
        return (
            second == first + 1
            and left[first] == right[second]
            and left[second] == right[first]
        )

    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    short_index = 0
    long_index = 0
    skipped = False
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue
        if skipped:
            return False
        skipped = True
        long_index += 1
    return True


def probable_relation_names(
    attribute_name: str,
    relation_catalog: RelationCatalog = DEFAULT_RELATION_CATALOG,
) -> tuple[str, ...]:
    """Return catalog relations one typo edit away from an attribute name.

    Unknown `.need` keys are valid custom attributes, so this helper never
    reinterprets them. It only supports an advisory diagnostic at validation
    time; the original key/value remains authored data and no graph edge is
    created automatically.
    """
    return tuple(
        name
        for name in relation_catalog.names
        if _one_edit_apart(attribute_name, name)
    )


def resolved_v1_name(
    token_authored_name: str,
    relation_catalog: RelationCatalog,
) -> str:
    """Resolve one authored relation name, falling back to the authored name.

    This is the single place where pre-snapshot validation decides whether a
    relation name is supported; the fallback value only ever reaches
    diagnostics, because an unresolved name also raises the structural
    REQ007 finding that blocks snapshot construction.
    """
    try:
        return relation_catalog.resolve(token_authored_name).v1_name
    except ValueError:
        return token_authored_name


def validate_declarations(
    declarations: Iterable[ObjectDeclaration],
    relation_catalog: RelationCatalog = DEFAULT_RELATION_CATALOG,
    require_rationale_for: set[str] | None = None,
) -> tuple[Finding, ...]:
    """Validate canonical declarations before any snapshot exists.

    This is the canonical pre-snapshot validation surface; it operates on
    ``ObjectDeclaration`` and the relation catalog and never constructs
    legacy DTOs. It produces the historical diagnostic set plus the
    conservative relation-name typo advisory:

    * ``REQ004`` duplicate ID (error, blocks snapshot construction);
    * ``REQ005`` unknown relation target (error, blocks snapshot
      construction);
    * ``REQ007`` unsupported relation name (error, blocks snapshot
      construction);
    * ``REQ002`` missing rationale (warning);
    * ``REQ006`` approved requirement without a verification relation
      (warning);
    * ``QND005`` unknown attribute one typo edit from a catalog relation
      (warning; the attribute is preserved and no relation is invented).

    REQ002/REQ006 and QND005 are object-local checks that need no resolved
    graph. They deliberately stay in this pre-snapshot pass (instead of the
    post-snapshot rules engine) because structurally blocked projects produce
    no snapshot, and their findings tuple is the only diagnostic surface such
    a project has; characterization tests pin that these warnings remain
    observable there.
    """
    rationale_types = (
        DEFAULT_RATIONALE_TYPES
        if require_rationale_for is None
        else frozenset(require_rationale_for)
    )
    declarations = tuple(declarations)
    findings: list[Finding] = []
    counts = Counter(declaration.id for declaration in declarations)
    known_ids = set(counts)
    for need_id, count in counts.items():
        if count > 1:
            location = next(
                declaration.location
                for declaration in declarations
                if declaration.id == need_id
            )
            findings.append(Finding(
                "REQ004",
                "error",
                f"Duplicate ID: {need_id}",
                need_id,
                location,
            ))

    for declaration in declarations:
        for attribute_name in declaration.attributes:
            suggestions = probable_relation_names(attribute_name, relation_catalog)
            if not suggestions:
                continue
            if len(suggestions) == 1:
                suggested = f"relation {suggestions[0]!r}"
                replacement = suggestions[0]
            else:
                suggested = "relations " + ", ".join(
                    repr(name) for name in suggestions
                )
                replacement = suggestions[0]
            findings.append(Finding(
                "QND005",
                "warning",
                f"Attribute {attribute_name!r} on {declaration.id} resembles "
                f"catalog {suggested}. It remains an ordinary attribute and "
                "creates no graph edge; use "
                f"{replacement!r} if a relation was intended.",
                declaration.id,
                declaration.location,
            ))

        for token in declaration.relations:
            try:
                v1_name = relation_catalog.resolve(token.authored_name).v1_name
            except ValueError:
                v1_name = token.authored_name
                findings.append(Finding(
                    "REQ007",
                    "error",
                    "Unsupported relation type "
                    f"{token.authored_name} on {declaration.id}",
                    declaration.id,
                    token.location or declaration.location,
                ))
            if token.target not in known_ids:
                findings.append(Finding(
                    "REQ005",
                    "error",
                    f"{declaration.id} references unknown object "
                    f"{token.target} via {v1_name}",
                    declaration.id,
                    declaration.location,
                ))
        if (
            declaration.type in rationale_types
            and not declaration.rationale
            and "### Rationale" not in declaration.body
        ):
            findings.append(Finding(
                "REQ002",
                "warning",
                f"{declaration.id} has no rationale",
                declaration.id,
            ))
        if declaration.status == "approved" and declaration.type.endswith(
            "requirement"
        ):
            has_verification = any(
                resolved_v1_name(token.authored_name, relation_catalog)
                in VERIFICATION_RELATION_NAMES
                for token in declaration.relations
            )
            if not has_verification:
                findings.append(Finding(
                    "REQ006",
                    "warning",
                    f"{declaration.id} is approved but has no verification relation",
                    declaration.id,
                ))
    return tuple(sorted(findings, key=finding_key))


def validate(
    objects: list[EngineeringObject],
    require_rationale_for: set[str] | None = None,
) -> list[Finding]:
    """Legacy compatibility entry point.

    Adapts ``EngineeringObject`` inputs into canonical declarations and
    defers to :func:`validate_declarations`. The canonical analyzer no
    longer routes through this function; it remains for external callers
    and tests that construct legacy objects directly.

    Two deliberate differences from the pre-stabilization implementation
    remain for direct callers:

    * relation names are resolved through the relation catalog, so an
      unsupported name now also raises the structural ``REQ007`` finding
      this function previously never produced, and the ``REQ005`` message
      names the resolved v1 relation (``derived-from`` reports as
      ``derives-from``);
    * an explicitly passed ``require_rationale_for`` still honors the
      historical falsy-falls-back-to-default behavior, so an empty set
      selects the default governed types instead of disabling ``REQ002``.
    """
    from .model import to_declaration

    return list(
        validate_declarations(
            (to_declaration(item) for item in objects),
            require_rationale_for=(
                require_rationale_for or None
            ),
        )
    )