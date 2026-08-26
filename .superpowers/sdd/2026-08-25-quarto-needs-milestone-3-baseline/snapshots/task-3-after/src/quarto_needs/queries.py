from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
from typing import Any, Mapping

from .config import ConfigurationError
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord


class QueryError(ConfigurationError):
    """Raised when a named query violates the safe-query grammar or limits."""


DEFAULT_QUERY_NAME = "approved-requirements"

MAX_DEPTH = 10
MAX_CLAUSES = 100

BASE_FIELDS = ("id", "title", "type", "status", "priority", "tags")

FIELD_OPERATIONS = ("eq", "in", "contains", "exists", "missing")
RELATION_OPERATIONS = ("exists", "missing")
DIRECTIONS = ("out", "in", "either")

PRIORITY_RANK = {"critical": 1, "high": 2, "medium": 3, "low": 4}

DEFAULT_QUERY_SOURCE: Mapping[str, object] = {
    "all": [
        {"field": "type", "op": "contains", "value": "requirement"},
        {"field": "status", "op": "eq", "value": "approved"},
    ],
    "sort": ["priority:asc", "id:asc"],
}


@dataclass(frozen=True, slots=True)
class FieldClause:
    field: str
    op: str
    value: Any = None
    values: tuple[Any, ...] = ()
    has_value: bool = False
    has_values: bool = False


@dataclass(frozen=True, slots=True)
class RelationClause:
    relation: str
    direction: str
    op: str


@dataclass(frozen=True, slots=True)
class AllClause:
    children: tuple["Clause", ...]


@dataclass(frozen=True, slots=True)
class AnyClause:
    children: tuple["Clause", ...]


@dataclass(frozen=True, slots=True)
class NotClause:
    child: "Clause"


Clause = FieldClause | RelationClause | AllClause | AnyClause | NotClause


