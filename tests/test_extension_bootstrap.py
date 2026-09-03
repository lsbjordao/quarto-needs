"""The extension's managed-runtime bootstrap.

The bootstrap runs before the engine exists, so it gets standard library
only and must be correct without anything to lean on. These tests cover the
parts that are easy to get subtly wrong -- runtime identity, what counts as
proof that a cached runtime is usable, and the lock -- because by the time
this code is wrong, every render in the project is failing.

Nothing here reaches the network. Provisioning is exercised through an
injected installer; Task 4 covers the real one.

Spec: docs/superpowers/specs/2026-09-02-extension-first-distribution-design.md
Plan: docs/superpowers/plans/2026-09-02-extension-first-distribution.md (Task 3)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "_extensions" / "quarto-needs" / "bootstrap.py"


def load_bootstrap():
    """Import the script the way a test can, not the way Quarto runs it."""
    spec = importlib.util.spec_from_file_location("quarto_needs_bootstrap", BOOTSTRAP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # `_extensions/quarto-needs/` is a shipped directory that the example
    # projects mirror byte for byte. Importing from it must not leave a
    # __pycache__ behind for the sync check to trip over.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


bootstrap = load_bootstrap()


# --- Import hygiene ---------------------------------------------------------


def test_importing_the_bootstrap_has_no_side_effects(tmp_path) -> None:
    """Loading it must not create directories, install, or run anything."""
    before = set(sys.modules)
    module = load_bootstrap()
    assert module.MINIMUM_PYTHON == (3, 10)
    # It may not drag the engine in: the engine is what it exists to install.
    assert "quarto_needs" not in (set(sys.modules) - before)


def test_the_bootstrap_uses_only_the_standard_library() -> None:
    """It runs before the managed runtime exists, so it has nothing else.

    A third-party import here would be a bootstrap that cannot start until
    something has already installed its dependency -- exactly the problem
    this phase removes.
    """
    import ast

    tree = ast.parse(BOOTSTRAP.read_text(encoding="utf-8"))

    def roots(node: ast.AST) -> set[str]:
        found: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                found.update(alias.name.split(".")[0] for alias in child.names)
            elif isinstance(child, ast.ImportFrom) and child.module and child.level == 0:
                found.add(child.module.split(".")[0])
        return found

    # `load_pre_render` is the handoff: by the time it runs, the managed
    # runtime is on sys.path, so importing the engine there is the whole
    # point. Everything else must stand on the standard library alone.
    engine_loader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_pre_render"
    )
    before_the_runtime = roots(tree) - roots(engine_loader)

    assert before_the_runtime <= set(sys.stdlib_module_names), (
        before_the_runtime - set(sys.stdlib_module_names)
    )
    assert "quarto_needs" in roots(engine_loader), (
        "the engine handoff should be the one place the engine is imported"
    )


# --- Identity ---------------------------------------------------------------


def test_extension_version_comes_from_the_manifest(tmp_path) -> None:
    manifest = tmp_path / "_extension.yml"
    manifest.write_text("title: X\nversion: 9.9.9\n", encoding="utf-8")

    assert bootstrap.extension_version(manifest) == "9.9.9"


def test_a_manifest_without_a_version_is_a_bootstrap_error(tmp_path) -> None:
    manifest = tmp_path / "_extension.yml"
    manifest.write_text("title: X\n", encoding="utf-8")

    with pytest.raises(bootstrap.BootstrapError, match="declares no version"):
        bootstrap.extension_version(manifest)


def test_the_shipped_manifest_version_is_readable() -> None:
    """The real manifest must parse -- this is what provisioning installs."""
    assert bootstrap.extension_version()


def test_runtime_identity_covers_interpreter_and_machine() -> None:
    identity = bootstrap.runtime_identity()

    assert identity["schemaVersion"] == "quarto-needs-managed-runtime-v1"
    for key in ("pythonImplementation", "pythonTag", "pythonVersion", "platform", "machine"):
        assert identity[key], key


def test_different_interpreters_get_different_runtime_directories(tmp_path) -> None:
    """`pip --target` can place compiled modules, so identity is not just version.

    Reusing a CPython 3.11 runtime under CPython 3.13 is how you get an
    import error that looks like a corrupt install.
    """
    base = bootstrap.runtime_identity()
    other = dict(base, pythonTag="cpython-311")

    assert bootstrap.runtime_directory(
        tmp_path, "0.1.0", base
    ) != bootstrap.runtime_directory(tmp_path, "0.1.0", other)


def test_different_versions_get_different_runtime_directories(tmp_path) -> None:
    identity = bootstrap.runtime_identity()

    assert bootstrap.runtime_directory(
        tmp_path, "0.1.0", identity
    ) != bootstrap.runtime_directory(tmp_path, "0.2.0", identity)


def test_the_runtime_lives_under_generated_project_state(tmp_path) -> None:
    """Nothing global, nothing in the user's virtualenv, nothing on PATH."""
    directory = bootstrap.runtime_directory(
        tmp_path, "0.1.0", bootstrap.runtime_identity()
    )

    assert directory.is_relative_to(tmp_path / ".quarto-needs" / "runtime")


