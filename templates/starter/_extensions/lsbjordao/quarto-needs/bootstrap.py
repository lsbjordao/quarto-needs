"""Managed-runtime bootstrap for the Quarto-Needs extension.

Quarto runs this before rendering. Its job is to make sure the exact Python
engine paired with this extension is present in the project's generated
state, then hand control to that engine's canonical pre-render service.

Standard library only. This code runs *before* the managed runtime exists,
so it cannot import anything the runtime provides -- including
`quarto_needs` itself.

It is a runtime adapter and nothing more. It holds no parser, no graph
semantics, no rule evaluation, no projection logic, and no interpretation of
authored relations. Everything semantic lives in the engine it loads.

Importing this module has no side effects, so tests can exercise each piece
in isolation; `main()` is the only thing that touches the filesystem.

Contract: Phase 8B extension-first distribution.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

EXTENSION_DIR = Path(__file__).resolve().parent
MANIFEST = EXTENSION_DIR / "_extension.yml"

MARKER_SCHEMA_VERSION = "quarto-needs-managed-runtime-v1"
MARKER_NAME = "installed.json"
SITE_PACKAGES_NAME = "site-packages"

MINIMUM_PYTHON = (3, 10)

# A render holding the lock is installing a package; a couple of minutes is
# generous for that and still bounded. A lock older than the stale threshold
# belonged to a process that died without releasing it.
LOCK_WAIT_SECONDS = 120.0
LOCK_STALE_SECONDS = 600.0
LOCK_POLL_SECONDS = 0.05

# The one supported source override, for development and air-gapped
# preparation. A local filesystem path only -- never an arbitrary remote URL,
# and never anything a project file can set.
ENGINE_SOURCE_ENV = "QUARTO_NEEDS_ENGINE_SOURCE"


class BootstrapError(Exception):
    """A failure that must stop the render with an actionable message."""


# --- Identity ---------------------------------------------------------------


def extension_version(manifest: Path = MANIFEST) -> str:
    """The version this extension is pinned to, read from its own manifest.

    Read rather than hardcoded so the manifest stays the single source of
    truth: a bootstrap that disagreed with the extension it ships inside
    would provision the wrong engine.
    """
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError as error:
        raise BootstrapError(f"Cannot read the extension manifest {manifest}: {error}")
    match = re.search(r"^version:\s*(\S+)\s*$", text, re.M)
    if not match:
        raise BootstrapError(f"The extension manifest {manifest} declares no version")
    return match.group(1).strip("\"'")


def runtime_identity() -> dict[str, str]:
    """Everything about this interpreter that makes a runtime non-portable.

    A runtime installed for CPython 3.11 on macOS/arm64 must never be reused
    by CPython 3.13 on Linux/x86_64: `pip --target` can place compiled
    extension modules, so the interpreter and machine are part of identity,
    not decoration.

    The interpreter is identified down to its minor version only. A routine
    patch update (3.13.6 to 3.13.7) keeps the same bytecodes and ABI for a
    target install, and pinning the patch here would force a full network
    reprovision -- or an offline render failure -- after nothing but an OS
    security update.
    """
    implementation = platform.python_implementation().lower()
    major, minor = sys.version_info[:2]
    return {
        "schemaVersion": MARKER_SCHEMA_VERSION,
        "pythonImplementation": implementation,
        "pythonTag": f"{implementation}-{major}{minor}",
        "pythonVersion": f"{major}.{minor}",
        "platform": sys.platform,
        "machine": platform.machine(),
    }


def identity_slug(identity: dict[str, str]) -> str:
    """A path-safe directory name for one interpreter/platform combination."""
    parts = (identity["pythonTag"], identity["platform"], identity["machine"])
    slug = "-".join(part for part in parts if part)
    return re.sub(r"[^A-Za-z0-9_.-]", "_", slug)


# --- Locations --------------------------------------------------------------


def project_root() -> Path:
    """The Quarto project this extension is installed into.

    Quarto exports `QUARTO_PROJECT_DIR` for pre-render scripts; prefer it,
    because it is what Quarto itself considers the project. Fall back to the
    extension's own location (`<project>/_extensions/quarto-needs/`), which
    holds regardless of the working directory a caller happens to have.
    """
    declared = os.environ.get("QUARTO_PROJECT_DIR")
    if declared:
        return Path(declared).resolve()
    return EXTENSION_DIR.parents[1]


def runtime_root(root: Path) -> Path:
    return root / ".quarto-needs" / "runtime"


def runtime_directory(root: Path, version: str, identity: dict[str, str]) -> Path:
    """Where one exact engine/interpreter pairing lives.

    Versioned *and* interpreter-scoped, so updating the extension provisions
    a new directory rather than mutating the old one in place.
    """
    return runtime_root(root) / version / identity_slug(identity)


def site_packages(runtime_dir: Path) -> Path:
    return runtime_dir / SITE_PACKAGES_NAME


def marker_path(runtime_dir: Path) -> Path:
    return runtime_dir / MARKER_NAME


# --- Marker -----------------------------------------------------------------


def build_marker(version: str, identity: dict[str, str]) -> dict[str, str]:
    marker = dict(identity)
    marker["engineVersion"] = version
    return marker


def write_marker(runtime_dir: Path, version: str, identity: dict[str, str]) -> None:
    """Record what was installed. Written last, after a complete install."""
    marker_path(runtime_dir).write_text(
        json.dumps(build_marker(version, identity), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_marker(runtime_dir: Path) -> dict[str, str] | None:
    try:
        loaded = json.loads(marker_path(runtime_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def marker_matches(
    marker: dict[str, str] | None, version: str, identity: dict[str, str]
) -> bool:
    if not marker:
        return False
    expected = build_marker(version, identity)
    return all(marker.get(key) == value for key, value in expected.items())


# --- Validation -------------------------------------------------------------


def probe_engine(target: Path) -> tuple[str, str] | None:
    """Import `quarto_needs` from *target* and report its version and file.

    Runs in a child interpreter so a probe cannot contaminate this process's
    module table, and reports `__file__` so the caller can prove the import
    resolved inside the managed runtime rather than from an unrelated
    `quarto-needs` that happens to be installed on the system.
    """
    # Import the entry point the bootstrap will actually call, not merely
    # the top-level package: a truncated install can leave an importable
    # `quarto_needs/__init__.py` with the rest of the engine missing, and a
    # runtime that cannot be invoked is not a runtime.
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(target)!r})\n"
        "import quarto_needs\n"
        "from quarto_needs.quarto_integration import run_quarto_pre_render\n"
        "print(json.dumps({'version': quarto_needs.__version__,"
        " 'file': quarto_needs.__file__}))\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        return str(payload["version"]), str(payload["file"])
    except (ValueError, KeyError, IndexError):
        return None


def runtime_is_valid(
    runtime_dir: Path, version: str, identity: dict[str, str]
) -> bool:
    """A runtime is usable only when it can prove itself.

    The marker is descriptive, never authoritative: it says what an earlier
    process intended to install. Proof is importing the engine out of this
    runtime's own site-packages and getting the exact expected version from
    a file that actually lives there.
    """
    if not marker_matches(read_marker(runtime_dir), version, identity):
        return False
    target = site_packages(runtime_dir)
    if not target.is_dir():
        return False
    probed = probe_engine(target)
    if probed is None:
        return False
    found_version, found_file = probed
    if found_version != version:
        return False
    try:
        Path(found_file).resolve().relative_to(target.resolve())
    except ValueError:
        # Imported from somewhere else entirely -- a system install standing
        # in for the managed one. That is the skew this design exists to
        # prevent, so it is not a valid runtime.
        return False
    return True


# --- Lock -------------------------------------------------------------------


def _read_lock_token(path: Path) -> tuple[int, str] | None:
    """The holder's (pid, token), or None when absent or unreadable.

    Locks written by earlier versions hold just a pid; they parse as
    (pid, "<pid>") and stay reclaimable through both paths below.
    """
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    head = content.split("-", 1)[0].strip()
    try:
        pid = int(head)
    except ValueError:
        return None
    return pid, content


def _unlink_matching(path: Path, recorded: tuple[int, str] | None) -> bool:
    """Delete *path* only when it still carries this exact lock token."""
    if recorded is None:
        return False
    try:
        if _read_lock_token(path) != recorded:
            # The file now belongs to a different holder, or is gone.
            return False
        path.unlink()
        return True
    except OSError:
        return False


def _process_alive(pid: int) -> bool | None:
    """Whether *pid* is running, when the platform can tell without harm.

    POSIX can probe with signal 0, which does not deliver anything. On
    Windows os.kill with any other value terminates the target process, so
    it must never be used as a liveness probe there; Windows falls back to
    mtime staleness only.
    """
    if os.name != "posix":
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


@contextmanager
def exclusive_lock(
    path: Path,
    *,
    wait_seconds: float = LOCK_WAIT_SECONDS,
    stale_seconds: float = LOCK_STALE_SECONDS,
    poll_seconds: float = LOCK_POLL_SECONDS,
):
    """A cross-platform exclusive lock built on atomic file creation.

    `O_CREAT | O_EXCL` is atomic on every platform Quarto runs on, which
    `flock` is not. The holder records its process ID; a waiter reclaims a
    lock whose holder process is demonstrably gone, or whose file is older
    than *stale_seconds* -- the fallback for platforms (and situations)
    where liveness cannot be probed safely.

    Ownership is a token, not a name: release only deletes the file when it
    still holds this holder's token, so a holder that was legitimately
    reclaimed can never delete the replacement lock. The lock is always
    released, including when the body raises -- a failed install must not
    wedge every later render.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    descriptor = None
    token = f"{os.getpid()}-{time.time_ns()}"
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            recorded = _read_lock_token(path)
            liveness = _process_alive(recorded[0]) if recorded is not None else None
            if liveness is False:
                # The holder is dead: reclaim now rather than making every
                # render after a crash wait out the full staleness window.
                if _unlink_matching(path, recorded):
                    continue
            try:
                age = time.time() - path.stat().st_mtime
            except OSError:
                # It vanished between the failed create and the stat: the
                # holder released it, so try again immediately.
                continue
            # A provably live holder keeps its lock however old the mtime
            # looks -- an old mtime means a slow install, not a dead render.
            # When liveness cannot be probed, age alone decides.
            if age > stale_seconds and liveness is not True:
                if _unlink_matching(path, recorded):
                    continue
            if time.monotonic() >= deadline:
                raise BootstrapError(
                    f"Timed out after {wait_seconds:.0f}s waiting for the "
                    f"Quarto-Needs runtime lock at {path}. Another render is "
                    "provisioning the engine; wait for it and render again. "
                    f"A lock left by a crashed render is reclaimed "
                    f"automatically within {stale_seconds / 60:.0f} minutes."
                )
            time.sleep(poll_seconds)
    try:
        os.write(descriptor, token.encode("utf-8"))
        os.close(descriptor)
        descriptor = None
        yield path
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _unlink_matching(path, (os.getpid(), token))


