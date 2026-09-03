"""Shared test setup.

Since Phase 8B, activating the Quarto-Needs extension also installs its
engine step: any `quarto render` in these tests now runs the extension's
bootstrap, which provisions `quarto-needs==<extension version>` from the
package index.

That version is not published, and the tests must not reach the network
anyway, so the whole session points the bootstrap at a wheel built from
this checkout -- exactly the local-source override that exists for
development and air-gapped preparation.

Building the wheel once matters. The override also accepts a source
directory, but then every rendered fixture project would rebuild the
package from source; one prebuilt wheel turns that into a plain install.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SOURCE_ENV = "QUARTO_NEEDS_ENGINE_SOURCE"


@pytest.fixture(scope="session", autouse=True)
def local_engine_source(tmp_path_factory: pytest.TempPathFactory):
    """Point the extension bootstrap at this checkout for the whole session.

    Yields the source it set, or the caller's own value when one is already
    exported, so a developer can aim the suite at a specific artifact.
    """
    existing = os.environ.get(ENGINE_SOURCE_ENV)
    if existing:
        yield existing
        return

    wheel_dir = tmp_path_factory.mktemp("quarto-needs-engine")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--quiet",
            "--wheel-dir",
            str(wheel_dir),
            str(ROOT),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(
            "Could not build the engine wheel the extension bootstrap "
            f"provisions from:\n{completed.stderr or completed.stdout}"
        )
    wheels = sorted(wheel_dir.glob("*.whl"))
    assert wheels, f"pip wheel wrote no wheel into {wheel_dir}"

    os.environ[ENGINE_SOURCE_ENV] = str(wheels[0])
    try:
        yield str(wheels[0])
    finally:
        os.environ.pop(ENGINE_SOURCE_ENV, None)