def test_identity_slug_is_path_safe() -> None:
    slug = bootstrap.identity_slug(
        {"pythonTag": "cpython-313", "platform": "win32", "machine": "AMD64/x86"}
    )

    assert "/" not in slug
    assert slug == "cpython-313-win32-AMD64_x86"


# --- Marker -----------------------------------------------------------------


def test_marker_round_trips(tmp_path) -> None:
    identity = bootstrap.runtime_identity()
    tmp_path.mkdir(exist_ok=True)

    bootstrap.write_marker(tmp_path, "0.1.0", identity)
    marker = bootstrap.read_marker(tmp_path)

    assert marker is not None
    assert marker["engineVersion"] == "0.1.0"
    assert bootstrap.marker_matches(marker, "0.1.0", identity)


def test_a_marker_for_another_version_does_not_match(tmp_path) -> None:
    identity = bootstrap.runtime_identity()
    bootstrap.write_marker(tmp_path, "0.1.0", identity)

    assert not bootstrap.marker_matches(
        bootstrap.read_marker(tmp_path), "0.2.0", identity
    )


def test_a_missing_or_corrupt_marker_reads_as_absent(tmp_path) -> None:
    assert bootstrap.read_marker(tmp_path) is None

    bootstrap.marker_path(tmp_path).write_text("{not json", encoding="utf-8")
    assert bootstrap.read_marker(tmp_path) is None


# --- Validation -------------------------------------------------------------


def test_a_marker_alone_is_never_proof_of_a_valid_runtime(tmp_path) -> None:
    """The central rule: the marker says what was intended, not what is there.

    Here the marker is perfect and the site-packages directory is empty, so
    the runtime must be rejected -- otherwise a wiped cache directory with a
    surviving marker would send the render on with no engine.
    """
    identity = bootstrap.runtime_identity()
    runtime_dir = bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    bootstrap.site_packages(runtime_dir).mkdir(parents=True)
    bootstrap.write_marker(runtime_dir, "0.1.0", identity)

    assert not bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)


def test_a_runtime_whose_engine_imports_from_elsewhere_is_invalid(tmp_path) -> None:
    """A system-installed engine must not validate a managed runtime.

    This is the extension/engine skew the design exists to remove: the
    probe imports with an empty site-packages first on the path, so if
    anything resolves, it resolved from outside the runtime.
    """
    identity = bootstrap.runtime_identity()
    runtime_dir = bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    target = bootstrap.site_packages(runtime_dir)
    target.mkdir(parents=True)
    bootstrap.write_marker(runtime_dir, "0.1.0", identity)

    # The repository's own quarto_needs is importable in this test session,
    # but it does not live under `target`, so validation must reject it.
    assert not bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)


def test_a_runtime_validates_when_the_engine_really_is_installed_there(tmp_path) -> None:
    identity = bootstrap.runtime_identity()
    runtime_dir = bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    target = bootstrap.site_packages(runtime_dir)
    target.mkdir(parents=True)
    _plant_engine(target, "0.1.0")
    bootstrap.write_marker(runtime_dir, "0.1.0", identity)

    assert bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)


def test_a_runtime_holding_the_wrong_engine_version_is_invalid(tmp_path) -> None:
    identity = bootstrap.runtime_identity()
    runtime_dir = bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    target = bootstrap.site_packages(runtime_dir)
    target.mkdir(parents=True)
    _plant_engine(target, "0.9.9")
    bootstrap.write_marker(runtime_dir, "0.1.0", identity)

    assert not bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)