def lock_path(root: Path) -> Path:
    return runtime_root(root) / ".bootstrap.lock"


# --- Provisioning -----------------------------------------------------------


def engine_source(version: str) -> str:
    """What to install: the exact released package, or a local override.

    Unset means `quarto-needs==<version>` exactly. Never a floor, never a
    range, and never `latest`: the extension and the engine ship together,
    so anything looser reintroduces the skew this replaces.

    The override takes a local filesystem path only. A remote URL is refused
    in this slice, and a path that does not exist is an error rather than a
    silent fallback to the package index -- falling back would install a
    published engine while the operator believed they were testing a local
    build. Whatever the source, the installed engine still has to prove its
    version afterwards; a path is never trusted for what its name claims.
    """
    override = os.environ.get(ENGINE_SOURCE_ENV)
    if not override:
        return f"quarto-needs=={version}"
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", override):
        raise BootstrapError(
            f"{ENGINE_SOURCE_ENV} must be a local filesystem path; refusing the "
            f"remote source {override!r}."
        )
    if not Path(override).exists():
        raise BootstrapError(
            f"{ENGINE_SOURCE_ENV} points at {override!r}, which does not exist."
        )
    return override


def provision_command(target: Path, source: str) -> list[str]:
    """The exact argument array used to install the engine.

    An array, never a shell string: nothing here is ever interpolated into a
    shell. `python -m pip` from the interpreter Quarto chose, never a bare
    `pip`, which could belong to an entirely different environment.
    """
    return [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--target",
        str(target),
        source,
    ]


