#!/usr/bin/env python3
"""Identity-only smoke test: prove an environment runs on identity RS256 alone.

Row 13 deletes the legacy `/api/auth` operations and the HS256 dual mode from
every resolver. Before that merges, the question worth real evidence is not
whether the tests pass, it is whether a live environment still needs any of it.
This script answers that against a deployed environment, over HTTP, with one
account it creates itself.

It checks four things, in the order they build on each other:

1. **An identity account can be created and can sign in.** Registration through
   the package's own `/api/auth/register`, then `/api/auth/login`, then the
   access token is decoded far enough to assert `alg` is RS256 and the issuer
   and audience are this environment's. A legacy HS256 token would fail that
   assertion rather than silently pass as "a token".
2. **Every domain function accepts that token.** One authenticated read and one
   authenticated write per domain Lambda. The write matters more than the read:
   a resolver that still decodes HS256 first and falls back can answer a read
   from cache or from an anonymous path, but a write goes through the ownership
   check that needs a real `sub`.
3. **The frontend bundle no longer names the legacy routes.** The deployed JS is
   fetched and grepped, because the bundle is what users actually run and a
   source tree that no longer mentions a route proves nothing about what is
   deployed in front of them.
4. **The legacy operations are gone.** Each is called with and without the
   token, and each must answer the absence status the gateway's own route table
   implies, which is 404 everywhere the identity prefix still has a catch-all
   `{proxy+}` key and 405 only where a method mismatch hits an explicit route.
   Nothing softer counts: the earlier bar of "not 200 and not 5xx" passed on the
   429 that the per-IP auth limiter returns, which is evidence about the limiter
   and not about the route. So the sweep paces itself under that limit, and waits
   out and retries any 429 it still meets rather than banking it as a pass.

   A 401 or 403 is the pre-row-13 answer from a route that still exists and
   merely refuses, so it is a failure now rather than a pass. A 200 means
   something still serves a legacy operation outright.

Staging's 58 synthetic users carry no credentials, so nothing there is
loginable. Rather than seeding a password onto one of them, which would put a
credential on a row that the migration is trying to empty, this registers a
fresh account through the public endpoint and leaves the credential where the
identity package puts it.

**`--verify-email` flips `email_verified` on the new row.** CarModPicker's
`may_authenticate` hook refuses an unverified address, and `@staging.invalid`
receives no mail, so without this the account can never sign in. The flip is the
same single field write `mark_email_verified` performs when a real user clicks
the link. It needs DynamoDB credentials, and it is a flag rather than the
default so that running this against production does not quietly confirm an
address nobody verified.

A non-zero exit is not automatically a reason to hold row 13. Read the matrix:
a domain write failing on a 404 because a fixture is missing is a defect in this
script, while a domain write failing on a 401 while carrying a valid identity
token is exactly the finding row 13 must not ship over. The summary separates
the two.

Staging answers only a request carrying the origin-verify header. Supply it in
`CARMODPICKER_ORIGIN_VERIFY`, the same variable `verify_route_cut.sh` and the
`smoke-domains` CI job read, sourced from SSM:

    export CARMODPICKER_ORIGIN_VERIFY=$(aws ssm get-parameter --with-decryption \
      --name /carmodpicker-staging/access-gate/origin-verify \
      --query Parameter.Value --output text)

Nothing is embedded here and no value is printed: the header, the password and
the token are redacted everywhere they could reach output.

Usage:

    scripts/identity_smoke.py --env staging --verify-email
    scripts/identity_smoke.py --env staging --keep-account   # skip cleanup
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from expected_route_key import (  # noqa: E402
    declared_route_keys,
    generated_route_keys,
    resolve,
)

TERRAFORM_ROUTE_SOURCE = (
    Path(__file__).resolve().parent.parent / "terraform" / "apigateway.tf"
)

IDENTITY_PATH_PREFIX = "/api/auth"

LEGACY_OPERATIONS: list[tuple[str, str]] = [
    ("DELETE", "/api/auth/oauth/{account_id}"),
    ("DELETE", "/api/auth/webauthn/credentials/{credential_id}"),
    ("GET", "/api/auth/oauth"),
    ("GET", "/api/auth/webauthn/credentials"),
    ("PATCH", "/api/auth/webauthn/credentials/{credential_id}"),
    ("POST", "/api/auth/2fa/disable"),
    ("POST", "/api/auth/2fa/setup"),
    ("POST", "/api/auth/2fa/verify"),
    ("POST", "/api/auth/oauth/2fa"),
    ("POST", "/api/auth/oauth/google"),
    ("POST", "/api/auth/oauth/google/connect"),
    ("POST", "/api/auth/oauth/google/signup"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/reset-password/confirm"),
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/token/2fa"),
    ("POST", "/api/auth/webauthn/login/options"),
    ("POST", "/api/auth/webauthn/login/verify"),
    ("POST", "/api/auth/webauthn/register/options"),
    ("POST", "/api/auth/webauthn/register/verify"),
]

UNMATCHABLE = "row13-smoke-nonexistent"

FORBIDDEN_BUNDLE_STRINGS = [
    "/api/auth/token",
    "/api/auth/webauthn",
    "/api/auth/2fa",
    "/api/auth/reset-password",
    "/auth/token",
    "/auth/webauthn",
    "/auth/2fa",
    "/auth/reset-password",
]

REQUIRED_BUNDLE_STRINGS = ["/api/auth/passkeys", "/api/auth/logout-all"]


AUTH_REQUESTS_PER_MINUTE = 10

AUTH_MINUTE_WINDOW = 60

LEGACY_RETRY_ATTEMPTS = 4

LEGACY_RETRY_CAP_SECONDS = 75

PACING_RESERVE = 1


def _lower_headers(headers: Any) -> dict[str, str]:
    """Every response header as a lowercase-keyed dict."""
    if headers is None:
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _header_int(headers: dict[str, str], name: str) -> int | None:
    """One header parsed as a non-negative int, or None when absent or unparseable."""
    raw = headers.get(name)
    if raw is None:
        return None
    try:
        value = int(float(raw.strip()))
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


def retry_delay(headers: dict[str, str], attempt: int) -> float:
    """How long to wait before retrying a 429, from `Retry-After` when present.

    The app limiter answers a minute-window rejection with `Retry-After: 60` and
    an hour-window rejection with 3600, so the value is honoured but capped: a
    sweep must not block for an hour, it must fail and say the hour bucket is
    exhausted. Without the header this falls back to bounded exponential
    backoff, which is the path a gateway-level 429 takes.
    """
    advertised = _header_int(headers, "retry-after")
    if advertised is not None:
        return float(min(advertised, LEGACY_RETRY_CAP_SECONDS))
    return float(min(2**attempt, LEGACY_RETRY_CAP_SECONDS))


class AuthPacer:
    """Keeps `/api/auth` calls under the per-IP minute limit instead of tripping it.

    Both limiter layers key on source IP alone, not on user agent or path, so
    every auth call this script makes shares one bucket of
    `AUTH_REQUESTS_PER_MINUTE`. The sweep is 40 auth calls, which is four
    minutes' worth, so the choice is between pacing and a wall of 429s that
    prove nothing about whether a route is gone.

    Pacing is driven by the `X-RateLimit-Remaining-Minute` header the app sets
    on every answer rather than by a fixed sleep. The limiter is in-memory per
    execution environment, so the remaining count is the only honest read on how
    much budget this instance has left; when the header is missing the pacer
    falls back to its own count of calls in the current window.
    """

    def __init__(
        self,
        per_minute: int = AUTH_REQUESTS_PER_MINUTE,
        sleeper: Any = time.sleep,
        clock: Any = time.monotonic,
    ) -> None:
        """Configure the budget and the sleep and clock functions to pace with."""
        self._per_minute = per_minute
        self._sleep = sleeper
        self._clock = clock
        self._window_start: float | None = None
        self._calls_in_window = 0
        self._remaining: int | None = None
        self.slept_seconds = 0.0

    def _wait(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self._sleep(seconds)
        self.slept_seconds += seconds

    def before_call(self) -> None:
        """Block until this instance has budget for one more auth call."""
        now = self._clock()
        if self._window_start is None:
            self._window_start = now
            return

        elapsed = now - self._window_start
        if elapsed >= AUTH_MINUTE_WINDOW:
            self._window_start = now
            self._calls_in_window = 0
            self._remaining = None
            return

        budget_left = self._per_minute - PACING_RESERVE - self._calls_in_window
        if self._remaining is not None:
            budget_left = min(budget_left, self._remaining - PACING_RESERVE)
        if budget_left > 0:
            return

        self._wait(AUTH_MINUTE_WINDOW - elapsed)
        self._window_start = self._clock()
        self._calls_in_window = 0
        self._remaining = None

    def after_call(self, headers: dict[str, str]) -> None:
        """Record one spent call and the quota the response advertised."""
        self._calls_in_window += 1
        self._remaining = _header_int(headers, "x-ratelimit-remaining-minute")

    def wait_out_429(self, headers: dict[str, str], attempt: int) -> float:
        """Sleep off a 429 and reset the window, returning the seconds waited."""
        delay = retry_delay(headers, attempt)
        self._wait(delay)
        self._window_start = self._clock()
        self._calls_in_window = 0
        self._remaining = None
        return delay


@dataclass
class Result:
    """One row of the output matrix."""

    domain: str
    method: str
    path: str
    status: int | str
    verdict: str
    note: str = ""


@dataclass
class Probe:
    """One authenticated call to make against a domain function."""

    domain: str
    method: str
    path: str
    ok: tuple[int, ...]
    body: dict[str, Any] | None = None
    kind: str = "read"
    note: str = ""
    needs: list[str] = field(default_factory=list)
    expect_json: dict[str, Any] | None = None


class Client:
    """A tiny HTTP client that never raises on a status and never logs a secret."""

    def __init__(self, base: str, origin_verify: str, timeout: int = 30) -> None:
        """Store the API base URL, the origin verify secret and the request timeout."""
        self._base = base.rstrip("/")
        self._origin_verify = origin_verify
        self._timeout = timeout

    def call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        skip_gate_header: bool = False,
    ) -> tuple[int, str]:
        """Send one request and return its status code and body text."""
        status, text, _ = self.call_with_headers(
            method,
            path,
            token=token,
            body=body,
            skip_gate_header=skip_gate_header,
        )
        return status, text

    def call_with_headers(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        skip_gate_header: bool = False,
    ) -> tuple[int, str, dict[str, str]]:
        """Send one request and also return its response headers, lowercased.

        The legacy sweep needs `Retry-After` and the `X-RateLimit-*` counters to
        pace itself, and those only exist on the response. Header names are
        lowercased here so callers never have to guess the server's casing.
        """
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        if self._origin_verify and not skip_gate_header:
            request.add_header("x-origin-verify", self._origin_verify)
        if token:
            request.add_header("authorization", f"Bearer {token}")
        if data is not None:
            request.add_header("content-type", "application/json")
        request.add_header("user-agent", "carmodpicker-identity-smoke")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return (
                    response.status,
                    response.read().decode("utf-8", "replace"),
                    _lower_headers(response.headers),
                )
        except urllib.error.HTTPError as exc:
            return (
                exc.code,
                exc.read().decode("utf-8", "replace"),
                _lower_headers(exc.headers),
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            return 0, f"transport error: {exc}", {}


def decode_claims(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read a JWT's header and claims without verifying it.

    Verification is the gateway's job and it has already happened by the time a
    call succeeds. What this is for is asserting the *shape*: that the token the
    environment issued is RS256 from the identity issuer rather than a legacy
    HS256 one, which is a claim about which code path minted it.
    """
    header_b64, payload_b64 = token.split(".")[:2]
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    return (
        json.loads(base64.urlsafe_b64decode(pad(header_b64))),
        json.loads(base64.urlsafe_b64decode(pad(payload_b64))),
    )


