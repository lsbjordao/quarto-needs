from pathlib import Path

from quarto_needs.parser import parse_qmd
from quarto_needs.validation import validate


def test_parse_need(tmp_path: Path):
    qmd = tmp_path / "req.qmd"
    qmd.write_text('''::: {.need #SYS-REQ-001 type="system-requirement" status="approved" derived-from="NEED-001"}\n## Login\nText.\n:::\n''', encoding="utf-8")
    objs = parse_qmd(qmd, tmp_path)
    assert len(objs) == 1
    assert objs[0].id == "SYS-REQ-001"
    assert objs[0].title == "Login"
    assert objs[0].relations[0].target == "NEED-001"


def test_unknown_reference(tmp_path: Path):
    qmd = tmp_path / "req.qmd"
    qmd.write_text('''::: {.need #SYS-REQ-001 type="system-requirement" verified-by="TC-404"}\n## Login\nText.\n:::\n''', encoding="utf-8")
    findings = validate(parse_qmd(qmd, tmp_path))
    assert any(f.code == "REQ005" for f in findings)


def test_parser_accepts_catalog_only_relation_names(tmp_path: Path):
    qmd = tmp_path / "req.qmd"
    qmd.write_text(
        '''::: {.need #TC-1 type="test-case"}
verifies: REQ-1
evidences: EVD-1
## Login test
Text.
:::
''',
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.type, relation.authored_name, relation.target) for relation in relations] == [
        ("verifies", "verifies", "REQ-1"),
        ("evidences", "evidences", "EVD-1"),
    ]
