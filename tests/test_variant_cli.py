from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main


def _project(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"

[types.test-case]
role = "verification"

[queries.one]
all = [{ field = "id", op = "eq", value = "FUN-001" }]
sort = ["id:asc"]

[variants.assurance]
scope = "one"
relations = ["verified-by"]
depth = 1
''',
        encoding="utf-8",
    )
    (tmp_path / "model.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Requirement
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Test
:::
''',
        encoding="utf-8",
    )


def test_variant_list_json(tmp_path: Path, capsys) -> None:
    _project(tmp_path)
    assert main(["--root", str(tmp_path), "variant", "list", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["variants"] == [
        {"name": "assurance", "objects": ["FUN-001", "TC-001"], "count": 2}
    ]
    assert payload["variantFingerprint"]


def test_variant_show_text(tmp_path: Path, capsys) -> None:
    _project(tmp_path)
    assert main(["--root", str(tmp_path), "variant", "show", "assurance"]) == 0
    output = capsys.readouterr().out
    assert "Variant assurance: 2 object(s)" in output
    assert "FUN-001" in output
    assert "TC-001" in output


def test_unknown_variant_is_configuration_style_error(tmp_path: Path, capsys) -> None:
    _project(tmp_path)
    assert main(["--root", str(tmp_path), "variant", "show", "missing"]) == 2
    assert "Unknown build variant: missing" in capsys.readouterr().err
