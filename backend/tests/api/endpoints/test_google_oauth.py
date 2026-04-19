"""Tests for Google sign-in / OAuth account linking endpoints.

Real Google ID-token verification requires a token signed by Google's keys, which we
can't reproduce in a unit test. We patch `verify_google_id_token` (the helper bound
into the auth module's namespace) and exercise the full state machine around it:

  - /auth/google: routing to login / link-required / signup-required.
  - /auth/google/link: password (and optional OTP) gated merge into an existing user.
  - /auth/google/signup: new user creation with no password and email auto-verified.
  - /auth/oauth/2fa: TOTP completion for users who have 2FA enabled.
  - /auth/google/connect, /auth/oauth, /auth/oauth/{id}: linked-account management.

The disconnect-safety check (no password + no other oauth + no passkeys → refuse)
is covered, since that's the invariant that prevents users from locking themselves out.
"""

import os
from typing import Generator
from unittest.mock import patch

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.oauth_account import OAuthAccount
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.api.utils.google_oauth import GoogleIdentity
from app.core.config import settings

GOOGLE_PATH = f"{settings.API_STR}/auth/google"
LINK_PATH = f"{settings.API_STR}/auth/google/link"
SIGNUP_PATH = f"{settings.API_STR}/auth/google/signup"
CONNECT_PATH = f"{settings.API_STR}/auth/google/connect"
OAUTH_2FA_PATH = f"{settings.API_STR}/auth/oauth/2fa"
OAUTH_LIST_PATH = f"{settings.API_STR}/auth/oauth"