def probes_for(user_id: str) -> list[Probe]:
    """One authenticated read and one authenticated write per domain function.

    The writes are chosen to be self-contained where possible: a build list is
    created and deleted by this run, and the build log post and vote hang off
    it. Where a domain has no write this account may perform, the probe is the
    refusal that proves the token was read, which is the case for `admin`.
    """
    return [
        Probe(
            "identity",
            "POST",
            "/api/auth/logout-all",
            ok=(200,),
            kind="write",
            note="ends other sessions, harmless for a fresh account",
        ),
        Probe("users", "GET", "/api/users/me", ok=(200,)),
        Probe(
            "users",
            "PUT",
            f"/api/users/{user_id}",
            ok=(200,),
            kind="write",
            body={"bio": "row13 smoke"},
            note="updates the account this run created",
        ),
        Probe("catalog", "GET", "/api/parts/count", ok=(200,)),
        Probe("catalog", "GET", "/api/parts/filter-options", ok=(200,), kind="read"),
        Probe("vehicles", "GET", "/api/car-generations/count", ok=(200,)),
        Probe("vehicles", "GET", "/api/search?q=row13", ok=(200,), kind="read"),
        Probe(
            "vehicles",
            "GET",
            "/api/car-generations?limit=1",
            ok=(200,),
            kind="read",
            note="supplies the car_id the build-lists create requires",
        ),
        Probe("build-lists", "GET", "/api/build-lists/user/me", ok=(200,)),
        Probe(
            "build-lists",
            "POST",
            "/api/build-lists",
            ok=(200, 201),
            kind="write",
            needs=["car_id"],
            body={
                "name": "row13 smoke",
                "description": "temporary",
                "car_id": "{car_id}",
            },
            note="creates the fixture the next two domains use",
        ),
        Probe("build-logs", "GET", "/api/build-logs/posts/count", ok=(200,)),
        Probe(
            "build-logs",
            "POST",
            "/api/build-logs/build-list/{build_list_id}/posts",
            ok=(200, 201),
            kind="write",
            needs=["build_list_id"],
            body={"title": "row13 smoke", "content": "temporary"},
        ),
        Probe("moderation", "GET", "/api/votes/count", ok=(200,)),
        Probe(
            "moderation",
            "POST",
            "/api/votes/build_list/{build_list_id}",
            ok=(200, 201),
            kind="write",
            needs=["build_list_id"],
            body={"vote_type": "upvote"},
        ),
        Probe(
            "media",
            "GET",
            f"/api/images/by-source-url?source_url=https://example.invalid/{UNMATCHABLE}.png",
            ok=(404,),
            kind="write",
            note="404 expected, the flagged media route resolved the caller",
        ),
        Probe(
            "media",
            "GET",
            "/api/images/admin/count",
            ok=(403,),
            kind="read",
            note="403 expected, this account is not an admin",
        ),
        Probe(
            "admin",
            "GET",
            "/api/admin/stats/table-counts",
            ok=(403,),
            note="403 expected for a non-admin",
        ),
        Probe(
            "admin",
            "POST",
            "/api/admin/db-ops/parts/delete-all",
            ok=(403,),
            kind="write",
            note="403 expected, must NOT be 200",
        ),
        Probe(
            "identity",
            "POST",
            "/api/auth/logout",
            ok=(200,),
            kind="write",
            expect_json={"signed_out": True},
            note="package-owned route, not a legacy leftover; runs last because it ends the session",
        ),
    ]


