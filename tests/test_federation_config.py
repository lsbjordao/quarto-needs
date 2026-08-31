from __future__ import annotations

from pathlib import Path

from quarto_needs.config import load_config
from quarto_needs.oslc_profiles import load_oslc_profiles


def test_federation_profiles_share_project_toml_without_changing_graph_config(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline"
    federated = tmp_path / "federated"
    baseline.mkdir()
    federated.mkdir()

    common = 'profile = "strict"\n[governance]\ntest-types = ["test-case"]\n'
    (baseline / ".quarto-needs.toml").write_text(common, encoding="utf-8")
    (federated / ".quarto-needs.toml").write_text(
        common
        + '\n[federation.oslc.profiles.production]\n'
        + 'service-provider-uri = "https://provider.test/oslc/sp/1"\n'
        + 'bearer-token-env = "QUARTO_NEEDS_OSLC_TOKEN"\n',
        encoding="utf-8",
    )

    baseline_config = load_config(baseline)
    federated_config = load_config(federated)

    # Read-only external access settings are operational adapter configuration.
    # Until external resources can be imported into the canonical graph, they
    # deliberately do not alter its semantic/configuration fingerprint input.
    assert federated_config.canonical_document() == baseline_config.canonical_document()

    profiles = load_oslc_profiles(federated)
    assert profiles["production"].service_provider_uri == "https://provider.test/oslc/sp/1"
    assert profiles["production"].bearer_token_env == "QUARTO_NEEDS_OSLC_TOKEN"
