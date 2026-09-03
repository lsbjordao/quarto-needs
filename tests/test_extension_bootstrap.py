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