def resolve_body(
    body: dict[str, Any] | None, context: dict[str, str]
) -> dict[str, Any] | None:
    """Substitute `{name}` placeholders in a probe body with ids earlier probes captured."""
    if not body:
        return body
    resolved: dict[str, Any] = {}
    for key, value in body.items():
        if isinstance(value, str):
            for name, captured in context.items():
                value = value.replace("{" + name + "}", captured)
        resolved[key] = value
    return resolved


def run_domain_probes(
    client: Client, token: str, user_id: str, results: list[Result]
) -> dict[str, str]:
    """Run every domain probe, threading ids created by one probe into the next."""
    context: dict[str, str] = {}
    for probe in probes_for(user_id):
        path = probe.path
        missing = [name for name in probe.needs if name not in context]
        if missing:
            results.append(
                Result(
                    probe.domain,
                    probe.method,
                    probe.path,
                    "skipped",
                    "SKIP",
                    f"needs {', '.join(missing)} from an earlier probe that failed",
                )
            )
            continue
        for name, value in context.items():
            path = path.replace("{" + name + "}", value)

        status, text = client.call(
            probe.method, path, token=token, body=resolve_body(probe.body, context)
        )
        verdict = "PASS" if status in probe.ok else "FAIL"
        note = probe.note
        if verdict == "PASS" and probe.expect_json is not None:
            try:
                payload = json.loads(text)
            except ValueError:
                payload = None
            if not isinstance(payload, dict) or any(
                payload.get(key) != value for key, value in probe.expect_json.items()
            ):
                verdict = "FAIL"
                note = f"expected {probe.expect_json} in the body, got {text[:120]}"
        if status == 401:
            note = "401 while carrying a valid identity token: THIS IS THE ROW 13 RISK"
        elif status >= 500:
            note = f"5xx: {text[:120]}"
        elif verdict == "FAIL":
            note = f"{note + '; ' if note else ''}body: {text[:120]}"

        results.append(
            Result(probe.domain, probe.method, probe.path, status, verdict, note)
        )

        if probe.path.startswith("/api/car-generations?") and status == 200:
            try:
                listing = json.loads(text)
            except ValueError:
                listing = {}
            items = listing.get("items") if isinstance(listing, dict) else None
            if items and isinstance(items[0], dict) and items[0].get("id") is not None:
                context["car_id"] = str(items[0]["id"])

        if (
            probe.domain == "build-lists"
            and probe.method == "POST"
            and status in (200, 201)
        ):
            try:
                created = json.loads(text)
            except ValueError:
                created = {}
            if isinstance(created, dict) and created.get("id") is not None:
                context["build_list_id"] = str(created["id"])
    return context