def _plant_engine(target: Path, version: str) -> None:
    """A minimal importable `quarto_needs` reporting *version*.

    Enough for the probe, which asks only for `__version__` and `__file__`.
    """
    package = target / "quarto_needs"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    # Validation imports the entry point, so a stand-in engine must expose
    # one -- the same thing a real install provides.
    (package / "quarto_integration.py").write_text(
        "def run_quarto_pre_render(root, quiet=False):\n    return 0\n",
        encoding="utf-8",
    )


# --- Python prerequisite ----------------------------------------------------


def test_an_old_python_is_rejected_with_an_actionable_message() -> None:
    with pytest.raises(bootstrap.BootstrapError) as caught:
        bootstrap.check_python((3, 9))

    message = str(caught.value)
    assert "3.10" in message and "3.9" in message
    assert sys.executable in message, "say which interpreter, not just which version"


def test_a_supported_python_passes() -> None:
    bootstrap.check_python((3, 10))
    bootstrap.check_python(sys.version_info[:2])


# --- Provisioning command ---------------------------------------------------


def test_the_install_source_is_the_exact_version_by_default(monkeypatch) -> None:
    monkeypatch.delenv(bootstrap.ENGINE_SOURCE_ENV, raising=False)

    assert bootstrap.engine_source("0.2.0") == "quarto-needs==0.2.0"


def test_a_local_source_override_is_honored(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(bootstrap.ENGINE_SOURCE_ENV, str(tmp_path))

    assert bootstrap.engine_source("0.2.0") == str(tmp_path)


def test_the_provision_command_never_shells_out_or_uses_bare_pip(tmp_path) -> None:
    command = bootstrap.provision_command(tmp_path, "quarto-needs==0.2.0")

    assert command[:4] == [sys.executable, "-m", "pip", "install"]
    assert "--target" in command
    assert command[-1] == "quarto-needs==0.2.0"
    # An argument array, so nothing is ever interpolated into a shell.
    assert all(isinstance(part, str) for part in command)


def test_installation_targets_a_directory_not_the_active_environment(tmp_path) -> None:
    command = bootstrap.provision_command(tmp_path / "site-packages", "src")

    assert str(tmp_path / "site-packages") in command


# --- The lock ---------------------------------------------------------------


def test_the_lock_is_acquired_and_released(tmp_path) -> None:
    path = tmp_path / "lock"

    with bootstrap.exclusive_lock(path):
        assert path.exists()

    assert not path.exists()


def test_a_second_holder_cannot_acquire_the_lock_simultaneously(tmp_path) -> None:
    path = tmp_path / "lock"

    with bootstrap.exclusive_lock(path):
        with pytest.raises(bootstrap.BootstrapError, match="Timed out"):
            with bootstrap.exclusive_lock(path, wait_seconds=0.2, poll_seconds=0.01):
                pytest.fail("the lock was granted twice")


def test_a_waiting_holder_acquires_the_lock_once_it_is_released(tmp_path) -> None:
    """The bounded wait must actually succeed when the holder finishes."""
    path = tmp_path / "lock"
    acquired = threading.Event()

    def waiter() -> None:
        with bootstrap.exclusive_lock(path, wait_seconds=10, poll_seconds=0.01):
            acquired.set()

    with bootstrap.exclusive_lock(path):
        thread = threading.Thread(target=waiter)
        thread.start()
        assert not acquired.wait(timeout=0.2), "granted while still held"

    thread.join(timeout=10)
    assert acquired.is_set(), "never granted after release"


def test_a_stale_lock_is_reclaimed(tmp_path) -> None:
    """A render killed mid-install must not wedge the project forever."""
    path = tmp_path / "lock"
    path.write_text("99999\n", encoding="utf-8")
    import os

    old = time.time() - 10_000
    os.utime(path, (old, old))

    with bootstrap.exclusive_lock(path, wait_seconds=0.5, stale_seconds=600):
        assert path.exists()

    assert not path.exists()


def test_an_exception_inside_the_lock_still_releases_it(tmp_path) -> None:
    path = tmp_path / "lock"

    with pytest.raises(RuntimeError):
        with bootstrap.exclusive_lock(path):
            raise RuntimeError("install blew up")

    assert not path.exists()
    # And the next caller gets it immediately.
    with bootstrap.exclusive_lock(path, wait_seconds=0.5):
        pass


# --- Staging and promotion --------------------------------------------------


def test_staging_directories_are_unique(tmp_path) -> None:
    first = bootstrap.staging_directory(tmp_path)
    second = bootstrap.staging_directory(tmp_path)

    assert first != second


def test_a_failed_provision_leaves_no_staging_directory_behind(tmp_path) -> None:
    """A crashed install must leave nothing that looks like a runtime."""
    identity = bootstrap.runtime_identity()

    def failing_installer(target: Path, source: str) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "half-written.txt").write_text("oops", encoding="utf-8")
        raise bootstrap.BootstrapError("pip exploded")

    with pytest.raises(bootstrap.BootstrapError, match="pip exploded"):
        bootstrap.provision_runtime(
            tmp_path, "0.1.0", identity, installer=failing_installer
        )

    leftovers = list(bootstrap.runtime_root(tmp_path).glob(".staging-*"))
    assert leftovers == [], leftovers
    assert not bootstrap.runtime_directory(tmp_path, "0.1.0", identity).exists()


