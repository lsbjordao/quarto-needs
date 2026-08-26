#!/usr/bin/env python3
"""Write one review package: file list, stat summary, and full diff.

Replaces the skill's `review-package` script. BASE and HEAD are snapshot
directories rather than commits.
"""
import subprocess
import sys
from pathlib import Path

base, head, destination = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

diff = subprocess.run(
    ["diff", "-ruN", "--unified=10", str(base), str(head)],
    capture_output=True, text=True,
).stdout

def _path_of(line: str) -> str:
    # `diff -ruN` appends a tab and a timestamp to the +++ header.
    return line[4:].split("\t", 1)[0].replace(f"{head}/", "", 1)


changed = sorted(
    _path_of(line)
    for line in diff.splitlines()
    if line.startswith("+++ ") and "/dev/null" not in line
)
added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))

destination.write_text(
    f"# Review package\n\n"
    f"Snapshot range: `{base.name}` -> `{head.name}`\n\n"
    f"## Files changed ({len(changed)})\n\n"
    + "".join(f"- `{name}`\n" for name in changed)
    + f"\n## Summary\n\n{added} lines added, {removed} lines removed.\n\n"
    f"## Full diff (10 lines of context)\n\n```diff\n{diff}```\n",
    encoding="utf-8",
)
print(destination)