def check_bundle(bucket: str, results: list[Result]) -> None:
    """Read the deployed frontend bundle from its S3 origin and grep it.

    **From S3 rather than over HTTPS, and that is not a shortcut.** The staging
    frontend sits behind the CloudFront signed-cookie login gate, so a plain
    fetch of `https://www.staging...` answers `302 /_auth/login` and the
    origin-verify header does not bypass it: that header is the API gate's, and
    the frontend gate is a different mechanism. Grepping the 302 body finds no
    legacy strings and reports a pass, which is the worst possible outcome for a
    check whose entire job is to find them. The bucket holds exactly the bytes
    CloudFront serves, so reading it is the same evidence with none of that.

    Every `.js` object under `assets/` is read, not only the entry chunk, since a
    code-split build can put the auth client anywhere.
    """
    try:
        import boto3
    except ImportError:
        results.append(
            Result("frontend", "s3", bucket, "skipped", "SKIP", "boto3 not installed")
        )
        return

    region = os.environ.get("AWS_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION", "us-west-2"
    )
    s3 = boto3.client("s3", region_name=region)
    combined = ""
    chunks = 0
    try:
        pages = s3.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix="assets/"
        )
        for page in pages:
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".js"):
                    continue
                combined += (
                    s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"]
                    .read()
                    .decode("utf-8", "replace")
                )
                chunks += 1
    except Exception as exc:  # noqa: BLE001
        results.append(
            Result("frontend", "s3", bucket, "error", "FAIL", str(exc)[:120])
        )
        return

    results.append(
        Result("frontend", "s3", bucket, 200, "PASS", f"{chunks} JS chunks read")
    )

    import re

    for needle in FORBIDDEN_BUNDLE_STRINGS:
        present = needle in combined
        results.append(
            Result(
                "frontend",
                "grep",
                needle,
                "PRESENT" if present else "absent",
                "FAIL" if present else "PASS",
                "legacy endpoint referenced in the deployed bundle" if present else "",
            )
        )

    for needle in REQUIRED_BUNDLE_STRINGS:
        present = needle in combined
        results.append(
            Result(
                "frontend",
                "grep",
                needle,
                "present" if present else "ABSENT",
                "PASS" if present else "FAIL",
                "" if present else "identity endpoint not referenced",
            )
        )


