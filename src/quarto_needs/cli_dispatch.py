from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .analysis import analyze_project
from .cli import main as legacy_main
from .config import load_config
from .evidence import (
    EVIDENCE_ENVELOPE_SCHEMA_VERSION,
    EVIDENCE_KIND,
    evidence_digest,
    parse_evidence_time,
    validate_evidence_envelope,
)
from .evidence_validation import validate_check_evidence


def _root(argv: Sequence[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root")
    args, _ = parser.parse_known_args(list(argv))
    return Path(args.root or os.getcwd()).resolve()


def _format(argv: Sequence[str]) -> str:
    try:
        index = list(argv).index("--format")
    except ValueError:
        return "text"
    if index + 1 >= len(argv):
        return "text"
    return str(argv[index + 1])


def _evidence_artifact(argv: Sequence[str]) -> Path | None:
    values = list(argv)
    try:
        index = values.index("evidence")
    except ValueError:
        return None
    if index + 2 >= len(values) or values[index + 1] != "check":
        return None
    return Path(values[index + 2])


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def _generic_envelope(
    path: Path, document: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, object]] | None:
    if document.get("schemaVersion") != EVIDENCE_ENVELOPE_SCHEMA_VERSION:
        raise ValueError(
            f"{path} has unsupported evidence envelope schemaVersion {document.get('schemaVersion')!r}"
        )
    provider = document.get("provider")
    subject = document.get("subject")
    artifact = document.get("artifact")
    generated_at = document.get("generatedAt")
    expires_at = document.get("expiresAt")
    if not isinstance(provider, Mapping):
        raise ValueError(f"{path} has invalid envelope provider")
    if not isinstance(provider.get("name"), str) or not provider.get("name"):
        raise ValueError(f"{path} has invalid envelope provider name")
    if not isinstance(provider.get("version"), str) or not provider.get("version"):
        raise ValueError(f"{path} has invalid envelope provider version")
    if not isinstance(subject, Mapping):
        raise ValueError(f"{path} has invalid envelope subject")
    if not isinstance(generated_at, str) or parse_evidence_time(generated_at) is None:
        raise ValueError(f"{path} has invalid generatedAt")
    if expires_at is not None and (
        not isinstance(expires_at, str) or parse_evidence_time(expires_at) is None
    ):
        raise ValueError(f"{path} has invalid expiresAt")
    if not isinstance(artifact, Mapping):
        raise ValueError(f"{path} has invalid envelope artifact")
    if artifact.get("schema") != "evidence-checks-v1":
        return None
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{path} has invalid generic evidence payload")
    expected_digest = artifact.get("digest")
    if expected_digest != evidence_digest(payload):
        raise ValueError(f"{path} evidence payload digest does not match its envelope")
    return dict(document), payload


def _generic_document(path: Path) -> tuple[dict[str, object] | None, dict[str, object]] | None:
    document = _read_json_object(path)
    if document.get("kind") == EVIDENCE_KIND:
        return _generic_envelope(path, document)
    if isinstance(document.get("checks"), list):
        return None, document
    return None


def _shape_error(payload: Mapping[str, object]) -> str | None:
    if payload.get("schemaVersion") != "1":
        return f"unsupported generic evidence schemaVersion {payload.get('schemaVersion')!r}"
    if not isinstance(payload.get("provider"), str) or not payload.get("provider"):
        return "generic evidence has invalid provider"
    if not isinstance(payload.get("providerVersion"), str) or not payload.get("providerVersion"):
        return "generic evidence has invalid providerVersion"
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return "generic evidence has invalid checks array"
    for index, check in enumerate(checks):
        if not isinstance(check, Mapping):
            return f"generic evidence checks[{index}] must be an object"
        if not isinstance(check.get("id"), str) or not check.get("id"):
            return f"generic evidence checks[{index}] has invalid id"
        if check.get("outcome") not in {"passed", "failed", "skipped"}:
            return f"generic evidence checks[{index}] has invalid outcome {check.get('outcome')!r}"
        for key in ("requirements", "testCases", "evidenceObjects"):
            values = check.get(key)
            if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
                return f"generic evidence checks[{index}] has invalid {key}"
    return None


def _generic_evidence_check(argv: Sequence[str], artifact_arg: Path) -> int | None:
    root = _root(argv)
    artifact = artifact_arg if artifact_arg.is_absolute() else root / artifact_arg
    try:
        loaded = _generic_document(artifact)
    except ValueError as error:
        print(f"Evidence error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not read evidence artifact {artifact}: {error}", file=sys.stderr)
        return 3
    if loaded is None:
        return None
    envelope, payload = loaded
    shape_error = _shape_error(payload)
    if shape_error is not None:
        print(f"Evidence error: {shape_error}", file=sys.stderr)
        return 2

    try:
        config = load_config(root)
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    result = analyze_project(root, config=config)
    if result.snapshot is None:
        from .cli import print_findings

        print_findings(result.findings, stream=sys.stderr)
        return 1

    issues = []
    if envelope is not None:
        issues.extend(validate_evidence_envelope(result.snapshot, envelope))
    issues.extend(validate_check_evidence(result.snapshot, payload))
    issues = sorted(
        issues,
        key=lambda issue: (
            issue.code,
            (issue.object_id or "").casefold(),
            issue.object_id or "",
            (issue.nodeid or "").casefold(),
            issue.nodeid or "",
            issue.message,
        ),
    )
    projection = {
        "artifact": str(artifact),
        "provider": payload["provider"],
        "checks": len(payload["checks"]),
        "attested": envelope is not None,
        "valid": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }
    if _format(argv) == "json":
        print(json.dumps(projection, indent=2, sort_keys=True))
    elif issues:
        print(f"Evidence check failed: {len(issues)} issue(s)")
        for issue in issues:
            scope = ""
            if issue.object_id:
                scope += f" {issue.object_id}"
            if issue.nodeid:
                scope += f" [{issue.nodeid}]"
            print(f"[{issue.code}]{scope}: {issue.message}")
    else:
        attestation = "attested " if envelope is not None else ""
        print(
            f"Evidence check passed: {len(payload['checks'])} {attestation}machine check(s) "
            f"from {artifact} agree with the current engineering graph"
        )
    return 1 if issues else 0


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    artifact = _evidence_artifact(values)
    if artifact is not None:
        result = _generic_evidence_check(values, artifact)
        if result is not None:
            return result
    return legacy_main(values)


if __name__ == "__main__":
    raise SystemExit(main())
