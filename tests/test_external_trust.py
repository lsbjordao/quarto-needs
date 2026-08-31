"""Explicit trust-state transitions for external observations.

Pins the reviewer-decision contract: transitions are an immutable,
closed allowlist; applying one returns a new observation (never mutating
the input) with provenance preserved, plus an auditable record.
"""

from __future__ import annotations

import pytest

from quarto_needs.external_trust import (
    TrustDecision,
    apply_trust_decision,
)
from quarto_needs.oslc_reconcile import ExternalRequirementObservation
from quarto_needs.oslc_rm import ExternalResourceIdentity


def _observation(trust_state: str = "unverified") -> ExternalRequirementObservation:
    return ExternalRequirementObservation(
        identity=ExternalResourceIdentity(
            resource_uri="https://api.github.com/repos/acme/widgets/issues/2067",
            service_provider_uri="https://api.github.com/repos/acme/widgets",
            digest="sha256:" + "a" * 64,
            fetched_at="2026-08-31T12:00:00Z",
            trust_state=trust_state,  # type: ignore[arg-type]
        ),
        title="Documentation train 2025-2026",
        external_identifier="2067",
    )


def _decision(action: str) -> TrustDecision:
    return TrustDecision(
        action=action,  # type: ignore[arg-type]
        decided_by="reviewer@acme.test",
        reason="Checked against the live tracker.",
        decided_at="2026-08-31T13:00:00Z",
    )


@pytest.mark.parametrize(
    ("from_state", "action", "to_state"),
    [
        ("unverified", "trust", "trusted"),
        ("unverified", "reject", "rejected"),
        ("unverified", "mark-stale", "stale"),
        ("trusted", "reject", "rejected"),
        ("trusted", "mark-stale", "stale"),
        ("stale", "trust", "trusted"),
        ("stale", "reject", "rejected"),
        ("rejected", "reset", "unverified"),
    ],
)
def test_allowed_transitions(from_state: str, action: str, to_state: str) -> None:
    observation = _observation(from_state)

    new_observation, record = apply_trust_decision(observation, _decision(action))

    assert new_observation.identity.trust_state == to_state
    assert record.resource_uri == observation.identity.resource_uri
    assert record.from_state == from_state
    assert record.to_state == to_state


def test_apply_is_non_mutating_and_preserves_provenance() -> None:
    observation = _observation("unverified")
    original_digest = observation.identity.digest
    original_fetched_at = observation.identity.fetched_at

    new_observation, _ = apply_trust_decision(observation, _decision("trust"))

    assert observation.identity.trust_state == "unverified"
    assert new_observation is not observation
    assert new_observation.identity.digest == original_digest
    assert new_observation.identity.fetched_at == original_fetched_at
    assert new_observation.title == observation.title
    assert new_observation.external_identifier == observation.external_identifier


def test_rejection_can_never_be_followed_directly_by_trust() -> None:
    rejected = _observation("rejected")

    with pytest.raises(ValueError, match="not allowed"):
        apply_trust_decision(rejected, _decision("trust"))


def test_unknown_action_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="unsupported trust decision action"):
        TrustDecision(
            action="auto-trust",  # type: ignore[arg-type]
            decided_by="reviewer@acme.test",
            reason="Because.",
            decided_at="2026-08-31T13:00:00Z",
        )


def test_decision_fields_must_be_substantive() -> None:
    with pytest.raises(ValueError, match="reason"):
        TrustDecision(
            action="trust",
            decided_by="reviewer@acme.test",
            reason="  ",
            decided_at="2026-08-31T13:00:00Z",
        )
    with pytest.raises(ValueError, match="decided_by"):
        TrustDecision(
            action="trust",
            decided_by="",
            reason="Because.",
            decided_at="2026-08-31T13:00:00Z",
        )


def test_reconciliation_sees_the_transitioned_state() -> None:
    """A rejected observation blocks reconciliation; after reset it is unbound,
    and after trust it matches — the decision flows into the existing contract."""
    from quarto_needs.oslc_reconcile import reconcile_external_requirements
    from quarto_needs.snapshot import AnalysisSnapshot, ObjectRecord

    local = ObjectRecord(
        id="DOC-2067",
        type="documentation-requirement",
        title="Documentation train 2025-2026",
        status="draft",
        body="Track the documentation work.",
        rationale="Keep authored content canonical.",
        attributes={},
        locations=(),
    )
    snapshot = AnalysisSnapshot(
        objects=(local,),
        relations=(),
        findings=(),
        metrics={},
        objects_by_id={local.id: local},
        outgoing={},
        incoming={},
        generator_name="quarto-needs",
        generator_version="0.1.0",
        relation_catalog_version="1",
        semantic_graph_fingerprint="graph-test",
    )
    observation = _observation()
    binding = {observation.identity.resource_uri: "DOC-2067"}

    rejected, _ = apply_trust_decision(observation, _decision("reject"))
    plan_rejected = reconcile_external_requirements(snapshot, (rejected,), bindings=binding)
    assert plan_rejected.items[0].status == "rejected-external"
    assert plan_rejected.has_conflicts is True

    reset, _ = apply_trust_decision(rejected, _decision("reset"))
    plan_reset = reconcile_external_requirements(snapshot, (reset,), bindings={})
    assert plan_reset.items[0].status == "unbound"

    trusted, _ = apply_trust_decision(reset, _decision("trust"))
    plan_trusted = reconcile_external_requirements(snapshot, (trusted,), bindings=binding)
    assert plan_trusted.items[0].status == "matched"
