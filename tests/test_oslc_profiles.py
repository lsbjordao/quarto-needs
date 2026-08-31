from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.oslc_profiles import OslcProfileError, load_oslc_profiles


def test_load_named_oslc_profile_with_bounded_secret_free_settings(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs-oslc.toml").write_text(
        """
[profiles.production]
service-provider-uri = "https://provider.test/oslc/sp/1"
cache-dir = ".quarto-needs/oslc/production"
max-age-seconds = 7200
allow-stale = true
timeout-seconds = 4.5
max-bytes = 500000
max-redirects = 1
max-nodes = 800
fetch-shapes = false
bearer-token-env = "QUARTO_NEEDS_OSLC_PROD_TOKEN"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    profiles = load_oslc_profiles(tmp_path)
    profile = profiles["production"]

    assert profile.service_provider_uri == "https://provider.test/oslc/sp/1"
    assert profile.cache_dir == ".quarto-needs/oslc/production"
    assert profile.max_age_seconds == 7200
    assert profile.allow_stale is True
    assert profile.timeout_seconds == 4.5
    assert profile.max_bytes == 500000
    assert profile.max_redirects == 1
    assert profile.max_nodes == 800
    assert profile.fetch_shapes is False
    assert profile.bearer_token_env == "QUARTO_NEEDS_OSLC_PROD_TOKEN"
    assert "token" not in profile.to_dict()


def test_oslc_profiles_are_sorted_and_defaults_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs-oslc.toml").write_text(
        """
[profiles.zeta]
service-provider-uri = "https://zeta.test/oslc/sp"

[profiles.alpha]
service-provider-uri = "https://alpha.test/oslc/sp"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    profiles = load_oslc_profiles(tmp_path)
    assert list(profiles) == ["alpha", "zeta"]
    assert profiles["alpha"].cache_dir == ".quarto-needs/oslc-cache"
    assert profiles["alpha"].max_age_seconds == 3600
    assert profiles["alpha"].fetch_shapes is True


def test_oslc_profile_rejects_unknown_keys_and_secret_values(tmp_path: Path) -> None:
    path = tmp_path / ".quarto-needs-oslc.toml"
    path.write_text(
        """
[profiles.bad]
service-provider-uri = "https://provider.test/oslc/sp"
bearer-token = "must-never-be-stored-here"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(OslcProfileError, match="unknown keys: bearer-token"):
        load_oslc_profiles(tmp_path)


def test_oslc_profile_rejects_invalid_budgets_and_top_level_keys(tmp_path: Path) -> None:
    path = tmp_path / ".quarto-needs-oslc.toml"
    path.write_text(
        """
[profiles.bad]
service-provider-uri = "https://provider.test/oslc/sp"
max-bytes = 0
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(OslcProfileError, match="max-bytes must be a positive integer"):
        load_oslc_profiles(tmp_path)

    path.write_text(
        """
[profiles.good]
service-provider-uri = "https://provider.test/oslc/sp"

[credentials]
token = "secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(OslcProfileError, match="unknown top-level keys: credentials"):
        load_oslc_profiles(tmp_path)