def _unique(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def _create_user(
    db: Session,
    username: str,
    *,
    password: str = "testpassword",
    email: str | None = None,
    totp_secret: str | None = None,
) -> DBUser:
    user = DBUser(
        username=username,
        email=email or f"{username}@example.com",
        hashed_password=get_password_hash(password) if password else None,
        email_verified=True,
        disabled=False,
        totp_secret=totp_secret,
        totp_enabled=bool(totp_secret),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client: TestClient, username: str, password: str = "testpassword") -> str:
    resp = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _identity(sub: str, email: str, email_verified: bool = True, name: str | None = "Tester") -> GoogleIdentity:
    return GoogleIdentity(sub=sub, email=email, email_verified=email_verified, name=name, picture=None)


@pytest.fixture
def google_configured(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """All Google endpoints 503 when GOOGLE_CLIENT_ID is empty (the default in tests)."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    yield


def test_google_sign_in_returns_503_when_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # The client id ships with a real default in source; an explicit empty override
    # disables Google sign-in (e.g. for an environment that doesn't want it).
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    assert resp.status_code == 503


def test_google_sign_in_rejects_unverified_email(client: TestClient, google_configured: None) -> None:
    identity = _identity("g-sub-unv", "unv@example.com", email_verified=False)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    assert resp.status_code == 400


def test_google_sign_in_no_match_returns_signup_token(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    email = f"{_unique('newgoogle')}@example.com"
    identity = _identity("g-sub-new", email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("requires_signup") is True
    assert body["email"] == email
    assert body["signup_token"]
    assert body["suggested_username"]


def test_google_sign_in_email_match_returns_link_token(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    username = _unique("emailmatch")
    user = _create_user(db_session, username)
    identity = _identity("g-sub-match", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("requires_link") is True
    assert body["email"] == user.email
    assert body["has_totp"] is False
    assert body["link_token"]


def test_google_sign_in_existing_link_logs_in(client: TestClient, db_session: Session, google_configured: None) -> None:
    username = _unique("alreadylinked")
    user = _create_user(db_session, username)
    db_session.add(
        OAuthAccount(user_id=user.id, provider="google", provider_account_id="g-sub-existing", email=user.email)
    )
    db_session.commit()
    identity = _identity("g-sub-existing", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == username


def test_google_sign_in_existing_link_with_totp_returns_otp_token(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    username = _unique("totpgoogle")
    secret = pyotp.random_base32()
    user = _create_user(db_session, username, totp_secret=secret)
    db_session.add(OAuthAccount(user_id=user.id, provider="google", provider_account_id="g-sub-totp", email=user.email))
    db_session.commit()

    identity = _identity("g-sub-totp", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("requires_2fa") is True
    otp_token = body["otp_token"]

    # Wrong OTP rejected
    bad = client.post(OAUTH_2FA_PATH, json={"otp_token": otp_token, "otp": "000000"})
    assert bad.status_code == 401

    # Correct OTP succeeds
    code = pyotp.TOTP(secret).now()
    good = client.post(OAUTH_2FA_PATH, json={"otp_token": otp_token, "otp": code})
    assert good.status_code == 200, good.text
    assert good.json()["user"]["username"] == username


def test_google_link_succeeds_with_correct_password(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    username = _unique("linkme")
    user = _create_user(db_session, username, password="rightpw")
    identity = _identity("g-sub-link", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        link_resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    link_token = link_resp.json()["link_token"]

    resp = client.post(LINK_PATH, json={"link_token": link_token, "password": "rightpw"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["username"] == username
    # OAuth row was created
    row = (
        db_session.query(OAuthAccount)
        .filter(OAuthAccount.user_id == user.id, OAuthAccount.provider == "google")
        .first()
    )
    assert row is not None
    assert row.provider_account_id == "g-sub-link"


def test_google_link_rejects_wrong_password(client: TestClient, db_session: Session, google_configured: None) -> None:
    username = _unique("linkmebad")
    user = _create_user(db_session, username, password="rightpw")
    identity = _identity("g-sub-linkbad", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        link_token = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"}).json()["link_token"]

    resp = client.post(LINK_PATH, json={"link_token": link_token, "password": "wrongpw"})
    assert resp.status_code == 401


def test_google_link_requires_otp_when_2fa_enabled(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    username = _unique("link2fa")
    secret = pyotp.random_base32()
    user = _create_user(db_session, username, password="rightpw", totp_secret=secret)
    identity = _identity("g-sub-link2fa", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        body = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"}).json()
    assert body["has_totp"] is True
    link_token = body["link_token"]

    # Missing OTP
    no_otp = client.post(LINK_PATH, json={"link_token": link_token, "password": "rightpw"})
    assert no_otp.status_code == 400

    # Bad OTP
    bad_otp = client.post(LINK_PATH, json={"link_token": link_token, "password": "rightpw", "otp": "000000"})
    assert bad_otp.status_code == 401

    # Good OTP
    good_otp = client.post(
        LINK_PATH,
        json={"link_token": link_token, "password": "rightpw", "otp": pyotp.TOTP(secret).now()},
    )
    assert good_otp.status_code == 200


def test_google_signup_creates_user_with_no_password(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    email = f"{_unique('signupg')}@example.com"
    identity = _identity("g-sub-signup", email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        signup_token = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"}).json()["signup_token"]

    chosen = _unique("g_user")
    resp = client.post(SIGNUP_PATH, json={"signup_token": signup_token, "username": chosen})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["username"] == chosen
    assert body["user"]["email"] == email
    assert body["user"]["email_verified"] is True

    user = db_session.query(DBUser).filter(DBUser.username == chosen).first()
    assert user is not None
    assert user.hashed_password is None
    link = (
        db_session.query(OAuthAccount)
        .filter(OAuthAccount.user_id == user.id, OAuthAccount.provider_account_id == "g-sub-signup")
        .first()
    )
    assert link is not None


def test_google_signup_rejects_taken_username(client: TestClient, db_session: Session, google_configured: None) -> None:
    taken = _unique("takenname")
    _create_user(db_session, taken)

    email = f"{_unique('signup2')}@example.com"
    identity = _identity("g-sub-signup2", email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        signup_token = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"}).json()["signup_token"]

    resp = client.post(SIGNUP_PATH, json={"signup_token": signup_token, "username": taken})
    assert resp.status_code == 409


def test_oauth_2fa_rejects_invalid_token(client: TestClient, google_configured: None) -> None:
    resp = client.post(OAUTH_2FA_PATH, json={"otp_token": "not-a-jwt", "otp": "123456"})
    assert resp.status_code == 400


def test_google_connect_links_authenticated_user(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    username = _unique("connectme")
    user = _create_user(db_session, username)
    token = _login(client, username)

    # Different email at Google than at CarModPicker — allowed for connect.
    identity = _identity("g-sub-connect", f"{username}-google@example.com")
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(CONNECT_PATH, json={"id_token": "x", "nonce": "y"}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider"] == "google"

    # Now appears in /auth/oauth list.
    listed = client.get(OAUTH_LIST_PATH, headers=_auth(token))
    assert listed.status_code == 200
    assert any(a["provider"] == "google" for a in listed.json())


def test_google_connect_refuses_when_email_belongs_to_other_user(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    me = _create_user(db_session, _unique("connectme_a"))
    other = _create_user(db_session, _unique("connectme_b"))
    token = _login(client, me.username)

    # Google email matches `other`, not `me` — must refuse to preserve the invariant
    # that no two users share an email.
    identity = _identity("g-sub-conflict", other.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(CONNECT_PATH, json={"id_token": "x", "nonce": "y"}, headers=_auth(token))
    assert resp.status_code == 409
    assert "EMAIL_BELONGS_TO_OTHER_USER" in resp.text


def test_google_connect_refuses_if_already_linked_to_other_user(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    me = _create_user(db_session, _unique("conn_me"))
    other = _create_user(db_session, _unique("conn_other"))
    db_session.add(
        OAuthAccount(user_id=other.id, provider="google", provider_account_id="g-sub-stolen", email=other.email)
    )
    db_session.commit()
    token = _login(client, me.username)

    identity = _identity("g-sub-stolen", f"{me.username}-g@example.com")
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(CONNECT_PATH, json={"id_token": "x", "nonce": "y"}, headers=_auth(token))
    assert resp.status_code == 409


def test_google_connect_refuses_when_user_already_has_google(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    user = _create_user(db_session, _unique("dup"))
    db_session.add(
        OAuthAccount(user_id=user.id, provider="google", provider_account_id="g-sub-existing", email=user.email)
    )
    db_session.commit()
    token = _login(client, user.username)

    identity = _identity("g-sub-second", f"{user.username}-second@example.com")
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        resp = client.post(CONNECT_PATH, json={"id_token": "x", "nonce": "y"}, headers=_auth(token))
    assert resp.status_code == 409


def test_delete_oauth_account_succeeds_when_password_exists(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    user = _create_user(db_session, _unique("delok"))
    link = OAuthAccount(user_id=user.id, provider="google", provider_account_id="g-sub-delok", email=user.email)
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)
    token = _login(client, user.username)

    resp = client.delete(f"{OAUTH_LIST_PATH}/{link.id}", headers=_auth(token))
    assert resp.status_code == 200
    assert db_session.query(OAuthAccount).filter(OAuthAccount.id == link.id).first() is None


def test_delete_oauth_account_refuses_when_only_login_method(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    # OAuth-only user: no password, no passkeys, only one OAuth link → can't delete it.
    username = _unique("oauthonly")
    user = DBUser(
        username=username,
        email=f"{username}@example.com",
        hashed_password=None,
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    link = OAuthAccount(user_id=user.id, provider="google", provider_account_id="g-sub-only", email=user.email)
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)

    # Login this user via the OAuth path (no password) — use the Google sub already linked.
    identity = _identity("g-sub-only", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        login_resp = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"})
    token = login_resp.json()["access_token"]

    resp = client.delete(f"{OAUTH_LIST_PATH}/{link.id}", headers=_auth(token))
    assert resp.status_code == 400
    assert db_session.query(OAuthAccount).filter(OAuthAccount.id == link.id).first() is not None


def test_delete_oauth_account_allows_when_passkey_present(
    client: TestClient, db_session: Session, google_configured: None
) -> None:
    # OAuth-only user with a passkey — passkey is a valid alternative login, so deleting the
    # only OAuth account is allowed (they can still sign in with the passkey).
    username = _unique("oauthpasskey")
    user = DBUser(username=username, email=f"{username}@example.com", hashed_password=None, email_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    link = OAuthAccount(user_id=user.id, provider="google", provider_account_id="g-sub-pk", email=user.email)
    db_session.add(link)
    db_session.add(
        WebAuthnCredential(
            user_id=user.id,
            credential_id=b"fake-cred-id",
            public_key=b"fake-pubkey",
            sign_count=0,
            nickname="laptop",
        )
    )
    db_session.commit()
    db_session.refresh(link)

    identity = _identity("g-sub-pk", user.email)
    with patch("app.api.endpoints.auth.verify_google_id_token", return_value=identity):
        token = client.post(GOOGLE_PATH, json={"id_token": "x", "nonce": "y"}).json()["access_token"]

    resp = client.delete(f"{OAUTH_LIST_PATH}/{link.id}", headers=_auth(token))
    assert resp.status_code == 200
