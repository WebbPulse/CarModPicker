"""Google OAuth endpoints: sign-in, signup, link, connect, 2FA, account list/delete."""

from __future__ import annotations

import binascii
import logging
import uuid
from datetime import timedelta
from typing import Any

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_current_user,
    verify_password,
)
from app.api.endpoints.auth._helpers import issue_login_response, maybe_2fa_challenge
from app.api.models.oauth_account import OAuthAccount
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.api.schemas.auth import (
    GoogleConnectRequest,
    GoogleLinkRequest,
    GoogleSignInLinkRequired,
    GoogleSignInRequest,
    GoogleSignInSignupRequired,
    GoogleSignupRequest,
    OAuthAccountRead,
    OAuthTwoFactorRequest,
)
from app.api.schemas.user import UserRead
from app.api.utils.google_oauth import GoogleIdentity, GoogleTokenError, verify_google_id_token
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Google-specific helpers (D-20 — stay in this module) ---

GOOGLE_LINK_PURPOSE = "google_link"
GOOGLE_SIGNUP_PURPOSE = "google_signup"
OAUTH_2FA_PURPOSE = "oauth_2fa"  # Duplicated in _helpers.py per planner decision
GOOGLE_PROVIDER = "google"  # Duplicated in _helpers.py per planner decision


def _ensure_google_enabled() -> None:
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )


def _verify_google_or_400(id_token_str: str, nonce: str, logger: logging.Logger) -> GoogleIdentity:
    try:
        identity = verify_google_id_token(id_token_str, nonce, settings.GOOGLE_CLIENT_ID)
    except GoogleTokenError as e:
        logger.warning(f"Google id_token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    if not identity.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified",
        )
    return identity


def _suggest_username(email: str, db: Session) -> str:
    """Build a username suggestion from the email local-part. Caller still validates uniqueness."""
    local = email.split("@", 1)[0].lower()
    base = "".join(ch for ch in local if ch.isalnum() or ch in ("_", "-", ".")) or "user"
    candidate = base
    suffix = 1
    while db.scalars(select(DBUser).where(DBUser.username == candidate)).first() is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
        if suffix > 100:
            # Give up on auto-numbering; user picks one. Returning the base is fine —
            # the signup endpoint will reject it if still taken and the form will reprompt.
            return base
    return candidate