def test_an_install_producing_the_wrong_version_is_rejected_and_cleaned(tmp_path) -> None:
    """A local source is never trusted for the version its filename claims."""
    identity = bootstrap.runtime_identity()

    def wrong_version(target: Path, source: str) -> None:
        _plant_engine(target, "0.9.9")

    with pytest.raises(bootstrap.BootstrapError, match="reports version 0.9.9"):
        bootstrap.provision_runtime(
            tmp_path, "0.1.0", identity, installer=wrong_version
        )

    assert list(bootstrap.runtime_root(tmp_path).glob(".staging-*")) == []
    assert not bootstrap.runtime_directory(tmp_path, "0.1.0", identity).exists()


def test_a_successful_provision_publishes_a_valid_runtime(tmp_path) -> None:
    identity = bootstrap.runtime_identity()

    def good(target: Path, source: str) -> None:
        _plant_engine(target, "0.1.0")

    runtime_dir = bootstrap.provision_runtime(
        tmp_path, "0.1.0", identity, installer=good
    )

    assert runtime_dir == bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    assert bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)
    # Marker written only after validation succeeded.
    marker = json.loads(bootstrap.marker_path(runtime_dir).read_text(encoding="utf-8"))
    assert marker["engineVersion"] == "0.1.0"
    # And nothing was left staged.
    assert list(bootstrap.runtime_root(tmp_path).glob(".staging-*")) == []


def test_provisioning_never_writes_into_the_final_directory_first(tmp_path) -> None:
    """The final path must not exist until a validated runtime is promoted."""
    identity = bootstrap.runtime_identity()
    final = bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    seen: list[bool] = []

    def observing(target: Path, source: str) -> None:
        seen.append(final.exists())
        _plant_engine(target, "0.1.0")

    bootstrap.provision_runtime(tmp_path, "0.1.0", identity, installer=observing)

    assert seen == [False], "installed straight into the published location"


# --- Engine source validation (Task 4) --------------------------------------


def test_an_engine_source_pointing_nowhere_is_rejected(monkeypatch, tmp_path) -> None:
    """A typo in the override must fail loudly, not fall back to the index.

    Falling back would quietly install a published engine while the operator
    believed they were testing a local build.
    """
    monkeypatch.setenv(bootstrap.ENGINE_SOURCE_ENV, str(tmp_path / "nope"))

    with pytest.raises(bootstrap.BootstrapError, match="does not exist"):
        bootstrap.engine_source("0.1.0")


def test_a_remote_engine_source_is_refused(monkeypatch) -> None:
    """This slice accepts a local path only -- never an arbitrary URL."""
    monkeypatch.setenv(
        bootstrap.ENGINE_SOURCE_ENV, "https://example.invalid/quarto_needs.whl"
    )

    with pytest.raises(bootstrap.BootstrapError, match="local filesystem path"):
        bootstrap.engine_source("0.1.0")


def test_an_existing_local_engine_source_is_accepted(monkeypatch, tmp_path) -> None:
    source = tmp_path / "checkout"
    source.mkdir()
    monkeypatch.setenv(bootstrap.ENGINE_SOURCE_ENV, str(source))

    assert bootstrap.engine_source("0.1.0") == str(source)


# --- Installer failures -----------------------------------------------------


