from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.localization import validate_localized_pair


@pytest.mark.requirement("FUN-006", "SYS-005")
@pytest.mark.quarto_need_test_case("TC-005")
def test_localized_source_semantic_parity_rejects_model_drift(tmp_path: Path) -> None:
    canonical = tmp_path / "requirements.qmd"
    translated = tmp_path / "requirements.pt-BR.qmd"
    canonical.write_text(
        """::: {.need #FUN-900 type="functional-requirement" status="approved" priority="high" tags="i18n" verified-by="TC-900"}
## Validate localized semantics
Canonical presentation text.
:::
""",
        encoding="utf-8",
    )
    translated.write_text(
        """::: {.need #FUN-900 type="functional-requirement" status="approved" priority="high" tags="i18n" verified-by="TC-900"}
## Validar semântica localizada
Texto de apresentação traduzido.
:::
""",
        encoding="utf-8",
    )

    assert validate_localized_pair(canonical, translated, tmp_path) == {
        "FUN-900": "Validar semântica localizada"
    }

    translated.write_text(
        """::: {.need #FUN-900 type="functional-requirement" status="draft" priority="high" tags="i18n" verified-by="TC-900"}
## Validar semântica localizada
Texto de apresentação traduzido.
:::
""",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="changes semantic metadata for FUN-900"):
        validate_localized_pair(canonical, translated, tmp_path)
