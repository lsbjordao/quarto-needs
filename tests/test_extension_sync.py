from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "_extensions" / "quarto-needs"
EXAMPLE_EXTENSION = ROOT / "examples" / "book" / "_extensions" / "quarto-needs"
PRE_RENDER = ROOT / "tools" / "quarto_needs_pre_render.py"


def pre_render_module():
    spec = spec_from_file_location("quarto_needs_pre_render", PRE_RENDER)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_assets(directory: Path) -> dict[Path, bytes]:
    """Return every canonical extension asset except the generated lookup index."""
    return {
        path.relative_to(directory): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
        and path.relative_to(directory) != Path("generated-index.lua")
        and "__pycache__" not in path.parts
    }


def test_example_extension_matches_all_canonical_runtime_assets():
    """The checked-in showcase installs exactly the canonical adapter assets."""
    assert runtime_assets(EXAMPLE_EXTENSION) == runtime_assets(SOURCE)


@pytest.mark.parametrize(
    "example",
    ["book", "minimal"],
)
def test_every_example_extension_matches_the_canonical_assets(example: str):
    """Every committed example extension copy stays in sync with the source.

    Without this, a new or changed extension asset would silently leave a
    stale vendored copy behind (the pre-render sync repairs it only at the
    next render).
    """
    extension = ROOT / "examples" / example / "_extensions" / "quarto-needs"
    assert runtime_assets(extension) == runtime_assets(SOURCE)


def test_pre_render_synchronizes_all_canonical_extension_assets(tmp_path: Path):
    """Adding a new extension asset must not require changing a sync allow-list."""
    (tmp_path / "index.qmd").write_text("# Empty project\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(PRE_RENDER)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    target = tmp_path / "_extensions" / "quarto-needs"
    assert runtime_assets(target) == runtime_assets(SOURCE)


def test_sync_leaves_project_generated_index_untouched(tmp_path: Path):
    """Sync must not overwrite the graph index generated for this project."""
    target = tmp_path / "_extensions" / "quarto-needs"
    target.mkdir(parents=True)
    generated_index = target / "generated-index.lua"
    generated_index.write_text('return { ["LOCAL"] = {} }\n', encoding="utf-8")

    pre_render_module().sync_extension(tmp_path)

    assert generated_index.read_text(encoding="utf-8") == 'return { ["LOCAL"] = {} }\n'


def test_sync_removes_stale_runtime_files_and_directories(tmp_path: Path):
    """A removed canonical asset must not remain installed in the project."""
    target = tmp_path / "_extensions" / "quarto-needs"
    stale_file = target / "obsolete.lua"
    stale_directory = target / "obsolete-assets"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_text("return {}\n", encoding="utf-8")
    (stale_directory / "nested.js").parent.mkdir(parents=True)
    (stale_directory / "nested.js").write_text("stale\n", encoding="utf-8")
    generated_index = target / "generated-index.lua"
    generated_index.write_text('return { ["LOCAL"] = {} }\n', encoding="utf-8")

    pre_render_module().sync_extension(tmp_path)

    assert not stale_file.exists()
    assert not stale_directory.exists()
    assert generated_index.read_text(encoding="utf-8") == 'return { ["LOCAL"] = {} }\n'


def test_pre_render_synchronizes_then_builds_exactly_once(
    tmp_path: Path, monkeypatch
):
    """Pre-render must delegate all parsing and validation to one build call."""
    module = pre_render_module()
    events: list[tuple[object, ...]] = []

    def sync(project_root: Path) -> None:
        events.append(("sync", project_root))

    def build(project_root: Path, quiet: bool = False) -> int:
        events.append(("build", project_root, quiet))
        return 7

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "sync_extension", sync)
    monkeypatch.setattr(module, "build", build)

    assert module.main() == 7
    assert events == [
        ("sync", tmp_path),
        ("build", tmp_path, False),
    ]
