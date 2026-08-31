from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .oslc_federation import OslcDiscoveryResult, discover_oslc_rm
from .oslc_http import HttpFetchPolicy, OslcTransportError
from .oslc_rdf import OslcRdfError
from .oslc_rm import CachePolicy


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs oslc discover",
        description="Discover one OSLC RM Service Provider through the bounded read-only federation adapter.",
    )
    parser.add_argument("service_provider_uri")
    parser.add_argument("--root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--cache-dir", default=".quarto-needs/oslc-cache")
    parser.add_argument("--max-age-seconds", type=int, default=3600)
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
    parser.add_argument("--max-redirects", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=5_000)
    parser.add_argument("--no-shapes", action="store_true")
    parser.add_argument(
        "--bearer-token-env",
        metavar="ENV_VAR",
        help="Read a bearer token from ENV_VAR. The token value is never persisted.",
    )
    parser.add_argument(
        "--now",
        help="Explicit ISO-8601 retrieval instant for reproducible testing; defaults to current UTC time.",
    )
    return parser


def _strip_dispatch_tokens(argv: Sequence[str]) -> list[str]:
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
            if index < len(values) and values[index] == "discover":
                index += 1
            continue
        result.append(value)
        index += 1
    return result


def _now(value: str | None) -> str:
    if value:
        # CachePolicy performs the canonical timezone-aware validation.
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
                        "valueShape": prop.value_shape,
                    }
                    for prop in discovered.shape.properties
                ],
            }
            for discovered in result.resource_shapes
        ],
    }


def _print_text(result: OslcDiscoveryResult) -> None:
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


def run_oslc_action(root: Path, argv: Sequence[str], action: str) -> int:
    if action != "discover":
        if not action:
            print("OSLC action required: discover", file=sys.stderr)
        else:
            print(f"Unknown OSLC action: {action}", file=sys.stderr)
        return 2

    parser = _parser()
    try:
        args = parser.parse_args(_strip_dispatch_tokens(argv))
        cache_policy = CachePolicy(
            max_age_seconds=args.max_age_seconds,
            allow_stale=args.allow_stale,
        )
        fetch_policy = HttpFetchPolicy(
            timeout_seconds=args.timeout_seconds,
            max_bytes=args.max_bytes,
            max_redirects=args.max_redirects,
        )
        auth_headers = _auth_headers(args.bearer_token_env)
        result = discover_oslc_rm(
            service_provider_uri=args.service_provider_uri,
            cache_root=_cache_root(root, args.cache_dir),
            cache_policy=cache_policy,
            now=_now(args.now),
            fetch_policy=fetch_policy,
            auth_headers=auth_headers,
            max_nodes=args.max_nodes,
            fetch_shapes=not args.no_shapes,
        )
    except (ValueError, OslcRdfError) as error:
        print(f"OSLC configuration/data error: {error}", file=sys.stderr)
        return 2
    except OslcTransportError as error:
        print(f"OSLC transport error [{error.code}]: {error}", file=sys.stderr)
        return 3
    except OSError as error:
        print(f"OSLC cache I/O error: {error}", file=sys.stderr)
        return 3

    if args.format == "json":
        print(json.dumps(discovery_to_dict(result), indent=2, sort_keys=True))
    else:
        _print_text(result)
    return 0