@dataclass(frozen=True, slots=True)
class Query:
    name: str
    root: Clause
    sort: tuple[tuple[str, str], ...]


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _scalar_eq(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return False


def _validate_field(field: object) -> str:
    if not isinstance(field, str) or not field:
        raise QueryError("query fields must be non-empty strings")
    if field in BASE_FIELDS:
        return field
    if field.startswith("attributes.") and len(field) > len("attributes."):
        return field
    raise QueryError(
        f"unknown query field: {field} "
        f"(allowed: {', '.join(BASE_FIELDS)}, attributes.<name>)"
    )


def _compile_field_clause(raw: Mapping[str, object]) -> FieldClause:
    unknown = set(raw) - {"field", "op", "value", "values"}
    if unknown:
        raise QueryError(
            f"field clause has unknown keys: {', '.join(sorted(unknown))}"
        )
    field = _validate_field(raw.get("field"))
    operation = raw.get("op")
    if not isinstance(operation, str) or operation not in FIELD_OPERATIONS:
        raise QueryError(
            f"unsupported operator for field {field}: {operation!r} "
            f"(allowed: {', '.join(FIELD_OPERATIONS)})"
        )
    has_value = "value" in raw
    has_values = "values" in raw
    if operation in {"exists", "missing"} and (has_value or has_values):
        raise QueryError(f"{operation} clauses take no comparison value")
    if operation == "eq":
        if not has_value:
            raise QueryError(f"eq clause on {field} requires a value")
    if operation == "contains":
        if not has_value or not _is_scalar(raw.get("value")):
            raise QueryError(f"contains clause on {field} requires a scalar value")
    if operation == "in":
        values = raw.get("values") if has_values else ()
        if (
            not has_values
            or not isinstance(values, list)
            or not values
            or not all(_is_scalar(item) for item in values)
        ):
            raise QueryError(f"in clause on {field} requires a non-empty values array")
        return FieldClause(field, operation, values=tuple(values), has_values=True)
    return FieldClause(field, operation, value=raw.get("value"), has_value=has_value)


def _compile_relation_clause(raw: Mapping[str, object]) -> RelationClause:
    unknown = set(raw) - {"relation", "direction", "op"}
    if unknown:
        raise QueryError(
            f"relation clause has unknown keys: {', '.join(sorted(unknown))}"
        )
    name = raw.get("relation")
    if not isinstance(name, str) or not name:
        raise QueryError("relation clauses require a relation name")
    try:
        resolved = DEFAULT_RELATION_CATALOG.resolve(name)
    except ValueError as error:
        raise QueryError(str(error)) from error
    direction = raw.get("direction")
    if not isinstance(direction, str) or direction not in DIRECTIONS:
        raise QueryError(
            f"relation clause on {resolved.v1_name} requires direction "
            f"one of: {', '.join(DIRECTIONS)}"
        )
    operation = raw.get("op")
    if not isinstance(operation, str) or operation not in RELATION_OPERATIONS:
        raise QueryError(
            f"unsupported operator for relation {resolved.v1_name}: {operation!r} "
            f"(allowed: {', '.join(RELATION_OPERATIONS)})"
        )
    return RelationClause(resolved.v1_name, direction, operation)


def _compile_clause(
    raw: object,
    depth: int,
    counter: list[int],
) -> Clause:
    counter[0] += 1
    if counter[0] > MAX_CLAUSES:
        raise QueryError(f"a query may contain at most {MAX_CLAUSES} clauses")
    if not isinstance(raw, Mapping):
        raise QueryError("every query clause must be a table")
    combinator = next((key for key in ("all", "any", "not") if key in raw), None)
    if combinator is not None:
        if depth >= MAX_DEPTH:
            raise QueryError(f"a query may nest at most {MAX_DEPTH} levels of depth")
        if combinator == "not":
            child = _compile_clause(raw["not"], depth + 1, counter)
            extra = set(raw) - {"not"}
            if extra:
                raise QueryError(
                    f"not clause cannot be combined with: {', '.join(sorted(extra))}"
                )
            return NotClause(child)
        children_raw = raw[combinator]
        if not isinstance(children_raw, list) or not children_raw:
            raise QueryError(f"{combinator} requires a non-empty array of clauses")
        extra = set(raw) - {combinator}
        if extra:
            raise QueryError(
                f"{combinator} cannot be combined with: {', '.join(sorted(extra))}"
            )
        children = tuple(
            _compile_clause(child, depth + 1, counter) for child in children_raw
        )
        return AllClause(children) if combinator == "all" else AnyClause(children)
    if "field" in raw:
        return _compile_field_clause(raw)
    if "relation" in raw:
        return _compile_relation_clause(raw)
    raise QueryError(
        "a clause must declare field/relation or combine clauses with all/any/not"
    )


def _parse_sort(raw_sort: object) -> tuple[tuple[str, str], ...]:
    if raw_sort is None:
        return ()
    if not isinstance(raw_sort, list):
        raise QueryError("sort must be an array of field tokens")
    parsed: list[tuple[str, str]] = []
    for token in raw_sort:
        if not isinstance(token, str):
            raise QueryError("sort tokens must be strings")
        field, _, direction = token.partition(":")
        direction = direction or "asc"
        if direction not in {"asc", "desc"}:
            raise QueryError(f"invalid sort direction in {token!r}: {direction}")
        _validate_field(field.strip() or field)
        parsed.append((field.strip(), direction))
    return tuple(parsed)


def compile_query(name: str, raw: Mapping[str, object]) -> Query:
    if not isinstance(raw, Mapping):
        raise QueryError(f"query {name} must be a table")
    combinator = next((key for key in ("all", "any", "not") if key in raw), None)
    if combinator is None:
        raise QueryError(
            f"query {name} must combine clauses with all, any, or not at the top level"
        )
    counter = [0]
    root = _compile_clause({combinator: raw[combinator]}, 1, counter)
    unknown = set(raw) - {combinator, "sort"}
    if unknown:
        raise QueryError(
            f"query {name} has unknown keys: {', '.join(sorted(unknown))}"
        )
    return Query(name=name, root=root, sort=_parse_sort(raw.get("sort")))


# --- evaluation --------------------------------------------------------------


def _field_is_present(record: ObjectRecord, field: str) -> tuple[bool, object]:
    if field == "id":
        return True, record.id
    if field == "title":
        return True, record.title
    if field == "type":
        return True, record.type
    if field == "status":
        return True, record.status
    if field == "tags":
        return True, record.tags
    if field == "priority":
        raw = record.attributes.get("priority")
        return raw is not None, raw
    name = field[len("attributes."):]
    if name in record.attributes:
        return True, record.attributes[name]
    return False, None


def _matches_field(record: ObjectRecord, clause: FieldClause) -> bool:
    present, value = _field_is_present(record, clause.field)
    if clause.op == "missing":
        return not present
    if clause.op == "exists":
        return present
    if not present:
        return False
    if clause.op == "eq":
        return _scalar_eq(value, clause.value)
    if clause.op == "in":
        return any(_scalar_eq(value, candidate) for candidate in clause.values)
    if clause.op == "contains":
        if isinstance(value, (tuple, list)):
            return any(_scalar_eq(item, clause.value) for item in value)
        if isinstance(value, str) and isinstance(clause.value, str):
            return clause.value.casefold() in value.casefold()
        return False
    return False


def _inverse_relations() -> Mapping[str, str]:
    labels: dict[str, tuple[str, str]] = {}
    for kind in DEFAULT_RELATION_CATALOG.entries.values():
        labels.setdefault(kind.v1_name, (kind.direct_label, kind.inverse_label))
    inverse: dict[str, str] = {}
    for left in labels:
        for right in labels:
            if (
                labels[left][0] == labels[right][1]
                and labels[left][1] == labels[right][0]
            ):
                inverse[left] = right
    return inverse


_INVERSE_RELATIONS: Mapping[str, str] = _inverse_relations()


def _has_relation_view(
    snapshot: AnalysisSnapshot,
    object_id: str,
    relation: str,
    direction: str,
) -> bool:
    inverse = _INVERSE_RELATIONS.get(relation)
    outgoing = snapshot.outgoing.get(object_id, ())
    incoming = snapshot.incoming.get(object_id, ())
    if direction in {"out", "either"}:
        if any(item.v1_name == relation for item in outgoing):
            return True
        if inverse is not None and any(
            item.v1_name == inverse for item in incoming
        ):
            return True
    if direction in {"in", "either"}:
        if any(item.v1_name == relation for item in incoming):
            return True
        if inverse is not None and any(
            item.v1_name == inverse for item in outgoing
        ):
            return True
    return False


def _matches(snapshot: AnalysisSnapshot, record: ObjectRecord, clause: Clause) -> bool:
    if isinstance(clause, AllClause):
        return all(_matches(snapshot, record, child) for child in clause.children)
    if isinstance(clause, AnyClause):
        return any(_matches(snapshot, record, child) for child in clause.children)
    if isinstance(clause, NotClause):
        return not _matches(snapshot, record, clause.child)
    if isinstance(clause, FieldClause):
        return _matches_field(record, clause)
    if isinstance(clause, RelationClause):
        found = _has_relation_view(snapshot, record.id, clause.relation, clause.direction)
        return found if clause.op == "exists" else not found
    raise QueryError(f"unsupported clause: {type(clause).__name__}")


def _sort_value(record: ObjectRecord, field: str) -> object:
    if field == "priority":
        raw = record.attributes.get("priority")
        rank = PRIORITY_RANK.get(str(raw).casefold()) if raw is not None else None
        return rank if rank is not None else len(PRIORITY_RANK) + 1
    present, value = _field_is_present(record, field)
    if not present or value is None:
        return ""
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value).casefold()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return value
    return str(value).casefold()


