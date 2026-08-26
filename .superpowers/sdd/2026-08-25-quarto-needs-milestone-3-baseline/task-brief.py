#!/usr/bin/env python3
"""Extract one task's full text from the plan into its own brief file.

Replaces the skill's `task-brief` script, which requires Git metadata this
workspace does not have.
"""
import re
import sys
from pathlib import Path

plan = Path(sys.argv[1])
number = int(sys.argv[2])
out_dir = Path(sys.argv[3])

text = plan.read_text(encoding="utf-8")
globals_block = text.split("## Global Constraints", 1)[1].split("## File Map", 1)[0].strip()

sections = re.split(r"^### Task (\d+): ", text, flags=re.M)
tasks = {int(sections[i]): sections[i + 1] for i in range(1, len(sections), 2)}
if number not in tasks:
    raise SystemExit(f"Task {number} not found; plan has {sorted(tasks)}")

body = tasks[number].rstrip()
if body.endswith("---"):
    body = body[:-3].rstrip()
title = body.splitlines()[0]

destination = out_dir / f"task-{number}-brief.md"
destination.write_text(
    f"# Task {number}: {title}\n\n"
    f"> Extracted from `{plan}`. This brief is your complete requirements.\n"
    f"> Use every value in it verbatim.\n\n"
    f"## Global Constraints (bind every task)\n\n{globals_block}\n\n"
    f"## Task {number}\n\n{body}\n",
    encoding="utf-8",
)
print(destination)
