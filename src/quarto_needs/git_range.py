"""Deterministic materialization of engineering states from Git commit ranges.

Git-range analysis never infers engineering semantics from a textual patch. Both
committed states are exported into isolated temporary directories and passed
through the normal Quarto-Needs parser/configuration/analysis pipeline.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator

from .analysis import analyze_project
from .baseline import build_baseline
from .config import NeedsConfig, load_config
from .queries import materialize_queries
from .snapshot import AnalysisSnapshot


class GitRangeError(RuntimeError):
    """A Git range cannot be resolved or safely materialized."""


@dataclass(frozen=True, slots=True)
class GitRangeStates:
    range_spec: str
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    reference_epoch: int
    base_snapshot: AnalysisSnapshot
    base_config: NeedsConfig
    base_baseline: dict[str, object]
    head_snapshot: AnalysisSnapshot
    head_config: NeedsConfig


def parse_git_range(spec: str) -> tuple[str, str]:
    """Parse the supported two-dot commit range syntax ``base..head``."""
    text = spec.strip()
    if "..." in text or text.count("..") != 1:
        raise GitRangeError("Git range must use exactly one two-dot form: BASE..HEAD")
    base, head = (part.strip() for part in text.split("..", 1))
    if not base or not head:
        raise GitRangeError("Git range must provide both BASE and HEAD")
    return base, head


def _git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        raise GitRangeError(f"Could not execute git: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise GitRangeError(detail)
    return completed.stdout.strip()


def repository_root(project_root: Path) -> tuple[Path, Path]:
    """Return repository root and the project root relative to that repository."""
    root = Path(project_root).resolve()
    repo_text = _git(root, "rev-parse", "--show-toplevel")
    repo = Path(repo_text).resolve()
    try:
        relative = root.relative_to(repo)
    except ValueError as error:  # pragma: no cover - git itself should prevent this
        raise GitRangeError(f"Project root {root} is not inside Git repository {repo}") from error
    return repo, relative


def resolve_commit(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def commit_epoch(repo: Path, commit_sha: str) -> int:
    raw = _git(repo, "show", "-s", "--format=%ct", commit_sha)
    try:
        value = int(raw)
    except ValueError as error:
        raise GitRangeError(f"Git returned an invalid commit timestamp for {commit_sha}: {raw!r}") from error
    if value < 0:
        raise GitRangeError(f"Git returned a negative commit timestamp for {commit_sha}")
    return value


def _safe_target(root: Path, member_name: str) -> Path:
    pure = PurePosixPath(member_name)
    if pure.is_absolute() or ".." in pure.parts:
        raise GitRangeError(f"Git archive contains unsafe path {member_name!r}")
    target = root.joinpath(*pure.parts)
    resolved_parent = target.parent.resolve(strict=False)
    try:
        resolved_parent.relative_to(root.resolve())
    except ValueError as error:
        raise GitRangeError(f"Git archive path escapes extraction root: {member_name!r}") from error
    return target


def _safe_link_target(root: Path, target: Path, link_name: str, member_name: str) -> Path:
    pure = PurePosixPath(link_name)
    if pure.is_absolute():
        raise GitRangeError(f"Git archive symlink {member_name!r} has an absolute target")
    resolved = (target.parent / Path(*pure.parts)).resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise GitRangeError(f"Git archive symlink {member_name!r} escapes extraction root") from error
    return resolved


def _extract_archive(archive: Path, destination: Path) -> None:
    """Extract a Git-produced tar without trusting tarfile path/link handling."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:") as bundle:
        for member in bundle:
            target = _safe_target(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            # Refuse writes through a symlink introduced by an earlier member.
            resolved_parent = target.parent.resolve(strict=False)
            try:
                resolved_parent.relative_to(destination.resolve())
            except ValueError as error:
                raise GitRangeError(f"Git archive member escapes through a symlink: {member.name!r}") from error

            if member.isfile():
                source = bundle.extractfile(member)
                if source is None:
                    raise GitRangeError(f"Could not read Git archive member {member.name!r}")
                with source, target.open("wb") as stream:
                    shutil.copyfileobj(source, stream)
                mode = stat.S_IMODE(member.mode)
                if mode:
                    target.chmod(mode)
                continue

            if member.issym():
                _safe_link_target(destination, target, member.linkname, member.name)
                try:
                    target.symlink_to(member.linkname)
                except OSError as error:
                    raise GitRangeError(f"Could not create archived symlink {member.name!r}: {error}") from error
                continue

            # Git archives should not need hard links, devices, or FIFOs. Reject
            # them instead of broadening the extraction trust boundary.
            raise GitRangeError(f"Git archive contains unsupported member type: {member.name!r}")


def _archive_commit(repo: Path, commit_sha: str, destination: Path) -> None:
    archive_path = destination.parent / f"{destination.name}.tar"
    try:
        with archive_path.open("wb") as stream:
            completed = subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", commit_sha],
                check=False,
                stdout=stream,
                stderr=subprocess.PIPE,
            )
    except OSError as error:
        raise GitRangeError(f"Could not materialize Git commit {commit_sha}: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip() or "git archive failed"
        raise GitRangeError(detail)
    try:
        _extract_archive(archive_path, destination)
    finally:
        try:
            archive_path.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _reference_epoch(epoch: int) -> Iterator[None]:
    previous = os.environ.get("SOURCE_DATE_EPOCH")
    os.environ["SOURCE_DATE_EPOCH"] = str(epoch)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = previous


def _analyze_materialized(project_root: Path, *, reference_epoch: int) -> tuple[NeedsConfig, AnalysisSnapshot]:
    with _reference_epoch(reference_epoch):
        try:
            config = load_config(project_root)
            result = analyze_project(project_root, config=config)
        except OSError as error:
            raise GitRangeError(f"Could not analyze materialized project {project_root}: {error}") from error
    if result.snapshot is None:
        errors = [finding for finding in result.findings if finding.severity == "error"]
        detail = "; ".join(f"{finding.code}: {finding.message}" for finding in errors[:5])
        suffix = f" ({detail})" if detail else ""
        raise GitRangeError(f"Materialized Git state is structurally invalid: {project_root}{suffix}")
    return config, result.snapshot


def materialize_git_range(project_root: Path, range_spec: str) -> GitRangeStates:
    """Resolve, export, and analyze both committed engineering states."""
    base_ref, head_ref = parse_git_range(range_spec)
    repo, relative_project = repository_root(project_root)
    base_sha = resolve_commit(repo, base_ref)
    head_sha = resolve_commit(repo, head_ref)
    epoch = commit_epoch(repo, head_sha)

    with tempfile.TemporaryDirectory(prefix="quarto-needs-git-") as temporary:
        temporary_root = Path(temporary)
        base_tree = temporary_root / "base"
        head_tree = temporary_root / "head"
        _archive_commit(repo, base_sha, base_tree)
        _archive_commit(repo, head_sha, head_tree)
        base_project = base_tree / relative_project
        head_project = head_tree / relative_project
        if not base_project.is_dir():
            raise GitRangeError(
                f"Project path {relative_project} does not exist as a directory in base ref {base_ref}"
            )
        if not head_project.is_dir():
            raise GitRangeError(
                f"Project path {relative_project} does not exist as a directory in head ref {head_ref}"
            )

        base_config, base_snapshot = _analyze_materialized(base_project, reference_epoch=epoch)
        head_config, head_snapshot = _analyze_materialized(head_project, reference_epoch=epoch)
        base_queries = materialize_queries(base_config, base_snapshot)
        baseline = build_baseline(base_snapshot, base_config, queries=base_queries)

        # The returned snapshots/baseline contain immutable data only; source
        # files are no longer needed after analysis, so the temporary trees can
        # disappear at context exit.
        return GitRangeStates(
            range_spec=range_spec,
            base_ref=base_ref,
            head_ref=head_ref,
            base_sha=base_sha,
            head_sha=head_sha,
            reference_epoch=epoch,
            base_snapshot=base_snapshot,
            base_config=base_config,
            base_baseline=baseline,
            head_snapshot=head_snapshot,
            head_config=head_config,
        )
