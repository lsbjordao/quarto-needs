from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .oslc_catalog import OslcCatalogResult, discover_oslc_catalog
from .oslc_federation import OslcDiscoveryResult, discover_oslc_rm
from .oslc_http import HttpFetchPolicy, OslcTransportError
from .oslc_profiles import OslcFederationProfile, OslcProfileError, load_oslc_profiles
from .oslc_query import OslcQueryResult, execute_oslc_query
from .oslc_rdf import OslcRdfError
from .oslc_rm import CachePolicy


@dataclass(frozen=True, slots=True)
class _ResolvedDiscovery:
    service_provider_uri: str
    cache_dir: str
    max_age_seconds: int
    allow_stale: bool
    timeout_seconds: float
    max_bytes: int
    max_redirects: int
    max_nodes: int
    fetch_shapes: bool
    bearer_token_env: str | None


@dataclass(frozen=True, slots=True)
class _ResolvedQuery:
    service_provider_uri: str
    cache_dir: str
    max_age_seconds: int
    allow_stale: bool
    timeout_seconds: float
    max_bytes: int
    max_redirects: int
    max_nodes: int
    max_members: int
    bearer_token_env: str | None


def oslc_action(argv: Sequence[str]) -> str | None:
    values = list(argv)
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--root":
            index += 2
            continue
        if value.startswith("--root="):
            index += 1
            continue
        if value.startswith("-"):
            index += 1
            continue
        if value != "oslc":
            return None
        if index + 1 >= len(values):
            return ""
        return values[index + 1]
    return None


def _discover_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs oslc discover",
        description="Discover one OSLC RM Service Provider through the bounded read-only federation adapter.",
    )
    parser.add_argument("service_provider_uri", nargs="?")
    parser.add_argument("--profile", help="Named OSLC profile from .quarto-needs.toml")
    _add_common_options(parser)
    parser.add_argument("--no-shapes", dest="fetch_shapes", action="store_false", default=None)
    parser.add_argument("--shapes", dest="fetch_shapes", action="store_true")
    return parser


def _catalog_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs oslc catalog",
        description="Inspect one OSLC Service Provider Catalog without recursively crawling nested catalogs.",
    )
    parser.add_argument("catalog_uri")
    _add_common_options(parser)
    parser.add_argument("--max-providers", type=int, default=200)
    parser.add_argument("--max-nested-catalogs", type=int, default=50)
    return parser


def _query_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs oslc query",
        description=(
            "Execute one bounded GET against an explicitly selected OSLC Query Capability. "
            "Member URIs are reported but are never recursively fetched."
        ),
    )
    parser.add_argument("query_base_uri")
    parser.add_argument("--profile", help="Named OSLC profile from .quarto-needs.toml")
    parser.add_argument(
        "--service-provider-uri",
        help="Service Provider identity when no named profile is used",
    )
    _add_common_options(parser)
    parser.add_argument("--max-members", type=int, default=None)
    return parser


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--cache-dir")
    parser.add_argument("--max-age-seconds", type=int)
    parser.add_argument("--allow-stale", dest="allow_stale", action="store_true", default=None)
    parser.add_argument("--disallow-stale", dest="allow_stale", action="store_false")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--max-redirects", type=int)
    parser.add_argument("--max-nodes", type=int)
    parser.add_argument(
        "--bearer-token-env",
        metavar="ENV_VAR",
        help="Read a bearer token from ENV_VAR. The token value is never persisted.",
    )
    parser.add_argument(
        "--now",
        help="Explicit ISO-8601 retrieval instant for reproducible testing; defaults to current UTC time.",
    )


def _strip_dispatch_tokens(argv: Sequence[str], action: str) -> list[str]:
    values = list(argv)
    result: list[str] = []
    skipped_command = False
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--root":
            result.extend(values[index : index + 2])
            index += 2
            continue
        if value.startswith("--root="):
            result.append(value)
            index += 1
            continue
        if not skipped_command and value == "oslc":
            skipped_command = True
            index += 1
            if index < len(values) and values[index] == action:
                index += 1
            continue
        result.append(value)
        index += 1
    return result