def staging_directory(parent: Path) -> Path:
    """A unique, empty directory to install into.

    Installation never writes to the final runtime path: a half-finished
    install that crashed there would look like a runtime on the next render.
    """
    parent.mkdir(parents=True, exist_ok=True)
    return parent / f".staging-{os.getpid()}-{time.time_ns()}"


def promote(staging: Path, runtime_dir: Path) -> None:
    """Publish a validated staging runtime under its final name.

    Failures here must be BootstrapErrors: a bare OSError from this step
    would escape ensure_runtime's diagnosis and reach the user as a raw
    traceback, breaking the "every bootstrap failure explains itself"
    contract.
    """
    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        if runtime_dir.exists():
            # Strict, not ignore_errors: a silent rmtree failure (a locked
            # file on Windows, say) would leave os.replace publishing onto a
            # non-empty directory, and the resulting error would name
            # nothing a user could act on.
            shutil.rmtree(runtime_dir)
        os.replace(staging, runtime_dir)
    except OSError as error:
        raise BootstrapError(
            f"Could not publish the managed runtime at {runtime_dir}: {error}\n"
            "Delete the .quarto-needs/runtime directory and render again to "
            "reprovision from scratch."
        ) from error


def install_engine(target: Path, source: str) -> None:
    """Run the provisioning command, or raise with what it printed."""
    command = provision_command(target, source)
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as error:
        raise BootstrapError(
            f"Could not run pip from {sys.executable} to provision the "
            f"Quarto-Needs engine: {error}"
        )
    if completed.returncode != 0:
        # pip splits diagnostically useful output across both streams --
        # "Looking in indexes: ..." is stdout, the actual failure is
        # stderr -- and keeping only one drops exactly the line a release
        # rehearsal needs to confirm which index pip actually queried.
        parts = [part.strip() for part in (completed.stdout, completed.stderr) if part.strip()]
        detail = "\n".join(parts)
        raise BootstrapError(
            f"Installing the Quarto-Needs engine ({source}) failed:\n{detail}"
        )


