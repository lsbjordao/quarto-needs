from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "examples" / "quarto-needs" / "_pre_render.py"


def load_hook():
    spec = spec_from_file_location("quarto_needs_example_pre_render", HOOK)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_self_hosted_project_hook_prepares_but_does_not_build(
    tmp_path: Path, monkeypatch
) -> None:
    """The example hook runs before the extension; only the extension builds."""
    module = load_hook()
    events: list[tuple[str, Path]] = []

    monkeypatch.setattr(module, "repository_root", lambda: ROOT)

    import quarto_needs.localization as localization

    monkeypatch.setattr(
        localization,
        "write_localized_projections",
        lambda root: events.append(("localize", Path(root))),
    )

    helper = types.ModuleType("quarto_needs_pre_render")
    helper.sync_extension = lambda root: events.append(("sync", Path(root)))
    monkeypatch.setitem(sys.modules, "quarto_needs_pre_render", helper)
    monkeypatch.chdir(tmp_path)

    module.main()

    assert events == [
        ("sync", tmp_path.resolve()),
        ("localize", tmp_path.resolve()),
    ]


def test_self_hosted_project_keeps_the_extension_activated() -> None:
    quarto_yml = (
        ROOT / "examples" / "quarto-needs" / "_quarto.yml"
    ).read_text(encoding="utf-8")
    assert "pre-render: python3 _pre_render.py" in quarto_yml
    assert "filters:\n  - quarto-needs" in quarto_yml
