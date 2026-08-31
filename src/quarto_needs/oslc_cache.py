from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .oslc_rm import CacheDecision, CachePolicy, ExternalResourceIdentity, content_digest

OSLC_CACHE_SCHEMA = "oslc-cache-v1"


@dataclass(frozen=True, slots=True)
class CachedRepresentation:
    identity: ExternalResourceIdentity
    media_type: str

    def __post_init__(self) -> None:
        media_type = self.media_type.strip().lower()
        if not media_type or "/" not in media_type:
            raise ValueError("media_type must be a non-empty MIME type")
        object.__setattr__(self, "media_type", media_type)

    def to_dict(self) -> dict[str, object]:
        result = self.identity.to_dict()
        result["mediaType"] = self.media_type
        return result


@dataclass(frozen=True, slots=True)
class CacheSelection:
    representation: CachedRepresentation
    payload: bytes
    decision: CacheDecision


def _identity_from_dict(value: object) -> ExternalResourceIdentity:
    if not isinstance(value, dict):
        raise ValueError("OSLC cache entry must be an object")

    required = {
        "resourceUri",
        "serviceProviderUri",
        "digest",
        "fetchedAt",
        "trustState",
        "mediaType",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"OSLC cache entry missing fields: {', '.join(missing)}")

    allowed = required | {"etag", "lastModified"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"OSLC cache entry has unknown fields: {', '.join(unknown)}")

    for field in required:
        if not isinstance(value[field], str):
            raise ValueError(f"OSLC cache field {field} must be a string")
    for field in ("etag", "lastModified"):
        if value.get(field) is not None and not isinstance(value[field], str):
            raise ValueError(f"OSLC cache field {field} must be a string or null")

    return ExternalResourceIdentity(
        resource_uri=value["resourceUri"],
        service_provider_uri=value["serviceProviderUri"],
        digest=value["digest"],
        fetched_at=value["fetchedAt"],
        trust_state=value["trustState"],  # type: ignore[arg-type]
        etag=value.get("etag"),
        last_modified=value.get("lastModified"),
    )


def _entry_from_dict(value: object) -> CachedRepresentation:
    identity = _identity_from_dict(value)
    assert isinstance(value, dict)
    media_type = value["mediaType"]
    assert isinstance(media_type, str)
    return CachedRepresentation(identity=identity, media_type=media_type)


def _entry_key(entry: CachedRepresentation) -> tuple[str, str, str]:
    return (
        entry.identity.resource_uri,
        entry.identity.digest,
        entry.identity.fetched_at,
    )


def _entry_sort_key(entry: CachedRepresentation) -> tuple[str, datetime, str]:
    return (
        entry.identity.resource_uri,
        _parsed_fetched_at(entry),
        entry.identity.digest,
    )


def _blob_path(root: Path, digest: str) -> Path:
    hex_digest = digest.removeprefix("sha256:")
    return root / "blobs" / f"{hex_digest}.bin"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_cache_manifest(root: Path) -> tuple[CachedRepresentation, ...]:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return ()
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read OSLC cache manifest: {error}") from error

    if not isinstance(document, dict):
        raise ValueError("OSLC cache manifest must be an object")
    if set(document) != {"schema", "entries"}:
        raise ValueError("OSLC cache manifest must contain only schema and entries")
    if document.get("schema") != OSLC_CACHE_SCHEMA:
        raise ValueError(f"unsupported OSLC cache schema: {document.get('schema')!r}")
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("OSLC cache manifest entries must be an array")

    entries = tuple(_entry_from_dict(value) for value in raw_entries)
    keys = [_entry_key(entry) for entry in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("OSLC cache manifest contains duplicate observations")
    return tuple(sorted(entries, key=_entry_sort_key))


def write_cache_manifest(root: Path, entries: tuple[CachedRepresentation, ...]) -> None:
    keys = [_entry_key(entry) for entry in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("OSLC cache manifest contains duplicate observations")
    document = {
        "schema": OSLC_CACHE_SCHEMA,
        "entries": [entry.to_dict() for entry in sorted(entries, key=_entry_sort_key)],
    }
    encoded = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    _atomic_write(root / "manifest.json", encoded)


def store_cached_representation(
    root: Path,
    representation: CachedRepresentation,
    payload: bytes,
) -> None:
    observed_digest = content_digest(payload)
    if observed_digest != representation.identity.digest:
        raise ValueError(
            "cached payload digest does not match ExternalResourceIdentity "
            f"({observed_digest} != {representation.identity.digest})"
        )

    blob_path = _blob_path(root, representation.identity.digest)
    if blob_path.exists():
        existing = blob_path.read_bytes()
        if content_digest(existing) != representation.identity.digest:
            raise ValueError("existing OSLC cache blob failed its content digest")
    else:
        _atomic_write(blob_path, payload)

    entries = list(load_cache_manifest(root))
    key = _entry_key(representation)
    if key not in {_entry_key(entry) for entry in entries}:
        entries.append(representation)
    write_cache_manifest(root, tuple(entries))


def read_cached_payload(root: Path, representation: CachedRepresentation) -> bytes:
    blob_path = _blob_path(root, representation.identity.digest)
    try:
        payload = blob_path.read_bytes()
    except OSError as error:
        raise ValueError(
            f"OSLC cache blob is unavailable for {representation.identity.digest}: {error}"
        ) from error
    if content_digest(payload) != representation.identity.digest:
        raise ValueError(
            f"OSLC cache blob failed digest validation for {representation.identity.resource_uri}"
        )
    return payload


def _parsed_fetched_at(entry: CachedRepresentation) -> datetime:
    value = entry.identity.fetched_at.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def latest_cached_representation(
    root: Path,
    *,
    resource_uri: str,
    include_rejected: bool = False,
) -> CachedRepresentation | None:
    candidates = [
        entry
        for entry in load_cache_manifest(root)
        if entry.identity.resource_uri == resource_uri
        and (include_rejected or entry.identity.trust_state != "rejected")
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda entry: (_parsed_fetched_at(entry), entry.identity.digest),
    )


def select_cached_representation(
    root: Path,
    *,
    resource_uri: str,
    policy: CachePolicy,
    now: str,
) -> CacheSelection | None:
    representation = latest_cached_representation(root, resource_uri=resource_uri)
    if representation is None:
        return None
    decision = policy.decide(representation.identity, now=now)
    if decision == "stale-rejected":
        return None
    return CacheSelection(
        representation=representation,
        payload=read_cached_payload(root, representation),
        decision=decision,
    )