def check_jwks_reachable(client: Client, results: list[Result]) -> bool:
    """Can the access gate authorizer fetch the JWKS it verifies tokens against?

    This is the first check that runs after login, because it explains an entire
    column of the matrix when it fails. The gate is a REQUEST authorizer that
    verifies the identity access token itself, and to do that it fetches
    `IDENTITY_JWKS_URL`. That URL is on the same API the gate protects, so if
    the JWKS route is not exempt from the gate, the authorizer's own fetch is
    answered 403 by the authorizer's own policy, every token verification fails
    closed, and every authenticated route answers 403 with API Gateway's bare
    `{"message":"Forbidden"}` regardless of which token is presented.

    The symptom reads exactly like "row 13 broke authentication" and is not that
    at all, so it is worth naming before the domain probes rather than after.
    """
    status, _ = client.call(
        "GET", "/api/auth/.well-known/jwks.json", skip_gate_header=True
    )
    reachable = status == 200
    results.append(
        Result(
            "gate",
            "GET",
            "/api/auth/.well-known/jwks.json (no gate header)",
            status,
            "PASS" if reachable else "FAIL",
            (
                ""
                if reachable
                else "the gate authorizer cannot fetch the JWKS, so every token fails closed"
            ),
        )
    )
    return reachable


def expected_legacy_status(method: str, path: str, route_keys: list[str]) -> int:
    """The status a deleted legacy operation must answer, 404 or 405.

    Derived from the gateway's own route table rather than assumed. A legacy path
    that resolves to a catch-all `ANY .../{proxy+}` key reaches the application,
    which has no such route left and answers 404. A path that resolves to no key
    at all for this method while some other method has an explicit key for it is
    a method mismatch on a route that still exists, and the gateway answers 405
    for that before the application sees it.
    """
    if resolve(path, method, route_keys):
        return 404
    for other in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        if other == method:
            continue
        key = resolve(path, other, route_keys)
        if key and not key.startswith("ANY "):
            return 405
    return 404


