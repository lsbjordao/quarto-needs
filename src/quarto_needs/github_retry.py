"""Caller-side rate-limit retry policy for GitHub fetches.

The transport reports the server's retry facts and never sleeps on its
own; this module is the policy that turns those facts into a decision.
Wait order is explicit, never guessed: the server's own ``Retry-After``
wins, then its ``X-RateLimit-Reset`` epoch (only if the caller supplies a
clock), then bounded exponential backoff. ``max_attempts`` is the give-up
point — exceeding it re-raises the original rate-limit error so the
caller sees the server's facts, not a synthesized failure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .github_http import GitHubFetchResult, GitHubRateLimitError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    max_wait_seconds: float = 120.0
    backoff_base_seconds: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if self.max_wait_seconds <= 0 or self.backoff_base_seconds <= 0:
            raise ValueError("wait bounds must be positive")


def wait_before_attempt(
    error: GitHubRateLimitError,
    *,
    attempt: int,
    policy: RetryPolicy,
    now_epoch: float | None = None,
) -> float | None:
    """Seconds to wait before retry ``attempt`` (1-based), or ``None`` to give up.

    ``Retry-After`` is the server's explicit instruction and is honored
    first; ``X-RateLimit-Reset`` is honored when the caller supplies a
    clock; otherwise the policy's exponential backoff applies. Every wait
    is clamped to ``max_wait_seconds``.
    """
    if attempt > policy.max_attempts:
        return None
    if error.retry_after_seconds is not None:
        return min(float(error.retry_after_seconds), policy.max_wait_seconds)
    if error.rate_limit_reset_epoch is not None and now_epoch is not None:
        return min(max(float(error.rate_limit_reset_epoch) - now_epoch, 0.0), policy.max_wait_seconds)
    return min(policy.backoff_base_seconds * (2 ** (attempt - 1)), policy.max_wait_seconds)


def fetch_with_retry(
    fetch,  # type: ignore[no-untyped-def]
    *,
    policy: RetryPolicy = RetryPolicy(),
    sleep=time.sleep,  # type: ignore[no-untyped-def]
    now=time.time,  # type: ignore[no-untyped-def]
) -> GitHubFetchResult:
    """Call ``fetch`` (a zero-argument callable), retrying only rate limits.

    Any other error propagates immediately — a 404 or an authentication
    failure is a fact to act on, not something to wait out.
    """
    attempt = 1
    while True:
        try:
            return fetch()
        except GitHubRateLimitError as error:
            next_attempt = attempt + 1
            wait = wait_before_attempt(
                error, attempt=next_attempt, policy=policy, now_epoch=now()
            )
            if wait is None:
                raise
            sleep(wait)
            attempt = next_attempt
