"""No dataclass field may default to a bare `MappingProxyType({})` literal.

Found 2026-09-03: CI failed on every Python version with
`ValueError: mutable default <class 'mappingproxy'> for field derived is
not allowed: use default_factory`, raised from `snapshot.py` at import
time -- meaning the whole package was unimportable in real CI.

`dataclasses` rejects a field default whenever the default value's class is
unhashable, as a proxy for "this is mutable and would be shared across every
instance." Whether `MappingProxyType({})` counts as hashable is not a
constant of the language: it changed between the CPython patch build this
repo develops against (3.13.5, where the import happens to succeed) and the
one GitHub Actions' `setup-python` installs for the same minor version
(3.13.15, where it raises) -- so this passed every local run and failed
every CI run, on every one of Python 3.10 through 3.14.

The fix is not "make MappingProxyType hashable again" -- that is an
implementation detail of a type this code does not control. It is to never
lean on it: `field(default_factory=...)` sidesteps the hashability
heuristic entirely, because `dataclasses` never inspects a factory's
return value, only a literal default's class.

This test is deliberately a static source check, not an import-time one:
the whole point is that import-time success on one interpreter proved
nothing, so the regression guard must not depend on which interpreter runs
it.
"""
from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "quarto_needs"


def _call_name(node: ast.expr) -> str | None:
    func = node.func if isinstance(node, ast.Call) else None
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _bare_mappingproxytype_defaults() -> list[tuple[str, int, str]]:
    """Every dataclass field whose literal default is `MappingProxyType(...)`.

    `MappingProxyType(...)` is exactly the pattern this bug hinges on: its
    hashability -- what `dataclasses` uses as its mutable-default proxy --
    is not consistent across CPython patch builds. `field(...)` itself is a
    call expression too, but it is the *correct*, version-stable pattern
    (dataclasses never inspects a factory's return value), so it is not
    flagged; nor is a frozen-dataclass instance like `GraphSettings()`,
    which is genuinely, unconditionally hashable.
    """
    findings: list[tuple[str, int, str]] = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            is_dataclass = any(
                (isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "dataclass")
                or (isinstance(dec, ast.Name) and dec.id == "dataclass")
                for dec in node.decorator_list
            )
            if not is_dataclass:
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or stmt.value is None:
                    continue
                if _call_name(stmt.value) == "MappingProxyType":
                    name = getattr(stmt.target, "id", "<unknown>")
                    findings.append((str(path), stmt.lineno, name))
    return findings


def test_no_dataclass_field_defaults_to_a_bare_mappingproxytype() -> None:
    """`field(default_factory=lambda: MappingProxyType({}))` is the fix.

    Whether `MappingProxyType({}).__class__.__hash__` is `None` is not a
    language constant -- it changed between the CPython patch build this
    repo develops against and the one CI's `setup-python` installs for the
    same minor version, which is exactly how this shipped locally-green and
    broke every CI run on every supported Python version at once.
    """
    offenders = _bare_mappingproxytype_defaults()
    assert not offenders, (
        "dataclass field(s) default to a bare MappingProxyType(...) -- use "
        "field(default_factory=lambda: MappingProxyType(...)) instead; "
        "whether this raises ValueError('mutable default') depends on the "
        "interpreter's patch build, not just its minor version:\n"
        + "\n".join(f"  {file}:{line}: {name}" for file, line, name in offenders)
    )