def _decode_purpose_token(token: str, expected_purpose: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from e
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    return payload


@router.post("/google")
async def google_sign_in(
    request: GoogleSignInRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify a Google ID token and route to the right next step.

    Outcomes:
      - Google `sub` is already linked → log the user in (or 2FA challenge).
      - Email matches an existing user → return a `link_token`; client prompts for password.
      - No match → return a `signup_token`; client collects a username.
    """
    _ensure_google_enabled()
    identity = _verify_google_or_400(request.id_token, request.nonce, logger)

    existing_link = db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == identity.sub,
        )
    ).first()
    if existing_link is not None:
        user = db.scalars(select(DBUser).where(DBUser.id == existing_link.user_id)).first()
        if user is None:
            logger.error(f"OAuth link {existing_link.id} points to missing user {existing_link.user_id}")
            ResponsePatterns.raise_unauthorized("Account not available")
        if user.disabled:
            ResponsePatterns.raise_bad_request("Inactive user")
        if user.is_service_account:
            ResponsePatterns.raise_unauthorized("Account not available")
        challenge = maybe_2fa_challenge(user)
        if challenge is not None:
            logger.info(f"Google sign-in: 2FA required for user {user.username}")
            return challenge
        logger.info(f"Google sign-in: existing link, logging in user {user.username}")
        return issue_login_response(user)

    email_match = db.scalars(select(DBUser).where(DBUser.email == identity.email)).first()
    if email_match is not None:
        if email_match.disabled or email_match.is_service_account:
            ResponsePatterns.raise_bad_request("Account not available")
        link_token = create_access_token(
            data={
                "purpose": GOOGLE_LINK_PURPOSE,
                "google_sub": identity.sub,
                "email": identity.email,
            },
            expires_delta=timedelta(minutes=10),
        )
        logger.info(f"Google sign-in: email match for {identity.email}, link required")
        return GoogleSignInLinkRequired(
            link_token=link_token,
            email=identity.email,
            display_name=identity.name,
            has_totp=email_match.totp_enabled,
        ).model_dump()

    signup_token = create_access_token(
        data={
            "purpose": GOOGLE_SIGNUP_PURPOSE,
            "google_sub": identity.sub,
            "email": identity.email,
        },
        expires_delta=timedelta(minutes=15),
    )
    suggested_username = _suggest_username(identity.email, db)
    logger.info(f"Google sign-in: no match for {identity.email}, signup required")
    return GoogleSignInSignupRequired(
        signup_token=signup_token,
        email=identity.email,
        suggested_username=suggested_username,
    ).model_dump()


@router.post("/google/link")
async def google_link(
    request: GoogleLinkRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Merge a Google identity into an existing password account.

    Required after the initial /auth/google call returned `requires_link: true`.
    Verifies the user's password (and OTP if 2FA is enabled), creates the oauth_accounts row,
    and returns an access token.
    """
    _ensure_google_enabled()
    payload = _decode_purpose_token(request.link_token, GOOGLE_LINK_PURPOSE)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    user = db.scalars(select(DBUser).where(DBUser.email == email)).first()
    if user is None or user.disabled or user.is_service_account:
        ResponsePatterns.raise_unauthorized("Account not available")
    assert user is not None  # for type checker

    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Google link: bad password for user {user.username}")
        ResponsePatterns.raise_unauthorized("Incorrect password")

    if user.totp_enabled:
        if not request.otp:
            ResponsePatterns.raise_bad_request("OTP required")
        if not user.totp_secret:
            logger.error(f"2FA enabled but no secret for user {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")
        # WR-06: split into (a) construct TOTP, (b) verify code — mirrors
        # ``verify_2fa`` (line ~419-434). Previously a single try/except wrapped
        # both calls, so a verify-time secret-format error would surface as
        # "Invalid OTP code" via the unauthorized helper while a construct-time
        # error surfaced as "2FA configuration error". Splitting keeps each
        # error message accurately scoped to its failure mode.
        try:
            totp = pyotp.TOTP(user.totp_secret)
        except (ValueError, TypeError, binascii.Error):
            logger.error(f"Invalid TOTP secret format for user: {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")

        try:
            if not totp.verify(request.otp, valid_window=1):
                ResponsePatterns.raise_unauthorized("Invalid OTP code")
        except (ValueError, TypeError, binascii.Error):
            logger.error(f"TOTP verification failed for user: {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")

    # Race-safety: another concurrent link could have inserted the row. Check both
    # constraints we'll hit and return clear errors instead of a 500 IntegrityError.
    if (
        db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.provider == GOOGLE_PROVIDER,
                OAuthAccount.provider_account_id == google_sub,
            )
        ).first()
        is not None
    ):
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")
    if (
        db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user.id,
                OAuthAccount.provider == GOOGLE_PROVIDER,
            )
        ).first()
        is not None
    ):
        ResponsePatterns.raise_conflict("Account already has Google linked", "OAUTH_ACCOUNT_EXISTS")

    link = OAuthAccount(
        user_id=user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=google_sub,
        email=email,
    )
    db.add(link)
    db.commit()
    logger.info(f"Google linked to existing user {user.username}")
    return issue_login_response(user)