def _ordered(records: list[ObjectRecord], query: Query) -> tuple[ObjectRecord, ...]:
    keys = query.sort

    def compare(left: ObjectRecord, right: ObjectRecord) -> int:
        for field, direction in keys:
            left_value = _sort_value(left, field)
            right_value = _sort_value(right, field)
            if left_value == right_value:
                continue
            less = (
                left_value < right_value
                if isinstance(left_value, str) and isinstance(right_value, str)
                or isinstance(left_value, int) and isinstance(right_value, int)
                else str(left_value) < str(right_value)
            )
            result = -1 if less else 1
            return -result if direction == "desc" else result
        left_id, right_id = left.id.casefold(), right.id.casefold()
        if left_id != right_id:
            return -1 if left_id < right_id else 1
        return -1 if left.id < right.id else (1 if left.id > right.id else 0)

    return tuple(sorted(records, key=cmp_to_key(compare)))


def evaluate(query: Query, snapshot: AnalysisSnapshot) -> tuple[ObjectRecord, ...]:
    matched = [
        record for record in snapshot.objects if _matches(snapshot, record, query.root)
    ]
    return _ordered(matched, query)


def materialize_queries(
    config: object,
    snapshot: AnalysisSnapshot,
) -> Mapping[str, tuple[str, ...]]:
    sources: Mapping[str, object] = getattr(config, "named_query_sources", {}) or {}
    compiled: dict[str, Query] = {
        DEFAULT_QUERY_NAME: compile_query(DEFAULT_QUERY_NAME, dict(DEFAULT_QUERY_SOURCE))
    }
    for name, raw in sources.items():
        if not isinstance(name, str) or not name.strip():
            raise QueryError("query names must be non-empty strings")
        compiled[name] = compile_query(name, raw if isinstance(raw, Mapping) else {})
    materialized: dict[str, tuple[str, ...]] = {}
    for name in sorted(compiled):
        materialized[name] = tuple(
            record.id for record in evaluate(compiled[name], snapshot)
        )
    return materialized
