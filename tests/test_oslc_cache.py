from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.oslc_cache import (
    CachedRepresentation,
    load_cache_manifest,
    read_cached_payload,
    select_cached_representation,
    store_cached_representation,
    write_cache_manifest,
)
from quarto_needs.oslc_rm import CachePolicy, ExternalResourceIdentity, content_digest


def _representation(
    payload: bytes,
    *,
    fetched_at: str,
    resource_uri: str = "https://provider.test/requirements/1",
    trust_state: str = "unverified",
) -> CachedRepresentation:
    return CachedRepresentation(
        identity=ExternalResourceIdentity(
            resource_uri=resource_uri,
            service_provider_uri="https://provider.test/oslc/sp/1",
            digest=content_digest(payload),
            fetched_at=fetched_at,
            trust_state=trust_state,  # type: ignore[arg-type]
            etag='"abc"',
            last_modified="Sun, 30 Aug 2026 20:00:00 GMT",
        ),
        media_type="Application/LD+JSON",
    )


def test_cache_persists_deterministic_manifest_and_content_addressed_blob(tmp_path: Path) -> None:
    payload = b'{"@id":"https://provider.test/requirements/1"}'
    representation = _representation(payload, fetched_at="2026-08-30T20:00:00Z")

    store_cached_representation(tmp_path, representation, payload)

    digest_hex = representation.identity.digest.removeprefix("sha256:")
    assert (tmp_path / "blobs" / f"{digest_hex}.bin").read_bytes() == payload
    assert read_cached_payload(tmp_path, representation) == payload

    manifest = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert manifest.endswith("\n")
    assert "Application/LD+JSON" not in manifest
    assert '"mediaType":"application/ld+json"' in manifest
    assert load_cache_manifest(tmp_path) == (representation,)

    # Re-storing the same observation is idempotent and byte-stable.
    before = manifest.encode("utf-8")
    store_cached_representation(tmp_path, representation, payload)
    assert (tmp_path / "manifest.json").read_bytes() == before


def test_cache_preserves_distinct_observations_for_same_resource(tmp_path: Path) -> None:
    old_payload = b"old"
    new_payload = b"new"
    old = _representation(old_payload, fetched_at="2026-08-30T20:00:00Z")
    new = _representation(new_payload, fetched_at="2026-08-30T21:00:00Z")

    store_cached_representation(tmp_path, new, new_payload)
    store_cached_representation(tmp_path, old, old_payload)

    entries = load_cache_manifest(tmp_path)
    assert [entry.identity.digest for entry in entries] == [
        old.identity.digest,
        new.identity.digest,
    ]

    selected = select_cached_representation(
        tmp_path,
        resource_uri=old.identity.resource_uri,
        policy=CachePolicy(max_age_seconds=7200),
        now="2026-08-30T21:30:00Z",
    )
    assert selected is not None
    assert selected.representation == new
    assert selected.payload == new_payload
    assert selected.decision == "fresh"


def test_cache_respects_stale_policy_and_rejected_trust(tmp_path: Path) -> None:
    stale_payload = b"stale"
    stale = _representation(stale_payload, fetched_at="2026-08-30T18:00:00Z")
    rejected_payload = b"rejected"
    rejected = _representation(
        rejected_payload,
        fetched_at="2026-08-30T21:00:00Z",
        trust_state="rejected",
    )
    store_cached_representation(tmp_path, stale, stale_payload)
    store_cached_representation(tmp_path, rejected, rejected_payload)

    assert (
        select_cached_representation(
            tmp_path,
            resource_uri=stale.identity.resource_uri,
            policy=CachePolicy(max_age_seconds=3600),
            now="2026-08-30T21:00:00Z",
        )
        is None
    )
    selected = select_cached_representation(
        tmp_path,
        resource_uri=stale.identity.resource_uri,
        policy=CachePolicy(max_age_seconds=3600, allow_stale=True),
        now="2026-08-30T21:00:00Z",
    )
    assert selected is not None
    assert selected.representation == stale
    assert selected.decision == "stale-allowed"


def test_cache_rejects_payload_or_blob_digest_mismatch(tmp_path: Path) -> None:
    payload = b"payload"
    representation = _representation(payload, fetched_at="2026-08-30T20:00:00Z")

    with pytest.raises(ValueError, match="does not match"):
        store_cached_representation(tmp_path, representation, b"tampered")

    store_cached_representation(tmp_path, representation, payload)
    digest_hex = representation.identity.digest.removeprefix("sha256:")
    (tmp_path / "blobs" / f"{digest_hex}.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="failed digest validation"):
        read_cached_payload(tmp_path, representation)


def test_cache_rejects_unknown_schema_duplicate_observations_and_unknown_fields(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": "future-cache-v9", "entries": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported OSLC cache schema"):
        load_cache_manifest(tmp_path)

    representation = _representation(b"payload", fetched_at="2026-08-30T20:00:00Z")
    entry = representation.to_dict()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": "oslc-cache-v1", "entries": [entry, entry]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate observations"):
        load_cache_manifest(tmp_path)

    bad_entry = dict(entry)
    bad_entry["secret"] = "must-not-be-persisted"
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": "oslc-cache-v1", "entries": [bad_entry]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown fields"):
        load_cache_manifest(tmp_path)


def test_cache_schema_is_a_parameter_not_a_hardcoded_oslc_constant(tmp_path: Path) -> None:
    """A non-OSLC caller (e.g. the GitHub adapter) stamps and reads its own schema.

    This is what makes reusing store_cached_representation/
    select_cached_representation for a different external source safe: a
    cache root written under one schema can never be silently read back (or
    silently overwritten) under a different one.
    """
    payload = b'{"number": 1}'
    representation = _representation(payload, fetched_at="2026-08-30T20:00:00Z")

    store_cached_representation(tmp_path, representation, payload, schema="github-cache-v1")

    document = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert document["schema"] == "github-cache-v1"

    # The default (OSLC) schema must not see entries written under another one.
    assert load_cache_manifest(tmp_path, schema="github-cache-v1") == (representation,)
    with pytest.raises(ValueError, match="unsupported OSLC cache schema"):
        load_cache_manifest(tmp_path)

    selection = select_cached_representation(
        tmp_path,
        resource_uri=representation.identity.resource_uri,
        policy=CachePolicy(max_age_seconds=3600),
        now="2026-08-30T20:30:00Z",
        schema="github-cache-v1",
    )
    assert selection is not None
    assert selection.decision == "fresh"


def test_write_cache_manifest_stamps_the_requested_schema(tmp_path: Path) -> None:
    write_cache_manifest(tmp_path, (), schema="github-cache-v1")
    document = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert document == {"schema": "github-cache-v1", "entries": []}
