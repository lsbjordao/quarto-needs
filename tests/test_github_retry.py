"""Caller-side retry policy for GitHub rate limits.

Pins the wait-order contract (Retry-After, then reset epoch, then
bounded backoff), the give-up point re-raising the server's own error,
and the rule that only rate limits are ever retried.
"""

from __future__ import annotations

import pytest

from quarto_needs.github_http import (
    GitHubRateLimitError,
    GitHubTransportError,
)
from quarto_needs.github_retry import RetryPolicy, fetch_with_retry, wait_before_attempt


def _error(
    *,
    retry_after: int | None = None,
    reset_epoch: int | None = None,
) -> GitHubRateLimitError:
    return GitHubRateLimitError(
        "GitHub rate limit exhausted",
        retry_after_seconds=retry_after,
        rate_limit_reset_epoch=reset_epoch,
    )


def test_retry_after_is_honored_first() -> None:
    error = _error(retry_after=30, reset_epoch=9999999999)

    assert wait_before_attempt(error, attempt=1, policy=RetryPolicy()) == 30.0


def test_reset_epoch_is_used_with_a_clock() -> None:
    error = _error(reset_epoch=2000)

    assert wait_before_attempt(
        error, attempt=1, policy=RetryPolicy(), now_epoch=1985.0
    ) == 15.0
    # A reset in the past means an immediate retry, never a negative wait.
    assert wait_before_attempt(
        error, attempt=1, policy=RetryPolicy(), now_epoch=5000.0
    ) == 0.0


def test_reset_epoch_without_a_clock_falls_back_to_backoff() -> None:
    error = _error(reset_epoch=2000)

    assert wait_before_attempt(error, attempt=1, policy=RetryPolicy()) == 1.0


def test_backoff_grows_and_is_capped() -> None:
    policy = RetryPolicy(max_attempts=10, backoff_base_seconds=2.0, max_wait_seconds=30.0)

    assert wait_before_attempt(_error(), attempt=1, policy=policy) == 2.0
    assert wait_before_attempt(_error(), attempt=2, policy=policy) == 4.0
    assert wait_before_attempt(_error(), attempt=9, policy=policy) == 30.0


def test_attempts_beyond_the_policy_give_up() -> None:
    policy = RetryPolicy(max_attempts=3)

    assert wait_before_attempt(_error(retry_after=30), attempt=3, policy=policy) == 30.0
    assert wait_before_attempt(_error(retry_after=30), attempt=4, policy=policy) is None


def test_invalid_policy_bounds_are_refused() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="positive"):
        RetryPolicy(max_wait_seconds=0)


def test_fetch_with_retry_sleeps_then_succeeds() -> None:
    calls: list[float] = []
    outcomes = [_error(retry_after=5), "result"]

    def fetch():
        outcome = outcomes.pop(0)
        if isinstance(outcome, GitHubRateLimitError):
            raise outcome
        return outcome

    result = fetch_with_retry(
        fetch, sleep=calls.append, policy=RetryPolicy(max_attempts=2)
    )

    assert result == "result"
    assert calls == [5.0]


def test_giving_up_re_raises_the_server_error() -> None:
    error = _error(retry_after=5)
    attempts: list[int] = []

    def fetch():
        attempts.append(1)
        raise error

    with pytest.raises(GitHubRateLimitError) as excinfo:
        fetch_with_retry(fetch, sleep=lambda _: None, policy=RetryPolicy(max_attempts=2))

    assert excinfo.value is error
    # max_attempts=2 permits 2 retries (matching wait_before_attempt's own
    # attempt=1/attempt=2 contract), plus the initial call: 3 total.
    assert len(attempts) == 3


def test_fetch_with_retry_uses_the_first_retrys_own_backoff_not_the_seconds() -> None:
    """The wait before retry #1 must be wait_before_attempt(attempt=1, ...).

    Passing ``attempt=2`` for the first retry would double every computed
    backoff wait and give up one retry earlier than the policy allows.
    """
    policy = RetryPolicy(max_attempts=5, backoff_base_seconds=2.0, max_wait_seconds=100.0)
    outcomes = [_error(), _error(), "result"]
    waits: list[float] = []

    def fetch():
        outcome = outcomes.pop(0)
        if isinstance(outcome, GitHubRateLimitError):
            raise outcome
        return outcome

    result = fetch_with_retry(fetch, sleep=waits.append, policy=policy)

    assert result == "result"
    assert waits == [2.0, 4.0]


def test_non_rate_limit_errors_propagate_immediately() -> None:
    sleeps: list[float] = []

    def fetch():
        raise GitHubTransportError("not-found", "GitHub resource not found")

    with pytest.raises(GitHubTransportError):
        fetch_with_retry(fetch, sleep=sleeps.append)

    assert sleeps == []