def provision_runtime(
    root: Path,
    version: str,
    identity: dict[str, str],
    *,
    installer=install_engine,
) -> Path:
    """Install, validate, then publish -- in that order, or not at all.

    Everything happens in a staging directory that is removed on any
    failure, so a run that dies part way through leaves nothing a later
    render could mistake for a working runtime. The marker is written only
    after the installed engine has proved its own version.
    """
    runtime_dir = runtime_directory(root, version, identity)
    staging = staging_directory(runtime_root(root))
    target = site_packages(staging)
    try:
        target.mkdir(parents=True, exist_ok=True)
        installer(target, engine_source(version))
        probed = probe_engine(target)
        if probed is None:
            raise BootstrapError(
                f"The provisioned Quarto-Needs engine in {target} could not be "
                "imported. The installation did not produce a usable engine."
            )
        found_version, found_file = probed
        if found_version != version:
            raise BootstrapError(
                f"The provisioned engine reports version {found_version}, but "
                f"this extension requires exactly {version}. A local engine "
                "source is never trusted for the version its filename claims."
            )
        try:
            Path(found_file).resolve().relative_to(target.resolve())
        except ValueError:
            raise BootstrapError(
                f"The engine imported for validation came from {found_file}, "
                f"outside the managed runtime {target}. Refusing to publish a "
                "runtime validated against a different installation."
            )
        write_marker(staging, version, identity)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    promote(staging, runtime_dir)
    return runtime_dir


