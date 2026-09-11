"""Authentication dependencies for resolving the caller from a request."""

import hmac
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from webbpulse.log_context import user_id_var
from webbpulse.security import (
    create_token,
    decode_token,
    hash_password,
)
from webbpulse.security import verify_password as _verify_password

from app.api.dependencies.identity_claims import (
    identity_subject,
    verify_bearer_subject,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.core.config import settings
from app.db.dynamo.users import User as DBUser

ALGORITHM = settings.JWT_ALGORITHM

__all__ = [
    "ALGORITHM",
    "create_access_token",
    "decode_access_token",
    "get_current_active_user_optional",
    "get_current_admin_user",
    "get_current_superuser",
    "get_current_user",
    "get_optional_current_user",
    "get_password_hash",
    "require_api_key_or_admin",
    "resolve_identity_user",
    "verify_api_key",
    "verify_password",
]


class IdentityAwareOAuth2(OAuth2PasswordBearer):
    """`OAuth2PasswordBearer` that does not refuse a request an authorizer vouched for."""

    async def __call__(self, request: Request) -> Optional[str]:
        """Return the bearer token, treating an authorizer vouched request as authenticated."""
        if request.headers.get("authorization"):
            return await super().__call__(request)
        if identity_subject(request):
            return ""
        return await super().__call__(request)


oauth2_scheme = IdentityAwareOAuth2(tokenUrl=f"{settings.API_STR}/auth/token", scheme_name="OAuth2PasswordBearer")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/token", auto_error=False)


def get_password_hash(password: str) -> str:
    """Hashes a plain password with bcrypt at cost 12."""
    return hash_password(password)


def verify_password(plain_password: str, hashed_password_str: Optional[str]) -> bool:
    """Verifies a plain password against a hashed password.

    Returns False if the user has no password set (OAuth-only account), which is
    a real state here rather than an error, and False rather than raising on a
    """
    return _verify_password(plain_password, hashed_password_str)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Sign a short lived HS256 token with `SECRET_KEY`.

    Not a session token since row 13. The only caller is the one-click
    unsubscribe link that `app/core/email.py` signs into price drop alert
    emails, which no identity access token can replace.
    """
    return create_token(
        data,
        settings.SECRET_KEY,
        expires_in=(
            expires_delta if expires_delta is not None else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        ),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify a token minted by `create_access_token` and return its claims.

    Raises `webbpulse.security.ExpiredToken` or `InvalidToken`, both of which
    are `TokenError`. The only caller since row 13 is the price alert
    unsubscribe route; no resolver in this module decodes anything.
    """
    return decode_token(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def _subject_from_request(request: Optional[Request]) -> str:
    """The identity `sub` for this request, from the authorizer or from the header.

    Two sources in order, which is the order `app/composition/identity_extension.
    py` already reads one in. The authorizer's context is preferred where the
    """
    if request is None:
        return ""
    subject = identity_subject(request)
    if subject:
        return subject
    return verify_bearer_subject(request)


def resolve_identity_user(request: Optional[Request], repos: Repositories) -> Optional[DBUser]:
    """The CarModPicker user an identity access token names, or `None`.

    **The mapping is the id and nothing else.** `CarModPickerIdentityHooks.
    claims_for` puts `roles` and `username` in the token and leaves `sub` to the
    """
    subject = _subject_from_request(request)
    if not subject:
        return None
    try:
        user_id = UUID(subject)
    except (AttributeError, TypeError, ValueError):
        return None

    user = repos.users.get(user_id)
    if user is None or user.disabled or not user.email_verified:
        return None
    user_id_var.set(str(user.id))
    return user


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    repos: Repositories = Depends(get_repositories),
) -> DBUser:
    """The user this request is for, or 401.

    Identity only since row 13, from authorizer claims or a verified Bearer
    token. `token` stays in the signature to keep `oauth2_scheme` in the
    dependency tree so the published security scheme is unchanged.
    """
    user = resolve_identity_user(request, repos)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """The user this request is for, or `None` for an anonymous caller.

    Identity only since row 13, and `None` rather than a raise for every way
    the answer can be nobody, which is what keeps a public page public.
    """
    return resolve_identity_user(request, repos)


async def get_current_active_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """The current active user if one is authenticated, otherwise `None`.

    Identity only since row 13, which collapsed its behaviour into
    `get_optional_current_user`. Kept as its own name so a later divergence
    is a change to one function rather than an unpicking of an alias.
    """
    return resolve_identity_user(request, repos)


async def get_current_admin_user(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Dependency that requires the current user to be an admin.
    """
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_superuser(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Dependency that requires the current user to be a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


API_KEY_HEADER = "X-API-Key"

api_key_header_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def verify_api_key(presented: Optional[str]) -> bool:
    """True when `presented` matches the configured `EXTENSION_API_KEY`.

    Compared with `hmac.compare_digest` so the check does not leak the key
    through its own timing. An unconfigured (empty) key never matches, so a
    """
    if not presented:
        return False
    configured = settings.EXTENSION_API_KEY
    if not configured:
        return False
    return hmac.compare_digest(presented, configured)


async def require_api_key_or_admin(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header_scheme),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    repos: Repositories = Depends(get_repositories),
) -> Optional[DBUser]:
    """Allow a valid `X-API-Key`, or an admin identity token, and nothing else.

    Returns the authenticated admin user, or `None` when the caller got in on
    the API key (there is no user behind a machine credential). Raises through
    the app's normal `HTTPException` path: no credential or a bad key with no
    token is a 401, and a valid token for a non-admin user is a 403. The API
    key is checked first and is a complete credential on its own. `token` is
    unread since row 13; `resolve_identity_user` reads both sources.
    """
    if verify_api_key(api_key):
        return None

    identity_user = resolve_identity_user(request, repos)
    if identity_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await get_current_admin_user(current_user=identity_user)
