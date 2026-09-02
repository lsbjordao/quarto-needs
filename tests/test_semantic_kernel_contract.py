"""Executable semantic-kernel boundary contract.

These tests turn the dependency rules from
``docs/superpowers/specs/2026-09-02-core-stabilization-design.md`` into AST
and dataclass assertions so the boundary cannot silently regress:

* canonical analysis works on declarations/snapshot records and never
  routes through ``EngineeringObject`` (only the explicitly named
  compatibility entry points may touch it);
* graph projections consume ``AnalysisSnapshot``; C4 projections consume
  graph projections, not parser internals;
* public projection dataclasses expose exactly the declared field
  allowlists;
* browser/extension assets consume projection data without redefining
  canonical relation semantics.

A future change that reintroduces the legacy semantic bridge fails here.
"""
from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

from quarto_needs import graph_projection
from quarto_needs.relations import TRAVERSAL_PROFILES

SRC = Path(__file__).resolve().parents[1] / "src" / "quarto_needs"
EXTENSION = Path(__file__).resolve().parents[1] / "_extensions" / "quarto-needs"

# Compatibility surfaces that may still name EngineeringObject. Everything
# else in these modules — the canonical pipeline — must stay legacy-free.
LEGACY_EXEMPT_FUNCTIONS = {
    "analysis.py": {"analyze_objects"},
    "validation.py": {"validate"},
    "parser.py": {"_legacy_object", "parse_qmd", "parse_project"},
}


def _parse(filename: str) -> ast.Module:
    return ast.parse((SRC / filename).read_text(encoding="utf-8"))


def _top_level_functions(tree: ast.Module) -> Iterator[ast.FunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            yield node


def _referenced_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name):
            names.add(inner.id)
        elif isinstance(inner, ast.Attribute):
            names.add(inner.attr)
        elif isinstance(inner, ast.ImportFrom):
            names.update(alias.name for alias in inner.names)
    return names


def _imported_modules(tree: ast.Module) -> set[str]:
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def _called_names(node: ast.AST) -> set[str]:
    return {
        ast.unparse(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
    }


def _type_checking_import_ids(tree: ast.Module) -> set[int]:
    """Collect node ids of imports guarded by ``if TYPE_CHECKING``."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded_test = isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        guarded_test |= (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if not guarded_test:
            continue
        for inner in node.body:
            if isinstance(inner, (ast.Import, ast.ImportFrom)):
                guarded.add(id(inner))
    return guarded


def _runtime_imports(tree: ast.Module) -> set[str]:
    guarded = _type_checking_import_ids(tree)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and id(node) not in guarded:
            if node.module is not None:
                modules.add(node.module)
    return modules


def test_canonical_pipeline_functions_do_not_reference_the_legacy_model() -> None:
    for filename, exempt in LEGACY_EXEMPT_FUNCTIONS.items():
        for function in _top_level_functions(_parse(filename)):
            if function.name in exempt:
                continue
            referenced = _referenced_names(function)
            assert "EngineeringObject" not in referenced, (
                f"{filename}.{function.name} references EngineeringObject; "
                "canonical pipeline code must operate on declarations and "
                "snapshot records"
            )


def test_analyze_batch_is_declaration_native_and_bridge_free() -> None:
    functions = {fn.name: fn for fn in _top_level_functions(_parse("analysis.py"))}

    assert "_legacy_objects" not in functions, (
        "the legacy conversion bridge must stay removed from the canonical "
        "analyzer"
    )
    called = _called_names(functions["_analyze_batch"])
    assert "validate_declarations" in called
    assert "validate" not in called, (
        "_analyze_batch must use the declaration-native validator, not the "
        "EngineeringObject compatibility wrapper"
    )


def test_snapshot_indexes_are_not_built_by_scanning_relations_per_object() -> None:
    # Guards the O(V + E) single-pass index construction. The two strings
    # below are the exact signatures of the removed pattern (one full
    # relation scan per object); their return would reintroduce O(V * E)
    # construction. Matched textually because the pattern is unambiguous.
    source = (SRC / "analysis.py").read_text(encoding="utf-8")
    assert "if relation.source == " not in source
    assert "if relation.target == " not in source


def test_kernel_modules_do_not_import_the_legacy_model_at_runtime() -> None:
    kernel = (
        "rules.py",
        "snapshot.py",
        "fingerprints.py",
        "relations.py",
        "config.py",
        "diagnostics.py",
    )
    for filename in kernel:
        runtime_modules = _runtime_imports(_parse(filename))
        offenders = {
            module
            for module in runtime_modules
            if module == "model" or module.endswith(".model")
        }
        assert not offenders, (
            f"{filename} imports the legacy model module {sorted(offenders)} "
            "at runtime; type-only imports must stay under TYPE_CHECKING"
        )


def test_graph_projections_consume_the_analysis_snapshot() -> None:
    functions = {
        fn.name: fn
        for fn in _top_level_functions(_parse("graph_projection.py"))
    }
    for name in ("select_graph", "build_projection"):
        annotation = ast.unparse(functions[name].args.args[0].annotation)
        assert annotation == "AnalysisSnapshot", (
            f"graph_projection.{name} must consume AnalysisSnapshot"
        )


def test_c4_projections_consume_graph_projections_not_parser_internals() -> None:
    tree = _parse("c4_projection.py")
    modules = _imported_modules(tree)
    names = _referenced_names(tree)

    assert "graph_projection" in modules
    assert "snapshot" in modules
    assert {"build_projection", "select_graph"} <= names
    assert not (modules & {"parser", "model"}), (
        "C4 projections must build on graph/snapshot projections rather than "
        "parsing internals or legacy DTOs"
    )


def test_public_projection_dataclasses_expose_exactly_the_allowlists() -> None:
    node = graph_projection.PublicNode(
        id="A",
        title="T",
        type="t",
        status="s",
        priority="p",
        tags=("x",),
        href="h",
        change="added",
        technology="py",
    )
    edge = graph_projection.PublicEdge(
        source="A", target="B", relation="r", label="L", change="added", path_member=True
    )
    assert set(node.to_dict()) == set(graph_projection.PUBLIC_NODE_FIELDS)
    assert set(edge.to_dict()) == set(graph_projection.PUBLIC_EDGE_FIELDS)


def test_browser_assets_consume_projection_data_without_defining_semantics() -> None:
    # Only hyphenated family identifiers are asserted: single-word families
    # (evidence, verification, ...) share vocabulary with legitimate object
    # type names in presentation policy maps such as TYPE_LEVEL_MAP. The
    # hyphenated names can only come from the relation catalog.
    families = {
        family
        for profile in TRAVERSAL_PROFILES.values()
        for family in profile
        if "-" in family
    }
    assets = sorted(EXTENSION.rglob("*.js")) + sorted(EXTENSION.rglob("*.lua"))
    assert assets, "extension assets are expected to exist"
    for asset in assets:
        tokens = set(re.findall(r"[\w-]+", asset.read_text(encoding="utf-8")))
        overlap = families & tokens
        assert not overlap, (
            f"{asset.name} hardcodes canonical relation families "
            f"{sorted(overlap)}; traversal semantics come from the Python "
            "projection, not the browser"
        )
