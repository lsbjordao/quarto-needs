"""Explicit trust-state transitions for external requirement observations.

Every fetched external observation starts ``unverified``. Moving it to
``trusted``/``rejected``/``stale`` is a reviewer decision, never an
inference: this module models that decision as an immutable record and
applies it by returning a *new* observation — the original is never
mutated, and the observed bytes' digest is preserved, because a trust
decision says something about the reviewer, not about the remote
representation. Transitions form a closed allowlist; anything outside it
raises rather than being guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .oslc_reconcile import ExternalRequirementObservation
from .oslc_rm import TrustState

TrustDecisionAction = Literal["trust", "reject", "mark-stale", "reset"]

# Closed allowlist of (from, action) -> to transitions. Deliberately
# asymmetric: a rejected observation must go through an explicit "reset"
# back to unverified before it can be trusted again — trust can never
# directly follow rejection.
_ALLOWED_TRANSITIONS: dict[tuple[str, str], TrustState] = {
    ("unverified", "trust"): "trusted",
    ("unverified", "reject"): "rejected",
    ("unverified", "mark-stale"): "stale",
    ("trusted", "reject"): "rejected",
    ("trusted", "mark-stale"): "stale",
    ("stale", "trust"): "trusted",
    ("stale", "reject"): "rejected",
    ("rejected", "reset"): "unverified",
}


@dataclass(frozen=True, slots=True)
class TrustDecision:
    """One explicit reviewer decision about an external observation."""

    action: TrustDecisionAction
    decided_by: str
    reason: str
    decided_at: str

    def __post_init__(self) -> None:
        if self.action not in {"trust", "reject", "mark-stale", "reset"}:
            raise ValueError(f"unsupported trust decision action: {self.action!r}")
        for field in ("decided_by", "reason", "decided_at"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"trust decision {field} must be a non-empty string")

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "decidedBy": self.decided_by,
            "reason": self.reason,
            "decidedAt": self.decided_at,
        }


@dataclass(frozen=True, slots=True)
class TrustDecisionRecord:
    """The auditable outcome of applying one decision to one observation."""

    resource_uri: str
    from_state: TrustState
    to_state: TrustState
    decision: TrustDecision

    def to_dict(self) -> dict[str, object]:
        return {
            "resourceUri": self.resource_uri,
            "fromState": self.from_state,
            "toState": self.to_state,
            "decision": self.decision.to_dict(),
        }


def apply_trust_decision(
    observation: ExternalRequirementObservation,
    decision: TrustDecision,
) -> tuple[ExternalRequirementObservation, TrustDecisionRecord]:
    """Return a new observation with the decision applied, plus its record.

    Non-mutating by construction: the input observation is untouched, the
    digest and retrieval provenance carry over unchanged (a trust decision
    is about the reviewer's judgement, not about the remote bytes), and a
    (from-state, action) pair outside the allowlist raises instead of
    guessing.
    """
    from_state = observation.identity.trust_state
    to_state = _ALLOWED_TRANSITIONS.get((from_state, decision.action))
    if to_state is None:
        alternatives = sorted(
            f"{source} -> {target}"
            for (source, action), target in _ALLOWED_TRANSITIONS.items()
            if action == decision.action
        )
        detail = "; allowed for this action: " + ", ".join(alternatives) if alternatives else ""
        raise ValueError(
            f"trust transition ({from_state}, {decision.action}) is not allowed"
            + detail
        )

    identity = observation.identity
    new_observation = ExternalRequirementObservation(
        identity=type(identity)(
            resource_uri=identity.resource_uri,
            service_provider_uri=identity.service_provider_uri,
            digest=identity.digest,
            fetched_at=identity.fetched_at,
            trust_state=to_state,
            etag=identity.etag,
            last_modified=identity.last_modified,
        ),
        title=observation.title,
        description=observation.description,
        external_identifier=observation.external_identifier,
        attributes=observation.attributes,
    )
    record = TrustDecisionRecord(
        resource_uri=identity.resource_uri,
        from_state=from_state,
        to_state=to_state,
        decision=decision,
    )
    return new_observation, record
