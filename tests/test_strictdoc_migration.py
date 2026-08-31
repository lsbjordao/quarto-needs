from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.migrations.strictdoc import (
    StrictDocMigrationError,
    build_migration_plan,
    load_strictdoc_documents,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_basic_project(root: Path) -> None:
    _write(
        root / "srs.sdoc",
        """[DOCUMENT]
TITLE: System Requirements
PREFIX: SRS-

[REQUIREMENT]
UID: SRS-1
STATUS: Active
TITLE: Persist configuration
TAGS: config, storage
STATEMENT: >>>
The system shall persist configuration between runs.
<<<
RATIONALE: >>>
Users expect settings to survive a restart.
<<<
""",
    )
    _write(
        root / "sub" / "llr.sdoc",
        """[DOCUMENT]
TITLE: Low-Level Requirements
PREFIX: LLR-

[REQUIREMENT]
UID: LLR-1
STATUS: Active
TITLE: Write config to disk atomically
STATEMENT: >>>
The config writer shall use a temp-file-plus-rename write.
<<<
RELATIONS:
- TYPE: Parent
  VALUE: SRS-1
""",
    )


def test_load_strictdoc_documents_parses_fields_relations_and_tags(tmp_path: Path) -> None:
    _write_basic_project(tmp_path)

    documents = load_strictdoc_documents(tmp_path)

    by_uid = {item.uid: item for document in documents for item in document.items}
    assert set(by_uid) == {"SRS-1", "LLR-1"}

    srs1 = by_uid["SRS-1"]
    assert srs1.tag == "REQUIREMENT"
    assert srs1.title == "Persist configuration"
    assert srs1.status == "Active"
    assert srs1.statement == "The system shall persist configuration between runs."
    assert srs1.rationale == "Users expect settings to survive a restart."
    assert srs1.tags == ("config", "storage")
    assert srs1.relations == ()

    llr1 = by_uid["LLR-1"]
    assert llr1.relations == (("Parent", "SRS-1"),)


def test_build_migration_plan_maps_types_and_relations_and_folds_rationale(
    tmp_path: Path,
) -> None:
    _write_basic_project(tmp_path)
    documents = load_strictdoc_documents(tmp_path)

    plan = build_migration_plan(
        documents,
        type_map={"REQUIREMENT": "system-requirement"},
        relation_map={"Parent": "derives-from"},
    )

    assert plan.tool == "StrictDoc"
    assert plan.schema == "strictdoc-migration-plan-v1"
    assert plan.issues == ()
    by_id = {candidate.source_id: candidate for candidate in plan.candidates}

    srs1 = by_id["SRS-1"]
    assert srs1.target_type == "system-requirement"
    assert srs1.tags == ("config", "storage")
    assert srs1.content == (
        "The system shall persist configuration between runs.\n\n"
        "### Rationale\n\n"
        "Users expect settings to survive a restart."
    )

    llr1 = by_id["LLR-1"]
    assert [(r.relation, r.target) for r in llr1.relations] == [("derives-from", "SRS-1")]
    assert llr1.content == "The config writer shall use a temp-file-plus-rename write."


def test_build_migration_plan_flags_unmapped_type(tmp_path: Path) -> None:
    _write_basic_project(tmp_path)
    documents = load_strictdoc_documents(tmp_path)

    plan = build_migration_plan(
        documents, type_map={}, relation_map={"Parent": "derives-from"}
    )

    codes = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("TYPE_UNMAPPED", "SRS-1") in codes
    assert ("TYPE_UNMAPPED", "LLR-1") in codes


def test_build_migration_plan_flags_unmapped_relation_type_but_preserves_it(
    tmp_path: Path,
) -> None:
    _write_basic_project(tmp_path)
    documents = load_strictdoc_documents(tmp_path)

    plan = build_migration_plan(
        documents, type_map={"REQUIREMENT": "system-requirement"}, relation_map={}
    )

    codes = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("RELATION_UNMAPPED", "LLR-1") in codes
    llr1 = next(c for c in plan.candidates if c.source_id == "LLR-1")
    assert llr1.relations == ()
    assert llr1.unmapped_links == {"Parent": ("SRS-1",)}


def test_build_migration_plan_flags_external_relation_target(tmp_path: Path) -> None:
    _write(
        tmp_path / "srs.sdoc",
        """[DOCUMENT]
TITLE: System Requirements

[REQUIREMENT]
UID: SRS-1
STATUS: Active
TITLE: Dangling reference
STATEMENT: >>>
Points at a UID that is never defined.
<<<
RELATIONS:
- TYPE: Parent
  VALUE: SRS-999
""",
    )
    documents = load_strictdoc_documents(tmp_path)

    plan = build_migration_plan(
        documents,
        type_map={"REQUIREMENT": "system-requirement"},
        relation_map={"Parent": "derives-from"},
    )

    codes = {(issue.code, issue.need_id, issue.field) for issue in plan.issues}
    assert ("EXTERNAL_LINK_TARGET", "SRS-1", "SRS-999") in codes


def test_build_migration_plan_rejects_duplicate_uid_across_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "a.sdoc",
        "[DOCUMENT]\nTITLE: A\n\n[REQUIREMENT]\nUID: DUP-1\nTITLE: First\nSTATEMENT: >>>\nFirst.\n<<<\n",
    )
    _write(
        tmp_path / "b.sdoc",
        "[DOCUMENT]\nTITLE: B\n\n[REQUIREMENT]\nUID: DUP-1\nTITLE: Second\nSTATEMENT: >>>\nSecond.\n<<<\n",
    )
    documents = load_strictdoc_documents(tmp_path)

    with pytest.raises(StrictDocMigrationError, match="DUP-1"):
        build_migration_plan(
            documents, type_map={"REQUIREMENT": "system-requirement"}, relation_map={}
        )


def test_load_strictdoc_documents_ignores_untagged_sections_and_text(tmp_path: Path) -> None:
    _write(
        tmp_path / "doc.sdoc",
        """[DOCUMENT]
TITLE: Doc

[[SECTION]]
MID: aaaa
TITLE: Introduction

[TEXT]
MID: bbbb
STATEMENT: >>>
Just prose, no UID, should not become a candidate.
<<<

[REQUIREMENT]
UID: REQ-1
TITLE: Real requirement
STATEMENT: >>>
This one has a UID.
<<<

[[/SECTION]]
""",
    )

    documents = load_strictdoc_documents(tmp_path)
    all_items = [item for document in documents for item in document.items]
    assert [item.uid for item in all_items] == ["REQ-1"]
