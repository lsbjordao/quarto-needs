from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

OSLC_CONFIG_FILENAME = ".quarto-needs-oslc.toml"


class OslcProfileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OslcFederationProfile:
    name: str
    service_provider_uri: str
    cache_dir: str = ".quarto-needs/oslc-cache"
    max_age_seconds: int = 3600
    allow_stale: bool = False
    timeout_seconds: float = 10.0
    max_bytes: int = 2_000_000
    max_redirects: int = 3
    max_nodes: int = 5_000
    fetch_shapes: bool = True
    bearer_token_env: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "service-provider-uri": self.service_provider_uri,
            "cache-dir": self.cache_dir,
            "max-age-seconds": self.max_age_seconds,
            "allow-stale": self.allow_stale,
            "timeout-seconds": self.timeout_seconds,
            "max-bytes": self.max_bytes,
            "max-redirects": self.max_redirects,
            "max-nodes": self.max_nodes,
            "fetch-shapes": self.fetch_shapes,
            "bearer-token-env": self.bearer_token_env,
        }


def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OslcProfileError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_int(value: object, field: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise OslcProfileError(f"{field} must be a {qualifier} integer")
    return value


def _positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise OslcProfileError(f"{field} must be a positive number")
    return float(value)


def _parse_profile(name: str, raw: object) -> OslcFederationProfile:
    if not isinstance(raw, dict):
        raise OslcProfileError(f"[profiles.{name}] must be a table")
    allowed = {
        "service-provider-uri",
        "cache-dir",
        "max-age-seconds",
        "allow-stale",
        "timeout-seconds",
        "max-bytes",
        "max-redirects",
        "max-nodes",
        "fetch-shapes",
        "bearer-token-env",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise OslcProfileError(
            f"[profiles.{name}] has unknown keys: {', '.join(unknown)}"
        )
    if "service-provider-uri" not in raw:
        raise OslcProfileError(
            f"[profiles.{name}] service-provider-uri is required"
        )
    allow_stale = raw.get("allow-stale", False)
    fetch_shapes = raw.get("fetch-shapes", True)
    if not isinstance(allow_stale, bool):
        raise OslcProfileError(f"[profiles.{name}] allow-stale must be a boolean")
    if not isinstance(fetch_shapes, bool):
        raise OslcProfileError(f"[profiles.{name}] fetch-shapes must be a boolean")
    token_env = raw.get("bearer-token-env")
    if token_env is not None:
        token_env = _non_empty_string(token_env, f"[profiles.{name}] bearer-token-env")

    return OslcFederationProfile(
        name=name,
        service_provider_uri=_non_empty_string(
            raw["service-provider-uri"],
            f"[profiles.{name}] service-provider-uri",
        ),
        cache_dir=_non_empty_string(
            raw.get("cache-dir", ".quarto-needs/oslc-cache"),
            f"[profiles.{name}] cache-dir",
        ),
        max_age_seconds=_positive_int(
            raw.get("max-age-seconds", 3600),
            f"[profiles.{name}] max-age-seconds",
            allow_zero=True,
        ),
        allow_stale=allow_stale,
        timeout_seconds=_positive_number(
            raw.get("timeout-seconds", 10.0),
            f"[profiles.{name}] timeout-seconds",
        ),
        max_bytes=_positive_int(
            raw.get("max-bytes", 2_000_000),
            f"[profiles.{name}] max-bytes",
        ),
        max_redirects=_positive_int(
            raw.get("max-redirects", 3),
            f"[profiles.{name}] max-redirects",
            allow_zero=True,
        ),
        max_nodes=_positive_int(
            raw.get("max-nodes", 5_000),
            f"[profiles.{name}] max-nodes",
        ),
        fetch_shapes=fetch_shapes,
        bearer_token_env=token_env,
    )


def load_oslc_profiles(root: Path) -> Mapping[str, OslcFederationProfile]:
    path = root / OSLC_CONFIG_FILENAME
    if not path.exists():
        return MappingProxyType({})
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise OslcProfileError(f"{OSLC_CONFIG_FILENAME} is not valid TOML: {error}") from error

    if set(document) != {"profiles"}:
        unknown = sorted(set(document) - {"profiles"})
        if unknown:
            raise OslcProfileError(
                f"{OSLC_CONFIG_FILENAME} has unknown top-level keys: {', '.join(unknown)}"
            )
        raise OslcProfileError(f"{OSLC_CONFIG_FILENAME} must define [profiles.*]")
    raw_profiles = document["profiles"]
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise OslcProfileError("[profiles] must contain at least one named profile")

    profiles: dict[str, OslcFederationProfile] = {}
    for name, raw in raw_profiles.items():
        if not isinstance(name, str) or not name.strip():
            raise OslcProfileError("OSLC profile names must be non-empty strings")
        normalized_name = name.strip()
        profiles[normalized_name] = _parse_profile(normalized_name, raw)
    return MappingProxyType(dict(sorted(profiles.items())))
