from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.migrations.doorstop import (
    DoorstopMigrationError,
    build_migration_plan,
    load_doorstop_documents,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_basic_tree(root: Path) -> None:
    _write(
        root / "reqs" / ".doorstop.yml",
        """
settings:
  digits: 3
  prefix: REQ
  sep: ''
""",
    )
    _write(
        root / "reqs" / "REQ001.yml",
        """
active: true
derived: false
header: 'Assets'
level: 2.3
links: []
normative: true
ref: ''
reviewed: abc
text: |
  Doorstop shall support the storage of external requirements assets.
""",
    )
    _write(
        root / "reqs" / "tutorial" / ".doorstop.yml",
        """
settings:
  digits: 3
  parent: REQ
  prefix: TUT
  sep: ''
""",
    )
    _write(
        root / "reqs" / "tutorial" / "TUT008.yml",
        """
active: true
derived: false
header: ''
level: 1.4
links:
- REQ001: 9TcFUzsQWUHhoh5wsqnhL7VRtSqMaIhrCXg7mfIkxKM=
normative: true
ref: ''
reviewed: vNBr4d83a8SIKz4mOaDu2_eLZlXcgDoKSW09sThlb9U=
text: |
  Validating the Tree.
""",
    )


def test_load_doorstop_documents_discovers_nested_document_tree(tmp_path: Path) -> None:
    _write_basic_tree(tmp_path)

    documents = load_doorstop_documents(tmp_path)

    by_prefix = {document.prefix: document for document in documents}
    assert set(by_prefix) == {"REQ", "TUT"}
    assert by_prefix["REQ"].parent is None
    assert by_prefix["TUT"].parent == "REQ"
    assert {item.uid for item in by_prefix["REQ"].items} == {"REQ001"}
    assert {item.uid for item in by_prefix["TUT"].items} == {"TUT008"}


def test_build_migration_plan_maps_types_and_relations_by_document_prefix(tmp_path: Path) -> None:
    _write_basic_tree(tmp_path)
    documents = load_doorstop_documents(tmp_path)

    plan = build_migration_plan(
        documents,
        type_map={"REQ": "system-requirement", "TUT": "test-case"},
        relation_map={"TUT": "derives-from"},
    )

    assert plan.tool == "Doorstop"
    assert plan.schema == "doorstop-migration-plan-v1"
    assert plan.issues == ()
    by_id = {candidate.source_id: candidate for candidate in plan.candidates}
    assert by_id["REQ001"].target_type == "system-requirement"
    assert by_id["REQ001"].title == "Assets"
    assert by_id["REQ001"].content == "Doorstop shall support the storage of external requirements assets."
    assert by_id["REQ001"].relations == ()

    tut008 = by_id["TUT008"]
    assert tut008.target_type == "test-case"
    assert tut008.title == "TUT008"  # empty header falls back to the UID
    assert [(r.relation, r.target) for r in tut008.relations] == [("derives-from", "REQ001")]
    assert tut008.extras["active"] is True
    assert tut008.extras["normative"] is True
    assert tut008.extras["derived"] is False


def test_build_migration_plan_flags_unmapped_type_prefix(tmp_path: Path) -> None:
    _write_basic_tree(tmp_path)
    documents = load_doorstop_documents(tmp_path)

    plan = build_migration_plan(
        documents,
        type_map={"REQ": "system-requirement"},
        relation_map={"TUT": "derives-from"},
    )

    codes = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("TYPE_UNMAPPED", "TUT008") in codes


def test_build_migration_plan_flags_unmapped_relation_prefix_but_preserves_link(
    tmp_path: Path,
) -> None:
    _write_basic_tree(tmp_path)
    documents = load_doorstop_documents(tmp_path)

    plan = build_migration_plan(
        documents,
        type_map={"REQ": "system-requirement", "TUT": "test-case"},
        relation_map={},
    )

    codes = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("RELATION_UNMAPPED", "TUT008") in codes
    tut008 = next(c for c in plan.candidates if c.source_id == "TUT008")
    assert tut008.relations == ()
    assert tut008.unmapped_links == {"TUT": ("REQ001",)}


def test_build_migration_plan_flags_external_link_target(tmp_path: Path) -> None:
    _write_basic_tree(tmp_path)
    _write(
        tmp_path / "reqs" / "tutorial" / "TUT009.yml",
        """
active: true
derived: false
header: ''
level: 1.5
links:
- REQ999: abc
normative: true
ref: ''
reviewed: abc
text: |
  Links to a requirement that does not exist anywhere in the tree.
""",
    )
    documents = load_doorstop_documents(tmp_path)

    plan = build_migration_plan(
        documents,
        type_map={"REQ": "system-requirement", "TUT": "test-case"},
        relation_map={"TUT": "derives-from"},
    )

    codes = {(issue.code, issue.need_id, issue.field) for issue in plan.issues}
    assert ("EXTERNAL_LINK_TARGET", "TUT009", "REQ999") in codes


def test_build_migration_plan_rejects_duplicate_uid_across_documents(tmp_path: Path) -> None:
    _write_basic_tree(tmp_path)
    _write(
        tmp_path / "reqs" / "other" / ".doorstop.yml",
        """
settings:
  digits: 3
  prefix: REQ
  sep: ''
""",
    )
    _write(
        tmp_path / "reqs" / "other" / "REQ001.yml",
        """
active: true
derived: false
header: 'Duplicate'
level: 1.0
links: []
normative: true
ref: ''
reviewed: abc
text: |
  Same UID reused by a misconfigured second document.
""",
    )
    documents = load_doorstop_documents(tmp_path)

    with pytest.raises(DoorstopMigrationError, match="REQ001"):
        build_migration_plan(
            documents,
            type_map={"REQ": "system-requirement", "TUT": "test-case"},
            relation_map={"TUT": "derives-from"},
        )


def test_load_doorstop_documents_rejects_document_without_prefix(tmp_path: Path) -> None:
    _write(tmp_path / "reqs" / ".doorstop.yml", "settings:\n  digits: 3\n")

    with pytest.raises(DoorstopMigrationError, match="prefix"):
        load_doorstop_documents(tmp_path)
