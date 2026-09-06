from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.quarto_integration import _runtime_extension_dir


def test_active_extension_dir_accepts_real_github_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    extension = root / "_extensions" / "lsbjordao" / "quarto-needs"
    extension.mkdir(parents=True)
    monkeypatch.setenv("QUARTO_NEEDS_EXTENSION_DIR", str(extension))

    assert _runtime_extension_dir(root) == extension.resolve()


def test_active_extension_dir_rejects_path_outside_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside" / "quarto-needs"
    outside.mkdir(parents=True)
    monkeypatch.setenv("QUARTO_NEEDS_EXTENSION_DIR", str(outside))

    with pytest.raises(OSError, match="outside project _extensions"):
        _runtime_extension_dir(root)


def test_active_extension_dir_rejects_extensions_symlink_outside_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside-extensions"
    extension = outside / "lsbjordao" / "quarto-needs"
    extension.mkdir(parents=True)
    (root / "_extensions").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv(
        "QUARTO_NEEDS_EXTENSION_DIR",
        str(root / "_extensions" / "lsbjordao" / "quarto-needs"),
    )

    with pytest.raises(OSError, match="_extensions directory resolves outside project"):
        _runtime_extension_dir(root)


def test_cli_detects_a_single_namespaced_fork(tmp_path: Path) -> None:
    root = tmp_path / "project"
    extension = root / "_extensions" / "acme" / "quarto-needs"
    extension.mkdir(parents=True)

    assert _runtime_extension_dir(root) == extension.resolve()


def test_cli_falls_back_to_unscoped_extension_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    assert _runtime_extension_dir(root) == (
        root / "_extensions" / "quarto-needs"
    ).resolve()
