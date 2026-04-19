"""Verify the nonce check accepts both forms Google emits:
    - raw nonce string (popup / classic GIS flow)
    - base64url(sha256(nonce)) without padding (FedCM flow on Chrome)

These run the real `verify_google_id_token` helper (only `verify_oauth2_token` is
mocked) so we'd notice if a future refactor accidentally tightens the comparison
back to literal equality.
"""

import base64
import hashlib
from unittest.mock import patch

import pytest

from app.api.utils.google_oauth import GoogleTokenError, verify_google_id_token

CLIENT_ID = "test-client.apps.googleusercontent.com"


def _hashed(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _claims(nonce_value: str) -> dict[str, object]:
    return {
        "sub": "g-sub-1",
        "email": "person@example.com",
        "email_verified": True,
        "name": "Person",
        "nonce": nonce_value,
    }


def test_verify_accepts_raw_nonce() -> None:
    expected = "abc123"
    with patch(
        "app.api.utils.google_oauth.google_id_token.verify_oauth2_token",
        return_value=_claims(expected),
    ):
        identity = verify_google_id_token("token", expected, CLIENT_ID)
    assert identity.sub == "g-sub-1"


def test_verify_accepts_hashed_nonce_form() -> None:
    expected = "abc123"
    with patch(
        "app.api.utils.google_oauth.google_id_token.verify_oauth2_token",
        return_value=_claims(_hashed(expected)),
    ):
        identity = verify_google_id_token("token", expected, CLIENT_ID)
    assert identity.email == "person@example.com"


def test_verify_rejects_unrelated_nonce() -> None:
    with patch(
        "app.api.utils.google_oauth.google_id_token.verify_oauth2_token",
        return_value=_claims("attacker-supplied-nonce"),
    ):
        with pytest.raises(GoogleTokenError, match="Nonce mismatch"):
            verify_google_id_token("token", "abc123", CLIENT_ID)