@router.post("/google/signup")
async def google_signup(
    request: GoogleSignupRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Create a brand-new account from a Google identity. The email had no existing match
    when /auth/google was called; the client collected a username and submits it here.
    """
    _ensure_google_enabled()
    payload = _decode_purpose_token(request.signup_token, GOOGLE_SIGNUP_PURPOSE)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    username = request.username.strip()
    if not username:
        ResponsePatterns.raise_bad_request("Username cannot be empty")

    if db.scalars(select(DBUser).where(DBUser.username == username)).first() is not None:
        ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")
    if db.scalars(select(DBUser).where(DBUser.email == email)).first() is not None:
        # Race: someone else (or another tab) signed up with this email between the initial
        # call and this one. Force them through the merge flow instead.
        ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")
    if (
        db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.provider == GOOGLE_PROVIDER,
                OAuthAccount.provider_account_id == google_sub,
            )
        ).first()
        is not None
    ):
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")

    user = DBUser(
        username=username,
        email=email,
        hashed_password=None,
        email_verified=True,
    )
    db.add(user)
    db.flush()  # populate user.id without committing yet
    link = OAuthAccount(
        user_id=user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=google_sub,
        email=email,
    )
    db.add(link)
    db.commit()
    db.refresh(user)
    logger.info(f"Google signup: created user {user.username} (email {user.email})")
    return issue_login_response(user)


@router.post("/2fa")
async def oauth_two_factor(
    request: OAuthTwoFactorRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Complete 2FA after an OAuth sign-in. Accepts the otp_token + OTP only — no password,
    since OAuth-only users may not have one.
    """
    payload = _decode_purpose_token(request.otp_token, OAUTH_2FA_PURPOSE)
    user_id_str = payload.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from e

    user = db.scalars(select(DBUser).where(DBUser.id == user_uuid)).first()
    if user is None or user.disabled or user.is_service_account:
        ResponsePatterns.raise_unauthorized("Account not available")
    assert user is not None
    if not user.totp_enabled or not user.totp_secret:
        ResponsePatterns.raise_bad_request("2FA is not enabled for this user")

    try:
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(request.otp, valid_window=1):
            ResponsePatterns.raise_unauthorized("Invalid OTP code")
    except (ValueError, TypeError, binascii.Error):
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    logger.info(f"OAuth 2FA completed for user {user.username}")
    return issue_login_response(user)


@router.post("/google/connect", response_model=OAuthAccountRead)
async def google_connect(
    request: GoogleConnectRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OAuthAccountRead:
    """Link a Google account to the *currently logged-in* user.

    Refuses if the Google email matches a *different* user — the user must instead sign out
    and use the merge flow from the login page. This preserves the invariant that no two
    accounts share an email.
    """
    _ensure_google_enabled()
    identity = _verify_google_or_400(request.id_token, request.nonce, logger)

    existing_link = db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == identity.sub,
        )
    ).first()
    if existing_link is not None:
        if existing_link.user_id == current_user.id:
            ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")
        ResponsePatterns.raise_conflict(
            "This Google account is linked to a different user", "OAUTH_LINKED_TO_OTHER_USER"
        )

    if (
        db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id,
                OAuthAccount.provider == GOOGLE_PROVIDER,
            )
        ).first()
        is not None
    ):
        ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")

    email_match = db.scalars(select(DBUser).where(DBUser.email == identity.email)).first()
    if email_match is not None and email_match.id != current_user.id:
        ResponsePatterns.raise_conflict(
            "Another account already uses this Google email — sign out and use 'Sign in with Google' to merge.",
            "EMAIL_BELONGS_TO_OTHER_USER",
        )

    link = OAuthAccount(
        user_id=current_user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=identity.sub,
        email=identity.email,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    logger.info(f"Google connected to user {current_user.username}")
    return OAuthAccountRead.model_validate(link)


@router.get("", response_model=list[OAuthAccountRead])
async def list_oauth_accounts(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OAuthAccountRead]:
    rows = list(
        db.scalars(
            select(OAuthAccount).where(OAuthAccount.user_id == current_user.id).order_by(OAuthAccount.created_at.desc())
        ).all()
    )
    return [OAuthAccountRead.model_validate(r) for r in rows]


@router.delete("/{account_id}")
async def delete_oauth_account(
    account_id: uuid.UUID,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Remove a linked OAuth provider.

    Refuses if removing it would leave the user with no way to sign in: no password set,
    no other linked OAuth accounts, and no passkeys.
    """
    link = db.scalars(
        select(OAuthAccount).where(OAuthAccount.id == account_id, OAuthAccount.user_id == current_user.id)
    ).first()
    if link is None:
        ResponsePatterns.raise_not_found("OAuth account")
    assert link is not None

    if not current_user.hashed_password:
        other_oauth = db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id,
                OAuthAccount.id != link.id,
            )
        ).first()
        passkey = db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == current_user.id)).first()
        if other_oauth is None and passkey is None:
            ResponsePatterns.raise_bad_request(
                "Set a password or register a passkey before removing your only sign-in method"
            )

    db.delete(link)
    db.commit()
    logger.info(f"OAuth account {account_id} removed (user {current_user.username})")
    return {"message": "Connected account removed"}
