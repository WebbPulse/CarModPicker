"""AUTH-04 D-05: HS256 token parity between python-jose (old) and PyJWT (new).

Proves a token issued by the old library decodes identically under the new.
HS256 is deterministic HMAC — byte-compatible across libraries. This test
is the reviewer-visible safety check for the PyJWT swap PR.

Lifetime discretion: keep post-migration as a safeguard against future
library-swap regressions, OR delete alongside python-jose dependency in
Phase 6 cleanup. See CONTEXT.md "Claude's Discretion".
"""

from __future__ import annotations

import jwt as pyjwt
from jose import jwt as jose_jwt


def test_pyjwt_decodes_jose_hs256_token() -> None:
    """Round-trip: jose encode -> PyJWT decode -> payload match."""
    payload = {"sub": "user@example.com", "exp": 9999999999}
    secret = "test-secret-for-parity-check-not-for-production"

    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")
    decoded = pyjwt.decode(jose_token, secret, algorithms=["HS256"])

    assert decoded == payload


def test_pyjwt_and_jose_produce_identical_hs256_tokens() -> None:
    """Byte-identity assertion — both libraries produce the same string for HS256."""
    payload = {"sub": "bob", "exp": 9999999999}
    secret = "test-secret-deterministic"

    pyjwt_token = pyjwt.encode(payload, secret, algorithm="HS256")
    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")

    assert pyjwt_token == jose_token