def test_missing_pip_reports_which_interpreter_lacks_it(monkeypatch, tmp_path) -> None:
    def no_pip(target, source):
        return ["/nonexistent/interpreter", "-m", "pip", "install"]

    monkeypatch.setattr(bootstrap, "provision_command", no_pip)

    with pytest.raises(bootstrap.BootstrapError, match="Could not run pip"):
        bootstrap.install_engine(tmp_path, "quarto-needs==0.1.0")


def test_a_failing_install_surfaces_what_pip_printed(monkeypatch, tmp_path) -> None:
    def failing(target, source):
        return [
            sys.executable,
            "-c",
            "import sys; print('No matching distribution found', file=sys.stderr);"
            " raise SystemExit(1)",
        ]

    monkeypatch.setattr(bootstrap, "provision_command", failing)

    with pytest.raises(bootstrap.BootstrapError) as caught:
        bootstrap.install_engine(tmp_path, "quarto-needs==9.9.9")

    assert "No matching distribution found" in str(caught.value)
    assert "quarto-needs==9.9.9" in str(caught.value)


# --- ensure_runtime: the full algorithm -------------------------------------


def test_a_valid_cached_runtime_triggers_no_installation(tmp_path, monkeypatch) -> None:
    """The offline guarantee: a good runtime never contacts an index."""
    # The session points the bootstrap at a locally built wheel; this test
    # is about the default source, so it clears that.
    monkeypatch.delenv(bootstrap.ENGINE_SOURCE_ENV, raising=False)
    identity = bootstrap.runtime_identity()
    calls: list[str] = []

    def counting(target: Path, source: str) -> None:
        calls.append(source)
        _plant_engine(target, "0.1.0")

    first = bootstrap.ensure_runtime(tmp_path, "0.1.0", identity, installer=counting)
    assert calls == ["quarto-needs==0.1.0"]

    second = bootstrap.ensure_runtime(tmp_path, "0.1.0", identity, installer=counting)

    assert second == first
    assert calls == ["quarto-needs==0.1.0"], "reinstalled a runtime that was already valid"


def test_a_corrupted_runtime_is_reprovisioned(tmp_path) -> None:
    """A marker that outlived its site-packages must not be trusted."""
    identity = bootstrap.runtime_identity()
    calls: list[str] = []

    def counting(target: Path, source: str) -> None:
        calls.append(source)
        _plant_engine(target, "0.1.0")

    runtime_dir = bootstrap.ensure_runtime(
        tmp_path, "0.1.0", identity, installer=counting
    )
    # Wipe the engine but leave the marker: exactly what a partially cleaned
    # cache directory looks like.
    import shutil

    shutil.rmtree(bootstrap.site_packages(runtime_dir))
    assert bootstrap.read_marker(runtime_dir) is not None

    bootstrap.ensure_runtime(tmp_path, "0.1.0", identity, installer=counting)

    assert len(calls) == 2, "trusted a runtime whose engine was gone"
    assert bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)


def test_ensure_runtime_releases_the_lock_after_a_failed_install(tmp_path) -> None:
    identity = bootstrap.runtime_identity()

    def failing(target: Path, source: str) -> None:
        raise bootstrap.BootstrapError("install failed")

    with pytest.raises(bootstrap.BootstrapError, match="install failed"):
        bootstrap.ensure_runtime(tmp_path, "0.1.0", identity, installer=failing)

    assert not bootstrap.lock_path(tmp_path).exists()
    # A later render can still provision.
    bootstrap.ensure_runtime(
        tmp_path,
        "0.1.0",
        identity,
        installer=lambda target, source: _plant_engine(target, "0.1.0"),
    )


def test_an_updated_extension_provisions_beside_the_old_runtime(tmp_path) -> None:
    """Updating must not mutate an existing runtime in place."""
    identity = bootstrap.runtime_identity()

    def planting(version: str):
        return lambda target, source: _plant_engine(target, version)

    old = bootstrap.ensure_runtime(
        tmp_path, "0.1.0", identity, installer=planting("0.1.0")
    )
    new = bootstrap.ensure_runtime(
        tmp_path, "0.2.0", identity, installer=planting("0.2.0")
    )

    assert old != new
    assert bootstrap.runtime_is_valid(old, "0.1.0", identity)
    assert bootstrap.runtime_is_valid(new, "0.2.0", identity)