def _now(value: str | None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cache_root(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _auth_headers(env_name: str | None) -> dict[str, str] | None:
    if not env_name:
        return None
    token = os.environ.get(env_name)
    if token is None or not token.strip():
        raise ValueError(f"environment variable {env_name!r} is unset or empty")
    return {"Authorization": f"Bearer {token.strip()}"}


def _value(cli_value, profile_value, default):
    if cli_value is not None:
        return cli_value
    if profile_value is not None:
        return profile_value
    return default


def _profile(root: Path, name: str | None) -> OslcFederationProfile | None:
    if not name:
        return None
    profiles = load_oslc_profiles(root)
    try:
        return profiles[name]
    except KeyError as error:
        available = ", ".join(sorted(profiles)) or "none"
        raise ValueError(
            f"unknown OSLC profile {name!r} (available: {available})"
        ) from error


def _resolve_discovery(root: Path, args: argparse.Namespace) -> _ResolvedDiscovery:
    if args.profile and args.service_provider_uri:
        raise ValueError("provide either a Service Provider URI or --profile, not both")
    if not args.profile and not args.service_provider_uri:
        raise ValueError("a Service Provider URI or --profile is required")

    profile = _profile(root, args.profile)
    return _ResolvedDiscovery(
        service_provider_uri=(
            profile.service_provider_uri if profile is not None else args.service_provider_uri
        ),
        cache_dir=_value(args.cache_dir, profile.cache_dir if profile else None, ".quarto-needs/oslc-cache"),
        max_age_seconds=_value(args.max_age_seconds, profile.max_age_seconds if profile else None, 3600),
        allow_stale=_value(args.allow_stale, profile.allow_stale if profile else None, False),
        timeout_seconds=_value(args.timeout_seconds, profile.timeout_seconds if profile else None, 10.0),
        max_bytes=_value(args.max_bytes, profile.max_bytes if profile else None, 2_000_000),
        max_redirects=_value(args.max_redirects, profile.max_redirects if profile else None, 3),
        max_nodes=_value(args.max_nodes, profile.max_nodes if profile else None, 5_000),
        fetch_shapes=_value(args.fetch_shapes, profile.fetch_shapes if profile else None, True),
        bearer_token_env=_value(args.bearer_token_env, profile.bearer_token_env if profile else None, None),
    )


def _resolve_query(root: Path, args: argparse.Namespace) -> _ResolvedQuery:
    if args.profile and args.service_provider_uri:
        raise ValueError("provide either --service-provider-uri or --profile, not both")
    if not args.profile and not args.service_provider_uri:
        raise ValueError("--service-provider-uri or --profile is required")
    profile = _profile(root, args.profile)
    max_members = _value(args.max_members, None, 1_000)
    if max_members < 1:
        raise ValueError("--max-members must be at least 1")
    return _ResolvedQuery(
        service_provider_uri=(
            profile.service_provider_uri if profile is not None else args.service_provider_uri
        ),
        cache_dir=_value(args.cache_dir, profile.cache_dir if profile else None, ".quarto-needs/oslc-cache"),
        max_age_seconds=_value(args.max_age_seconds, profile.max_age_seconds if profile else None, 3600),
        allow_stale=_value(args.allow_stale, profile.allow_stale if profile else None, False),
        timeout_seconds=_value(args.timeout_seconds, profile.timeout_seconds if profile else None, 10.0),
        max_bytes=_value(args.max_bytes, profile.max_bytes if profile else None, 2_000_000),
        max_redirects=_value(args.max_redirects, profile.max_redirects if profile else None, 3),
        max_nodes=_value(args.max_nodes, profile.max_nodes if profile else None, 5_000),
        max_members=max_members,
        bearer_token_env=_value(args.bearer_token_env, profile.bearer_token_env if profile else None, None),
    )


def _common_direct_values(args: argparse.Namespace) -> tuple[CachePolicy, HttpFetchPolicy, int, str, dict[str, str] | None]:
    cache_policy = CachePolicy(
        max_age_seconds=_value(args.max_age_seconds, None, 3600),
        allow_stale=_value(args.allow_stale, None, False),
    )
    fetch_policy = HttpFetchPolicy(
        timeout_seconds=_value(args.timeout_seconds, None, 10.0),
        max_bytes=_value(args.max_bytes, None, 2_000_000),
        max_redirects=_value(args.max_redirects, None, 3),
    )
    return (
        cache_policy,
        fetch_policy,
        _value(args.max_nodes, None, 5_000),
        _value(args.cache_dir, None, ".quarto-needs/oslc-cache"),
        _auth_headers(args.bearer_token_env),
    )


def discovery_to_dict(result: OslcDiscoveryResult) -> dict[str, object]:
    return {
        "schema": "oslc-discovery-v1",
        "serviceProviderUri": result.service_provider_uri,
        "providerFetchSource": result.provider_fetch_source,
        "services": [
            {
                "serviceId": service.service_id,
                "queryCapabilities": [
                    {
                        "queryBaseUri": query.query_base_uri,
                        "resourceShapeUri": query.resource_shape_uri,
                        "resourceTypes": list(query.resource_types),
                    }
                    for query in service.query_capabilities
                ],
            }
            for service in result.services
        ],
        "resourceShapes": [
            {
                "uri": discovered.uri,
                "fetchSource": discovered.fetch_source,
                "describes": list(discovered.shape.describes),
                "properties": [
                    {
                        "name": prop.name,
                        "occurs": prop.occurs,
                        "propertyDefinition": prop.property_definition,
                        "valueType": prop.value_type,
                        "ranges": list(prop.ranges),
                        "readOnly": prop.read_only,
                        "representation": prop.representation,
                        "valueShapes": list(prop.value_shapes),
                    }
                    for prop in discovered.shape.properties
                ],
            }
            for discovered in result.resource_shapes
        ],
    }


def catalog_to_dict(result: OslcCatalogResult) -> dict[str, object]:
    return {
        "schema": "oslc-catalog-v1",
        "catalogUri": result.catalog_uri,
        "fetchSource": result.fetch_source,
        "serviceProviderUris": list(result.service_provider_uris),
        "nestedCatalogUris": list(result.nested_catalog_uris),
    }


def _print_discovery_text(result: OslcDiscoveryResult) -> None:
    print(f"OSLC RM Service Provider: {result.service_provider_uri}")
    print(f"Provider source: {result.provider_fetch_source}")
    print(f"RM services: {len(result.services)}")
    for service in result.services:
        print(f"- service: {service.service_id or '(blank node)'}")
        for query in service.query_capabilities:
            print(f"  query-base: {query.query_base_uri}")
            if query.resource_shape_uri:
                print(f"  resource-shape: {query.resource_shape_uri}")
            if query.resource_types:
                print(f"  resource-types: {', '.join(query.resource_types)}")
    print(f"Resource Shapes: {len(result.resource_shapes)}")
    for discovered in result.resource_shapes:
        print(
            f"- {discovered.uri} ({discovered.fetch_source}): "
            f"{len(discovered.shape.properties)} propertie(s)"
        )


def _print_catalog_text(result: OslcCatalogResult) -> None:
    print(f"OSLC Service Provider Catalog: {result.catalog_uri}")
    print(f"Catalog source: {result.fetch_source}")
    print(f"Service Providers: {len(result.service_provider_uris)}")
    for uri in result.service_provider_uris:
        print(f"- {uri}")
    print(f"Nested catalogs: {len(result.nested_catalog_uris)}")
    for uri in result.nested_catalog_uris:
        print(f"- {uri}")
    if result.nested_catalog_uris:
        print("Nested catalogs are reported but not followed automatically.")


def _print_query_text(result: OslcQueryResult) -> None:
    print(f"OSLC Query Base: {result.query_base_uri}")
    print(f"Query source: {result.fetch_source}")
    print(f"Response digest: {result.response_digest}")
    print(f"Members: {len(result.members)}")
    for member in result.members:
        suffix = " (inline)" if member.is_inline else ""
        print(f"- {member.resource_uri}{suffix}")


def _run_discover(root: Path, argv: Sequence[str]) -> int:
    args = _discover_parser().parse_args(_strip_dispatch_tokens(argv, "discover"))
    resolved = _resolve_discovery(root, args)
    result = discover_oslc_rm(
        service_provider_uri=resolved.service_provider_uri,
        cache_root=_cache_root(root, resolved.cache_dir),
        cache_policy=CachePolicy(resolved.max_age_seconds, resolved.allow_stale),
        now=_now(args.now),
        fetch_policy=HttpFetchPolicy(
            resolved.timeout_seconds,
            resolved.max_bytes,
            resolved.max_redirects,
        ),
        auth_headers=_auth_headers(resolved.bearer_token_env),
        max_nodes=resolved.max_nodes,
        fetch_shapes=resolved.fetch_shapes,
    )
    if args.format == "json":
        print(json.dumps(discovery_to_dict(result), indent=2, sort_keys=True))
    else:
        _print_discovery_text(result)
    return 0


def _run_catalog(root: Path, argv: Sequence[str]) -> int:
    args = _catalog_parser().parse_args(_strip_dispatch_tokens(argv, "catalog"))
    cache_policy, fetch_policy, max_nodes, cache_dir, auth_headers = _common_direct_values(args)
    result = discover_oslc_catalog(
        catalog_uri=args.catalog_uri,
        cache_root=_cache_root(root, cache_dir),
        cache_policy=cache_policy,
        now=_now(args.now),
        fetch_policy=fetch_policy,
        auth_headers=auth_headers,
        max_nodes=max_nodes,
        max_providers=args.max_providers,
        max_nested_catalogs=args.max_nested_catalogs,
    )
    if args.format == "json":
        print(json.dumps(catalog_to_dict(result), indent=2, sort_keys=True))
    else:
        _print_catalog_text(result)
    return 0


def _run_query(root: Path, argv: Sequence[str]) -> int:
    args = _query_parser().parse_args(_strip_dispatch_tokens(argv, "query"))
    resolved = _resolve_query(root, args)
    result = execute_oslc_query(
        query_base_uri=args.query_base_uri,
        service_provider_uri=resolved.service_provider_uri,
        cache_root=_cache_root(root, resolved.cache_dir),
        cache_policy=CachePolicy(resolved.max_age_seconds, resolved.allow_stale),
        now=_now(args.now),
        fetch_policy=HttpFetchPolicy(
            resolved.timeout_seconds,
            resolved.max_bytes,
            resolved.max_redirects,
        ),
        auth_headers=_auth_headers(resolved.bearer_token_env),
        max_nodes=resolved.max_nodes,
        max_members=resolved.max_members,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        _print_query_text(result)
    return 0


def run_oslc_action(root: Path, argv: Sequence[str], action: str) -> int:
    if action not in {"discover", "catalog", "query"}:
        if not action:
            print("OSLC action required: discover, catalog, or query", file=sys.stderr)
        else:
            print(f"Unknown OSLC action: {action}", file=sys.stderr)
        return 2

    try:
        if action == "discover":
            return _run_discover(root, argv)
        if action == "catalog":
            return _run_catalog(root, argv)
        return _run_query(root, argv)
    except (ValueError, OslcProfileError, OslcRdfError) as error:
        print(f"OSLC configuration/data error: {error}", file=sys.stderr)
        return 2
    except OslcTransportError as error:
        print(f"OSLC transport error [{error.code}]: {error}", file=sys.stderr)
        return 3
    except OSError as error:
        print(f"OSLC cache I/O error: {error}", file=sys.stderr)
        return 3
