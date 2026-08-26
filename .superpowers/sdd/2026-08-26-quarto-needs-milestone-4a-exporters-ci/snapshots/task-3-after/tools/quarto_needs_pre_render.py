"""Zero-install pre-render entry point for a Quarto project."""
import os
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path.cwd().resolve()
GENERATED_INDEX = Path("generated-index.lua")
sys.path.insert(0, str(REPO_ROOT / "src"))

from quarto_needs.cli import build  # noqa: E402


def sync_extension(project_root: Path) -> None:
    """Install all canonical extension assets except the generated lookup index."""
    source = REPO_ROOT / "_extensions" / "quarto-needs"
    target = project_root / "_extensions" / "quarto-needs"
    if target.is_symlink() or target.parent.is_symlink():
        raise RuntimeError(f"Refusing to synchronize extension through symlink: {target}")
    target.mkdir(parents=True, exist_ok=True)

    source_files = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.is_file() and path.relative_to(source) != GENERATED_INDEX
    }
    source_directories = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.is_dir()
    }

    for target_path, directories, filenames in os.walk(target, topdown=False, followlinks=False):
        current = Path(target_path)
        for name in filenames:
            installed = current / name
            relative = installed.relative_to(target)
            if relative == GENERATED_INDEX:
                if installed.is_symlink():
                    raise RuntimeError(f"Refusing to use generated index symlink: {installed}")
                continue
            if installed.is_symlink() or relative not in source_files:
                installed.unlink()
        for name in directories:
            installed = current / name
            relative = installed.relative_to(target)
            if installed.is_symlink():
                installed.unlink()
            elif relative not in source_directories:
                installed.rmdir()

    for source_path in source.rglob("*"):
        if not source_path.is_file() or source_path.relative_to(source) == GENERATED_INDEX:
            continue
        target_path = target / source_path.relative_to(source)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def main() -> int:
    sync_extension(PROJECT_ROOT)
    return build(PROJECT_ROOT, quiet=False)


if __name__ == "__main__":
    raise SystemExit(main())