# --- Real provisioning ------------------------------------------------------


@pytest.mark.slow
def test_the_real_installer_provisions_this_checkout(tmp_path, monkeypatch) -> None:
    """Provision the engine for real, from this source tree.

    Everything above injects an installer. This one runs the actual
    `python -m pip install --target` path the extension will use, against
    the local-source override -- which is exactly how it is meant to work
    before the package is published.
    """
    identity = bootstrap.runtime_identity()
    version = bootstrap.extension_version()

    # monkeypatch, not os.environ: popping the variable by hand unset the
    # session-wide engine source and broke every later test that renders.
    monkeypatch.setenv(bootstrap.ENGINE_SOURCE_ENV, str(ROOT))
    runtime_dir = bootstrap.ensure_runtime(tmp_path, version, identity)

    assert bootstrap.runtime_is_valid(runtime_dir, version, identity)
    installed = bootstrap.site_packages(runtime_dir) / "quarto_needs" / "__init__.py"
    assert installed.is_file(), "the engine was not installed into the runtime"


def test_a_truncated_engine_install_is_not_a_valid_runtime(tmp_path) -> None:
    """An importable package with the engine missing must not validate.

    `pip` interrupted part way can leave `quarto_needs/__init__.py` in place
    with the rest absent. Validating on the top-level package alone would
    call that a good runtime and hand the render an engine it cannot invoke.
    """
    identity = bootstrap.runtime_identity()
    runtime_dir = bootstrap.runtime_directory(tmp_path, "0.1.0", identity)
    target = bootstrap.site_packages(runtime_dir)
    package = target / "quarto_needs"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    bootstrap.write_marker(runtime_dir, "0.1.0", identity)

    assert not bootstrap.runtime_is_valid(runtime_dir, "0.1.0", identity)


# --- Task 5: invoking the engine --------------------------------------------

PROJECT_QMD = '''---
title: "Bootstrap fixture"
---

::: {.need #REQ-1 type="functional-requirement" status="approved" priority="high"}
## Authenticate the user

The system shall authenticate the user.

### Rationale
Protect private data.
:::

::: {.need #TC-1 type="test-case" status="passed" verifies="REQ-1"}
## Login test

Signs a user in.
:::
'''


def _consumer_project(root: Path) -> Path:
    """A project holding the extension, the way `quarto add` leaves it."""
    import shutil

    root.mkdir(parents=True, exist_ok=True)
    (root / "index.qmd").write_text(PROJECT_QMD, encoding="utf-8")
    extension = root / "_extensions" / "quarto-needs"
    extension.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "_extensions" / "quarto-needs", extension)
    return root


def _run_bootstrap(root: Path, *, extra_path: Path | None = None):
    """Run bootstrap.py as its own process, the way Quarto runs it."""
    import os
    import subprocess

    environment = dict(os.environ)
    environment["QUARTO_NEEDS_ENGINE_SOURCE"] = str(ROOT)
    environment["QUARTO_PROJECT_DIR"] = str(root)
    environment.pop("PYTHONPATH", None)
    if extra_path is not None:
        environment["PYTHONPATH"] = str(extra_path)
    return subprocess.run(
        [sys.executable, str(root / "_extensions" / "quarto-needs" / "bootstrap.py")],
        capture_output=True,
        text=True,
        env=environment,
        cwd=str(root),
        timeout=600,
    )


@pytest.mark.slow
def test_the_bootstrap_builds_the_graph_end_to_end(tmp_path) -> None:
    root = _consumer_project(tmp_path / "consumer")

    completed = _run_bootstrap(root)

    assert completed.returncode == 0, completed.stderr
    graph = json.loads(
        (root / ".quarto-needs" / "needs.json").read_text(encoding="utf-8")
    )
    assert {item["id"] for item in graph["objects"]} == {"REQ-1", "TC-1"}
    assert graph["schemaVersion"] == "1"


