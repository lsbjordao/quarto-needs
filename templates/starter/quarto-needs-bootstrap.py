"""Delegate to the extension installed by either a local or GitHub template."""
from pathlib import Path
import runpy


root = Path(__file__).resolve().parent
for relative in ("lsbjordao/quarto-needs", "quarto-needs"):
    entry = root / "_extensions" / relative / "bootstrap-entry.py"
    if entry.is_file():
        runpy.run_path(str(entry), run_name="__main__")
        break
else:
    raise SystemExit(
        "Quarto-Needs extension is missing. Run "
        "`quarto add lsbjordao/quarto-needs` in this project, then `quarto render`."
    )
