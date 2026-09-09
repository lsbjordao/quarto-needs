"""Install each built distribution outside the checkout and verify its contents."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path, nargs="?", default=Path("dist"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    artifacts = sorted(args.dist.resolve().glob("*.whl")) + sorted(args.dist.resolve().glob("*.tar.gz"))
    if len(artifacts) != 2:
        parser.error("expected exactly one wheel and one sdist")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("QUARTO_NEEDS_ENGINE_SOURCE", None)
    env["PYTHONNOUSERSITE"] = "1"
    for artifact in artifacts:
        with tempfile.TemporaryDirectory(prefix="quarto-needs-release-") as directory:
            work = Path(directory)
            target = work / "venv"
            venv.EnvBuilder(with_pip=True).create(target)
            binary = target / ("Scripts" if os.name == "nt" else "bin")
            python = binary / ("python.exe" if os.name == "nt" else "python")
            cli = binary / ("quarto-needs.exe" if os.name == "nt" else "quarto-needs")
            def run(*command: str) -> None:
                subprocess.run(command, cwd=work, env=env, check=True)
            run(str(python), "-m", "pip", "install", str(artifact))
            run(str(cli), "--version")
            run(str(cli), "--help")
            run(str(python), "-c", "import quarto_needs; import importlib.util; "
                "assert all(importlib.util.find_spec(n) is None for n in ('rdflib', 'pyld', 'reqif', 'xmlschema'))")
            for source_dir in (root / "schemas", root / "_extensions" / "quarto-needs"):
                for source in source_dir.rglob("*"):
                    if not source.is_file() or "__pycache__" in source.parts:
                        continue
                    relative = source.relative_to(root)
                    installed = target / "share" / "quarto-needs" / relative
                    assert installed.is_file(), f"{artifact.name}: missing {relative}"
                    assert installed.read_bytes() == source.read_bytes(), f"{artifact.name}: changed {relative}"
            (work / "index.qmd").write_text(
                '::: {.need #REQ-1 type="functional-requirement" status="approved" priority="high"}\n'
                '## Installed requirement\n\nThe engine shall run outside the checkout.\n'
                '\n### Rationale\nVerify distribution independence.\n:::\n', encoding="utf-8",
            )
            run(str(cli), "scan")
            run(str(cli), "check")
            print(f"PASS: {artifact.name} contents and clean installation", flush=True)


if __name__ == "__main__":
    main()
