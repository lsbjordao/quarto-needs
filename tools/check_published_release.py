"""Exercise public Quarto installation paths against a published engine."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    args = parser.parse_args()
    env = dict(os.environ)
    env.pop("QUARTO_NEEDS_ENGINE_SOURCE", None)
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="quarto-needs-public-") as directory:
        for mode in ("extension", "starter"):
            project = Path(directory) / mode
            project.mkdir()
            def run(*command: str) -> None:
                subprocess.run(command, cwd=project, env=env, check=True)
            if mode == "starter":
                run("quarto", "use", "template", "lsbjordao/quarto-needs/templates/starter", "--no-prompt")
            else:
                run("quarto", "add", "lsbjordao/quarto-needs", "--no-prompt")
                (project / "_quarto.yml").write_text("project:\n  type: default\nfilters:\n  - quarto-needs\n", encoding="utf-8")
                (project / "index.qmd").write_text(
                    '::: {.need #REQ-1 type="functional-requirement" status="approved" priority="high"}\n'
                    '## Public installation\n\nThe extension shall render.\n\n### Rationale\n'
                    'Verify the published release.\n:::\n\n{{< need-count >}}\n', encoding="utf-8",
                )
            run("quarto", "render")
            markers = list((project / ".quarto-needs" / "runtime").rglob("installed.json"))
            assert markers, f"{mode}: no managed runtime"
            assert all(json.loads(p.read_text())["engineVersion"] == args.version for p in markers)
            graph = json.loads((project / ".quarto-needs" / "needs.json").read_text())
            assert graph["objects"], f"{mode}: empty graph"
            html = list(project.rglob("*.html"))
            assert any("need-card" in p.read_text(encoding="utf-8") for p in html), f"{mode}: no card"
            print(f"PASS: public {mode} path provisions {args.version}", flush=True)


if __name__ == "__main__":
    main()