def load_route_keys() -> list[str]:
    """The gateway's declared route keys, plus the identity prefix's generated pair.

    Read from the Terraform source so a route promoted to its own explicit key
    changes the expectation without an edit here. An unreadable source yields the
    generated pair alone, which keeps the sweep expecting 404 everywhere rather
    than failing on a missing file.
    """
    try:
        source = TERRAFORM_ROUTE_SOURCE.read_text(encoding="utf-8")
    except OSError:
        source = ""
    return declared_route_keys(source) + generated_route_keys([IDENTITY_PATH_PREFIX])


def check_legacy(
    client: Client,
    token: str | None,
    results: list[Result],
    route_keys: list[str],
    pacer: AuthPacer,
) -> None:
    """Call every legacy operation and prove each one is really gone.

    The bar here is the expected absence status and nothing softer. An earlier
    version passed anything that was not 200 and not 5xx, which in practice
    meant most rows passed on a 429 from the rate limiter: evidence that the
    limiter works, and no evidence at all about whether the route is gone. A
    route that answers 401 is still a route, so that fails now too.

    Both limiter layers key on source IP, so the sweep paces itself under the
    per-minute auth budget instead of tripping it, and a 429 that still arrives
    is waited out per `Retry-After` and retried rather than recorded as a pass.
    Exhausting `LEGACY_RETRY_ATTEMPTS` is a failure, because a probe that never
    got an answer has not proved anything.

    Only paths the shared identity package does not own belong here. A path the
    package serves answers from the package, not from a legacy leftover, so
    listing one turns package behaviour into a false failure. `test_identity_smoke.py`
    holds that line against the package's own route constants.
    """
    label = "legacy+token" if token else "legacy"
    for method, template in LEGACY_OPERATIONS:
        path = template.replace("{account_id}", UNMATCHABLE).replace(
            "{credential_id}", UNMATCHABLE
        )
        body = {} if method in ("POST", "PATCH", "PUT") else None
        expected = expected_legacy_status(method, path, route_keys)

        status: int | str = 0
        text = ""
        throttled = 0
        for attempt in range(LEGACY_RETRY_ATTEMPTS):
            pacer.before_call()
            status, text, headers = client.call_with_headers(
                method, path, token=token, body=body
            )
            pacer.after_call(headers)
            if status != 429:
                break
            throttled += 1
            if attempt == LEGACY_RETRY_ATTEMPTS - 1:
                break
            pacer.wait_out_429(headers, attempt)

        retried = f" after {throttled} 429" if throttled else ""
        if status == expected:
            verdict, note = "PASS", f"route absent ({expected}){retried}"
        elif status == 429:
            verdict, note = (
                "FAIL",
                f"still 429 after {LEGACY_RETRY_ATTEMPTS} attempts, no proof of deletion",
            )
        elif status == 200:
            verdict, note = "FAIL", "still serving a legacy operation"
        elif isinstance(status, int) and status >= 500:
            verdict, note = "FAIL", f"5xx: {text[:100]}"
        else:
            verdict, note = (
                "FAIL",
                f"expected {expected}, got {status}: {text[:80]}",
            )
        results.append(Result(label, method, template, status, verdict, note))


