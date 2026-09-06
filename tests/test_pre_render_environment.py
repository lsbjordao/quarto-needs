from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRE_RENDER = ROOT / "tools" / "quarto_needs_pre_render.py"


def _pre_render_module():
    spec = importlib.util.spec_from_file_location("quarto_needs_pre_render_env", PRE_RENDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_restores_absent_extension_environment(tmp_path, monkeypatch) -> None:
    module = _pre_render_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "sync_extension", lambda root: None)
    monkeypatch.setattr(module, "safe_extension_target", lambda root: root / "_extensions" / "lsbjordao" / "quarto-needs")
    monkeypatch.setattr(module, "build", lambda root, quiet=False: 0)
    monkeypatch.setattr(module, "write_localized_projections", lambda root: None)
    monkeypatch.delenv("QUARTO_NEEDS_EXTENSION_DIR", raising=False)

    assert module.main() == 0
    assert "QUARTO_NEEDS_EXTENSION_DIR" not in os.environ


def test_main_restores_existing_extension_environment(tmp_path, monkeypatch) -> None:
    module = _pre_render_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "sync_extension", lambda root: None)
    monkeypatch.setattr(module, "safe_extension_target", lambda root: root / "_extensions" / "lsbjordao" / "quarto-needs")
    monkeypatch.setattr(module, "build", lambda root, quiet=False: 0)
    monkeypatch.setattr(module, "write_localized_projections", lambda root: None)
    monkeypatch.setenv("QUARTO_NEEDS_EXTENSION_DIR", "/previous/extension")

    assert module.main() == 0
    assert os.environ["QUARTO_NEEDS_EXTENSION_DIR"] == "/previous/extension"