@pytest.mark.slow
def test_a_wrong_global_engine_never_wins_over_the_managed_runtime(tmp_path) -> None:
    """The skew this design removes, proved rather than asserted.

    An importable `quarto_needs` reporting a different version sits first in
    the ambient environment via PYTHONPATH. The managed runtime must still
    be the engine that runs.
    """
    root = _consumer_project(tmp_path / "consumer")
    ambient = tmp_path / "ambient"
    _plant_engine(ambient, "0.0.1-global")

    # Sanity: without the bootstrap, that ambient copy is what imports.
    import subprocess

    probe = subprocess.run(
        [sys.executable, "-c", "import quarto_needs; print(quarto_needs.__version__)"],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ambient), "PATH": "/usr/bin:/bin"},
    )
    assert probe.stdout.strip() == "0.0.1-global", probe

    completed = _run_bootstrap(root, extra_path=ambient)

    assert completed.returncode == 0, completed.stderr
    # The wrong engine could not have produced this graph.
    graph = json.loads(
        (root / ".quarto-needs" / "needs.json").read_text(encoding="utf-8")
    )
    assert {item["id"] for item in graph["objects"]} == {"REQ-1", "TC-1"}

    marker = json.loads(
        next(
            (root / ".quarto-needs" / "runtime").rglob("installed.json")
        ).read_text(encoding="utf-8")
    )
    assert marker["engineVersion"] == bootstrap.extension_version()


@pytest.mark.slow
def test_the_bootstrap_and_the_cli_write_identical_artifacts(tmp_path) -> None:
    """Artifact parity: same project, two invocation paths, same bytes.

    This is the phase's core promise -- changing who invokes the engine must
    change nothing the project produces.
    """
    from quarto_needs import cli

    via_bootstrap = _consumer_project(tmp_path / "via-bootstrap")
    via_cli = tmp_path / "via-cli"
    via_cli.mkdir()
    (via_cli / "index.qmd").write_text(PROJECT_QMD, encoding="utf-8")

    assert _run_bootstrap(via_bootstrap).returncode == 0
    assert cli.build(via_cli, quiet=True) == 0

    def artifacts(root: Path) -> dict[str, bytes]:
        base = root / ".quarto-needs"
        return {
            path.relative_to(base).as_posix(): path.read_bytes()
            for path in sorted(base.rglob("*"))
            # The runtime tree is provisioning state, not a semantic artifact.
            if path.is_file() and "runtime" not in path.relative_to(base).parts
        }

    assert artifacts(via_bootstrap) == artifacts(via_cli)


@pytest.mark.slow
def test_an_unsatisfiable_engine_source_fails_the_render(tmp_path) -> None:
    """A bootstrap failure must stop the build, not render an empty graph."""
    import os
    import subprocess

    root = _consumer_project(tmp_path / "consumer")
    environment = dict(os.environ)
    environment["QUARTO_NEEDS_ENGINE_SOURCE"] = str(tmp_path / "missing")
    environment["QUARTO_PROJECT_DIR"] = str(root)

    completed = subprocess.run(
        [sys.executable, str(root / "_extensions" / "quarto-needs" / "bootstrap.py")],
        capture_output=True,
        text=True,
        env=environment,
        cwd=str(root),
        timeout=600,
    )

    assert completed.returncode != 0
    assert "does not exist" in completed.stderr
    assert not (root / ".quarto-needs" / "needs.json").exists(), (
        "wrote a graph despite failing to provision an engine"
    )


# --- Task 8: hardening --------------------------------------------------


def test_the_first_run_offline_failure_names_everything_the_spec_requires(
    tmp_path,
) -> None:
    """§11: a first-run failure must be actionable, not merely "it failed".

    No cached runtime and an unreachable engine source is the worst case: the
    render has nothing to fall back on. The message must say which engine
    version was needed, that no managed runtime exists, that provisioning
    failed, and how to recover -- an online render or a local engine source.
    """
    identity = bootstrap.runtime_identity()

    def unreachable(target: Path, source: str) -> None:
        raise bootstrap.BootstrapError(
            "Installing the Quarto-Needs engine (quarto-needs==9.9.9) failed:\n"
            "ERROR: No matching distribution found for quarto-needs==9.9.9"
        )

    with pytest.raises(bootstrap.BootstrapError) as caught:
        bootstrap.ensure_runtime(tmp_path, "9.9.9", identity, installer=unreachable)

    message = str(caught.value)
    assert "9.9.9" in message, "must name the required engine version"
    assert "no managed runtime" in message.lower(), "must say none exists yet"
    assert "could not be provisioned" in message.lower() or "failed" in message.lower()
    assert "QUARTO_NEEDS_ENGINE_SOURCE" in message, "must name the recovery path"
    assert "online" in message.lower() or "network" in message.lower(), (
        "must mention rendering once with network access as the other recovery"
    )