def main() -> int:
    """Run the smoke suite against one environment and return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="staging", choices=("staging", "production"))
    parser.add_argument("--api-base-url", default=None)
    parser.add_argument(
        "--verify-email",
        action="store_true",
        help="flip email_verified on the created row, needs DynamoDB credentials",
    )
    parser.add_argument("--keep-account", action="store_true", help="skip cleanup")
    parser.add_argument(
        "--auth-per-minute",
        type=int,
        default=int(
            os.environ.get("CARMODPICKER_AUTH_PER_MINUTE", AUTH_REQUESTS_PER_MINUTE)
        ),
        help=(
            "per-IP /api/auth budget the legacy sweep paces under; only raise it "
            "when the deployed RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE is higher"
        ),
    )
    args = parser.parse_args()

    suffix = "staging." if args.env == "staging" else ""
    api_base = args.api_base_url or f"https://api.{suffix}carmodpicker.com"

    origin_verify = os.environ.get("CARMODPICKER_ORIGIN_VERIFY", "")
    if args.env == "staging" and not origin_verify:
        print(
            "CARMODPICKER_ORIGIN_VERIFY is not set. Staging is behind the access\n"
            "gate, so every request would be answered by the gate rather than by\n"
            "the API and the whole matrix would read as a failure that is really\n"
            "a missing credential. See this file's docstring for the SSM read.",
            file=sys.stderr,
        )
        return 2

    client = Client(api_base, origin_verify)
    results: list[Result] = []

    email = f"row13-smoke-{int(time.time())}@staging.invalid"
    password = f"Rw13!{secrets.token_hex(12)}Aa"
    print(
        f"Environment : {args.env}\nAPI         : {api_base}\nAccount     : {email}\n"
    )

    status, text = client.call(
        "POST", "/api/auth/register", body={"email": email, "password": password}
    )
    registered = status in (200, 201) or (
        status == 403 and "EMAIL_VERIFICATION_REQUIRED" in text
    )
    results.append(
        Result(
            "identity",
            "POST",
            "/api/auth/register",
            status,
            "PASS" if registered else "FAIL",
            "account created, verification required" if status == 403 else "",
        )
    )
    if not registered:
        print(f"Registration failed: {status} {text[:200]}", file=sys.stderr)
        return 1

    user_id = ""
    if args.verify_email:
        try:
            import boto3

            region = os.environ.get("AWS_REGION") or os.environ.get(
                "AWS_DEFAULT_REGION", "us-west-2"
            )
            table = boto3.resource("dynamodb", region_name=region).Table(
                f"carmodpicker-{args.env}-users"
            )
            scan = table.scan(
                FilterExpression="email = :e", ExpressionAttributeValues={":e": email}
            )
            items = scan.get("Items", [])
            if not items:
                print(
                    "Registered account not found in the users table.", file=sys.stderr
                )
                return 1
            user_id = str(items[0]["id"])
            table.update_item(
                Key={"id": user_id},
                UpdateExpression="SET email_verified = :t",
                ExpressionAttributeValues={":t": True},
            )
            results.append(
                Result(
                    "identity",
                    "ddb",
                    "email_verified",
                    "set",
                    "PASS",
                    "same field mark_email_verified writes",
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Could not mark the address verified: {exc}", file=sys.stderr)
            return 1

    status, text = client.call(
        "POST", "/api/auth/login", body={"email": email, "password": password}
    )
    if status != 200:
        results.append(
            Result("identity", "POST", "/api/auth/login", status, "FAIL", text[:150])
        )
        render(results)
        return 1
    token = json.loads(text).get("access_token", "")
    header, claims = decode_claims(token)

    rs256 = header.get("alg") == "RS256"
    issuer_ok = claims.get("iss", "").startswith(api_base)
    results.append(
        Result(
            "identity",
            "POST",
            "/api/auth/login",
            status,
            "PASS" if rs256 and issuer_ok else "FAIL",
            f"alg={header.get('alg')} iss={claims.get('iss')} aud={claims.get('aud')}",
        )
    )
    if not user_id:
        user_id = str(claims.get("sub", ""))

    check_jwks_reachable(client, results)
    run_domain_probes(client, token, user_id, results)
    check_bundle(f"carmodpicker-{args.env}-frontend", results)
    route_keys = load_route_keys()
    pacer = AuthPacer(per_minute=args.auth_per_minute)
    sweep_start = time.monotonic()
    check_legacy(client, None, results, route_keys, pacer)
    check_legacy(client, token, results, route_keys, pacer)
    print(
        f"\nLegacy sweep: {time.monotonic() - sweep_start:.0f}s wall, "
        f"{pacer.slept_seconds:.0f}s paced at {args.auth_per_minute}/min\n"
    )

    if not args.keep_account:
        client.call("DELETE", f"/api/users/{user_id}", token=token)

    return render(results)


def render(results: list[Result]) -> int:
    """Print the results as a table and return the number of failures."""
    width = max(len(r.path) for r in results) + 2
    print(
        f"{'DOMAIN':<14}{'METHOD':<8}{'PATH':<{width}}{'STATUS':<10}{'VERDICT':<8}NOTE"
    )
    print("-" * (44 + width))
    for r in results:
        print(
            f"{r.domain:<14}{r.method:<8}{r.path:<{width}}{str(r.status):<10}"
            f"{r.verdict:<8}{r.note}"
        )

    failures = [r for r in results if r.verdict == "FAIL"]
    skipped = [r for r in results if r.verdict == "SKIP"]
    print(
        f"\n{len(results) - len(failures) - len(skipped)} passed, "
        f"{len(failures)} failed, {len(skipped)} skipped"
    )
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  {r.domain} {r.method} {r.path} -> {r.status}  {r.note}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