def ensure_runtime(
    root: Path,
    version: str,
    identity: dict[str, str],
    *,
    installer=install_engine,
) -> Path:
    """Return a runtime directory proven to hold the exact engine.

    The fast path is the common one: a valid runtime is reused without
    taking the lock and without contacting a package index, which is what
    makes every render after the first work offline.

    Otherwise the lock is taken and validity is rechecked underneath it,
    because a concurrent render may have published a good runtime while this
    one was waiting. That recheck is what turns two racing renders into one
    installation rather than two.
    """
    runtime_dir = runtime_directory(root, version, identity)
    if runtime_is_valid(runtime_dir, version, identity):
        return runtime_dir
    with exclusive_lock(lock_path(root)):
        if runtime_is_valid(runtime_dir, version, identity):
            return runtime_dir
        try:
            return provision_runtime(root, version, identity, installer=installer)
        except BootstrapError as error:
            # The worst case: no cached runtime, and provisioning just
            # failed. The render has nothing to fall back on, so the message
            # must be a complete diagnosis rather than a bare exception --
            # which engine version was needed, that no runtime exists yet,
            # that provisioning failed, and both ways to recover.
            raise BootstrapError(
                f"Quarto-Needs {version} has no managed runtime at {runtime_dir}, "
                f"and it could not be provisioned:\n{error}\n\n"
                "To recover, either render once with network access so the "
                f"engine can be installed, or set {ENGINE_SOURCE_ENV} to a "
                "local checkout or wheel of quarto-needs and render again."
            ) from error


# --- Engine invocation ------------------------------------------------------


def load_pre_render(target: Path):
    """Import the managed engine's canonical pre-render service.

    The managed runtime must win outright. Putting *target* first on
    `sys.path` is only half of that: anything already imported would be
    served from `sys.modules` regardless of path order, so a `quarto_needs`
    that arrived from the ambient environment before this call is dropped
    first. Otherwise a globally installed 0.1.0 could answer for an
    extension pinned to 0.2.0 -- the skew this design exists to remove.
    """
    for name in [name for name in sys.modules if name.split(".")[0] == "quarto_needs"]:
        del sys.modules[name]
    while str(target) in sys.path:
        sys.path.remove(str(target))
    sys.path.insert(0, str(target))
    try:
        from quarto_needs.quarto_integration import run_quarto_pre_render
    except ImportError as error:
        raise BootstrapError(
            f"The managed Quarto-Needs runtime at {target} could not be loaded: {error}"
        )
    return run_quarto_pre_render


def check_python(version_info: tuple[int, ...] = sys.version_info[:2]) -> None:
    if tuple(version_info[:2]) < MINIMUM_PYTHON:
        found = ".".join(str(part) for part in version_info[:2])
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        raise BootstrapError(
            f"Quarto-Needs requires Python {required} or later; this render is "
            f"using Python {found} at {sys.executable}."
        )


def main(argv: list[str] | None = None) -> int:
    """Ensure the engine, then hand the project to it.

    Load the runtime, invoke the canonical integration, forward its status.
    Nothing here reimplements `scan`: the exit code returned is the one the
    engine produced, so the extension path and the CLI path agree by
    construction.

    Every bootstrap failure is a render failure with an actionable message.
    A document that rendered successfully while silently omitting its
    engineering model is the worse outcome.
    """
    try:
        check_python()
        root = project_root()
        version = extension_version()
        identity = runtime_identity()
        runtime_dir = ensure_runtime(root, version, identity)
        run_quarto_pre_render = load_pre_render(site_packages(runtime_dir))
    except BootstrapError as error:
        print(f"Quarto-Needs: {error}", file=sys.stderr)
        return 1
    return run_quarto_pre_render(root)


if __name__ == "__main__":
    raise SystemExit(main())