def test_a_runtime_valid_for_one_version_does_not_satisfy_a_request_for_another(
    tmp_path,
) -> None:
    """An update from 0.1.0 to 0.2.0 must reprovision, not reuse silently."""
    identity = bootstrap.runtime_identity()

    def planting(version: str):
        return lambda target, source: _plant_engine(target, version)

    old_dir = bootstrap.ensure_runtime(
        tmp_path, "0.1.0", identity, installer=planting("0.1.0")
    )
    assert bootstrap.runtime_is_valid(old_dir, "0.1.0", identity)
    assert not bootstrap.runtime_is_valid(old_dir, "0.2.0", identity)


@pytest.mark.slow
def test_two_concurrent_bootstrap_processes_produce_one_installation(tmp_path) -> None:
    """Two real processes race on the same clean project.

    Both must end up with a valid runtime; neither may see a partial one; and
    the losing process's wait for the lock must not itself corrupt anything.
    This is the scenario the lock exists for, run for real rather than only
    at the unit level.
    """
    import subprocess

    root = _consumer_project(tmp_path / "consumer")

    def launch():
        environment = dict(os.environ)
        environment["QUARTO_NEEDS_ENGINE_SOURCE"] = str(ROOT)
        environment["QUARTO_PROJECT_DIR"] = str(root)
        environment.pop("PYTHONPATH", None)
        return subprocess.Popen(
            [
                sys.executable,
                str(root / "_extensions" / "quarto-needs" / "bootstrap.py"),
            ],
            cwd=str(root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    import os

    first = launch()
    second = launch()
    first_out, first_err = first.communicate(timeout=600)
    second_out, second_err = second.communicate(timeout=600)

    assert first.returncode == 0, first_err
    assert second.returncode == 0, second_err

    identity = bootstrap.runtime_identity()
    version = bootstrap.extension_version()
    runtime_dir = bootstrap.runtime_directory(root, version, identity)
    assert bootstrap.runtime_is_valid(runtime_dir, version, identity)

    # Exactly one final publication: no `.staging-*` leftovers from either
    # process, and no second sibling runtime directory for this identity.
    staging_leftovers = list(bootstrap.runtime_root(root).glob(".staging-*"))
    assert staging_leftovers == [], staging_leftovers
    siblings = list((bootstrap.runtime_root(root) / version).iterdir())
    assert siblings == [bootstrap.runtime_directory(root, version, identity)], siblings


def test_a_missing_pip_module_is_detected_before_any_network_attempt(
    monkeypatch, tmp_path
) -> None:
    """No pip: fail with a diagnosis, never fall back to a global ensurepip."""

    def broken(target, source):
        return [sys.executable, "-c", "import sys; sys.exit(1)"]

    monkeypatch.setattr(bootstrap, "provision_command", broken)

    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.install_engine(tmp_path, "quarto-needs==0.1.0")

    # No ensurepip invocation is ever constructed by the bootstrap.
    source = (ROOT / "_extensions" / "quarto-needs" / "bootstrap.py").read_text(
        encoding="utf-8"
    )
    assert "ensurepip" not in source


def test_install_engine_honors_pip_index_url_from_the_environment(
    monkeypatch, tmp_path
) -> None:
    """The release rehearsal points pip at TestPyPI without touching bootstrap.py.

    `install_engine`'s subprocess inherits the parent environment rather than
    replacing it, so `PIP_INDEX_URL`/`PIP_EXTRA_INDEX_URL` -- pip's own
    mechanism -- reach the install without the bootstrap needing an index-url
    parameter of its own. That absence is deliberate: spec §16 forbids
    accepting an index/URL from project configuration. This proves the
    inherited environment is really what pip subprocess sees, using a bogus
    index whose distinctive failure could only come from pip having tried it.
    """
    monkeypatch.setenv("PIP_INDEX_URL", "https://example.invalid/simple/")
    monkeypatch.delenv("PIP_EXTRA_INDEX_URL", raising=False)

    with pytest.raises(bootstrap.BootstrapError) as caught:
        bootstrap.install_engine(tmp_path, "quarto-needs==0.1.0")

    message = str(caught.value)
    assert "example.invalid" in message, (
        "pip did not appear to use the PIP_INDEX_URL override at all"
    )
