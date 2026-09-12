"""Tests for the smoke script's legacy sweep: what it expects and how it paces.

Two independent concerns live here.

The first is that `LEGACY_OPERATIONS` never claims a package-owned path.
`LEGACY_OPERATIONS` exists to prove the deleted legacy `/api/auth` routes stay
deleted. The shared identity package serves its own routes under that same
prefix, so a package-owned path listed as legacy turns normal package behaviour
into a smoke failure, which is exactly what `POST /api/auth/logout` did. The
owned set is read from the package's route constants rather than restated here,
so a path the package adds later is covered without touching this file. Those
tests need the `webbpulse` package and skip without it.

The second is the sweep's own logic: that a 404 is the thing that passes, that a
429 is waited out per `Retry-After` and retried rather than banked as a pass, and
that the pacer keeps the run under the per-IP auth budget. Those run against a
fake transport and a fake clock, so they need no package and no network and do
run in the lean `Scripts` CI job.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import identity_smoke as smoke
from identity_smoke import LEGACY_OPERATIONS, probes_for

IDENTITY_PREFIX = "/api/auth"


def owned_paths() -> set[str]:
    """Every path the identity package serves, as a full `/api/auth` path.

    Read from the `_PATH` constants of the three modules that register routes,
    which is where the routers themselves get them. `verification.py` is left
    out deliberately: its `RESET_LINK_PATH` and `VERIFY_LINK_PATH` are frontend
    link targets baked into emails, not API routes, and one of them collides
    with the genuinely legacy `POST /api/auth/reset-password`.
    """
    pytest.importorskip("webbpulse.identity")
    from webbpulse.identity import oauth_routes, passkey_routes, router

    paths: set[str] = set()
    for module in (router, oauth_routes, passkey_routes):
        for name in dir(module):
            if not name.endswith("_PATH"):
                continue
            value = getattr(module, name)
            if isinstance(value, str) and value.startswith("/"):
                paths.add(f"{IDENTITY_PREFIX}{value}")
    return paths


def concrete(path: str) -> str:
    """Fill a templated path segment with the value the smoke script would send."""
    return path.replace("{provider}", "google")


def test_no_legacy_entry_collides_with_a_package_owned_path():
    owned = owned_paths()
    concrete_owned = {concrete(path) for path in owned}
    collisions = sorted(
        f"{method} {path}"
        for method, path in LEGACY_OPERATIONS
        if path in owned or path in concrete_owned
    )
    assert collisions == [], (
        "these legacy expectations name paths the identity package owns, so the "
        f"package's own answer reads as a smoke failure: {collisions}"
    )


def test_logout_is_not_expected_to_be_absent():
    assert ("POST", f"{IDENTITY_PREFIX}/logout") not in LEGACY_OPERATIONS


def test_logout_is_covered_by_a_positive_probe():
    logout = [
        probe
        for probe in probes_for("smoke-user")
        if probe.path == f"{IDENTITY_PREFIX}/logout"
    ]
    assert len(logout) == 1
    probe = logout[0]
    assert probe.method == "POST"
    assert probe.ok == (200,)
    assert probe.expect_json == {"signed_out": True}


def test_every_legacy_path_sits_under_the_identity_prefix():
    assert all(path.startswith(IDENTITY_PREFIX) for _, path in LEGACY_OPERATIONS)


class FakeClient:
    """A stand-in for `Client` that replays queued responses per request.

    The legacy sweep only needs `call_with_headers`, so that is all this
    implements. Responses are queued per `(method, path)` and popped in order,
    which is what lets a test say "429 twice, then 404" for one probe.
    """

    def __init__(self, responses: dict[tuple[str, str], list[tuple[int, str, dict]]]):
        """Queue the responses each probe should receive, in order."""
        self._responses = {key: list(value) for key, value in responses.items()}
        self.calls: list[tuple[str, str]] = []

    def call_with_headers(self, method, path, *, token=None, body=None, **_):
        """Record the call and return the next queued response for it."""
        self.calls.append((method, path))
        queue = self._responses.get((method, path))
        if not queue:
            return 404, "", {}
        return queue.pop(0) if len(queue) > 1 else queue[0]


class FakeClock:
    """A monotonic clock the test advances only through its own sleeps."""

    def __init__(self):
        """Start at zero with nothing slept."""
        self.now = 0.0
        self.slept: list[float] = []

    def sleep(self, seconds):
        """Advance the clock by `seconds` and remember the interval."""
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self):
        """Return the current time, as `time.monotonic` would."""
        return self.now


def one_legacy_operation():
    """The first legacy operation, as a `(method, concrete path, template)` triple."""
    method, template = smoke.LEGACY_OPERATIONS[0]
    path = template.replace("{account_id}", smoke.UNMATCHABLE).replace(
        "{credential_id}", smoke.UNMATCHABLE
    )
    return method, path, template


def sweep_one(responses, per_minute=smoke.AUTH_REQUESTS_PER_MINUTE):
    """Run the legacy sweep over a one-entry operation list and return its rows."""
    method, path, template = one_legacy_operation()
    clock = FakeClock()
    pacer = smoke.AuthPacer(per_minute=per_minute, sleeper=clock.sleep, clock=clock)
    client = FakeClient({(method, path): responses})
    results: list = []
    original = smoke.LEGACY_OPERATIONS[:]
    try:
        smoke.LEGACY_OPERATIONS[:] = [(method, template)]
        smoke.check_legacy(client, None, results, smoke.load_route_keys(), pacer)
    finally:
        smoke.LEGACY_OPERATIONS[:] = original
    return results, client, clock


def test_a_404_passes_as_proof_the_route_is_gone():
    results, client, _ = sweep_one([(404, "", {})])
    assert [r.verdict for r in results] == ["PASS"]
    assert results[0].status == 404
    assert len(client.calls) == 1


def test_a_429_is_retried_after_the_retry_after_header_and_then_passes():
    results, client, clock = sweep_one([(429, "", {"retry-after": "7"}), (404, "", {})])
    assert [r.verdict for r in results] == ["PASS"]
    assert results[0].status == 404
    assert len(client.calls) == 2
    assert clock.slept == [7.0]
    assert "after 1 429" in results[0].note


def test_a_retry_after_longer_than_the_cap_is_capped():
    _, _, clock = sweep_one([(429, "", {"retry-after": "3600"}), (404, "", {})])
    assert clock.slept == [float(smoke.LEGACY_RETRY_CAP_SECONDS)]


def test_a_429_without_retry_after_falls_back_to_bounded_backoff():
    _, client, clock = sweep_one([(429, "", {}), (429, "", {}), (404, "", {})])
    assert len(client.calls) == 3
    assert clock.slept == [1.0, 2.0]


def test_a_probe_that_never_stops_being_throttled_fails():
    results, client, _ = sweep_one([(429, "", {"retry-after": "1"})])
    assert [r.verdict for r in results] == ["FAIL"]
    assert results[0].status == 429
    assert len(client.calls) == smoke.LEGACY_RETRY_ATTEMPTS
    assert "no proof of deletion" in results[0].note


def test_a_401_now_fails_because_the_route_still_exists():
    results, _, _ = sweep_one([(401, "nope", {})])
    assert [r.verdict for r in results] == ["FAIL"]
    assert "expected 404" in results[0].note


def test_a_200_fails_as_a_live_legacy_operation():
    results, _, _ = sweep_one([(200, "{}", {})])
    assert [r.verdict for r in results] == ["FAIL"]
    assert "still serving" in results[0].note


def test_a_5xx_fails():
    results, _, _ = sweep_one([(503, "boom", {})])
    assert [r.verdict for r in results] == ["FAIL"]
    assert "5xx" in results[0].note


def test_retry_delay_prefers_retry_after_over_backoff():
    assert smoke.retry_delay({"retry-after": "12"}, 0) == 12.0
    assert smoke.retry_delay({"retry-after": "not a number"}, 3) == 8.0
    assert smoke.retry_delay({}, 2) == 4.0


def test_every_legacy_operation_is_expected_to_answer_404_today():
    route_keys = smoke.load_route_keys()
    expectations = {
        smoke.expected_legacy_status(
            method,
            template.replace("{account_id}", smoke.UNMATCHABLE).replace(
                "{credential_id}", smoke.UNMATCHABLE
            ),
            route_keys,
        )
        for method, template in smoke.LEGACY_OPERATIONS
    }
    assert expectations == {404}


def test_a_method_mismatch_on_an_explicit_route_expects_405():
    route_keys = ["GET /api/auth/passkeys"]
    assert (
        smoke.expected_legacy_status("DELETE", "/api/auth/passkeys", route_keys) == 405
    )


def test_the_pacer_sleeps_to_stay_under_the_per_minute_budget():
    clock = FakeClock()
    pacer = smoke.AuthPacer(per_minute=3, sleeper=clock.sleep, clock=clock)
    for _ in range(6):
        pacer.before_call()
        pacer.after_call({})
    assert clock.slept, "the pacer never waited despite exceeding the budget"
    assert pacer.slept_seconds > 0


def test_the_pacer_trusts_the_remaining_header_when_it_is_present():
    clock = FakeClock()
    pacer = smoke.AuthPacer(per_minute=10, sleeper=clock.sleep, clock=clock)
    pacer.before_call()
    pacer.after_call({"x-ratelimit-remaining-minute": "1"})
    pacer.before_call()
    assert clock.slept == [pytest.approx(smoke.AUTH_MINUTE_WINDOW)]
