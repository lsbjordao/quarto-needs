from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from quarto_needs import __version__


@pytest.mark.requirement("FUN-020")
@pytest.mark.quarto_need_test_case("TC-032")
def test_version_works_outside_a_project(tmp_path: Path) -> None:
    """Installation diagnostics must not require a valid authoring project."""
    (tmp_path / ".quarto-needs.toml").write_text("invalid TOML [", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    result = subprocess.run(
        [sys.executable, "-m", "quarto_needs.cli_entry", "--version"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"quarto-needs {__version__}"
    assert result.stderr == ""
