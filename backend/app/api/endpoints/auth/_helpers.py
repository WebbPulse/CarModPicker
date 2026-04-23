"""Cross-module auth helpers shared across sub-routers (D-18).

Used by core.py (login, 2FA login), oauth.py (Google sign-in, Google signup),
two_factor.py (2FA verify login). Leaf module — NO sibling sub-module imports
(Risk 4 mitigation). OAUTH_2FA_PURPOSE + GOOGLE_PROVIDER constants duplicated
here (matched verbatim in auth/oauth.py) to keep this module self-contained.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from app.api.dependencies.auth import (
    create_access_token,
    get_access_token_expires_delta_for_user,
)
from app.api.models.user import User as DBUser
from app.api.schemas.user import UserRead

logger = logging.getLogger(__name__)

# Duplicated from auth/oauth.py per planner decision (PATTERNS.md §9 Open Question):
# option (a) — duplicate constants to keep _helpers.py a leaf module.
# Source-of-truth for OAuth flows remains auth/oauth.py; any future change to
# these string values must update BOTH files (low-risk: string literals change rarely).
OAUTH_2FA_PURPOSE = "oauth_2fa"
GOOGLE_PROVIDER = "google"


def _issue_login_response(user: DBUser) -> dict[str, str | UserRead]:
    """Build the login response payload (access_token + user metadata).

    Source: auth.py:814-821 — copied verbatim (D-18).
    """
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=expires_delta)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


def _maybe_2fa_challenge(user: DBUser) -> Optional[dict[str, str | bool]]:
    """If user has TOTP enabled, mint an otp_token bound to them and return the challenge payload.

    Source: auth.py:824-832 — copied verbatim (D-18).
    """
    if not user.totp_enabled:
        return None
    otp_token = create_access_token(
        data={"purpose": OAUTH_2FA_PURPOSE, "user_id": str(user.id), "source": GOOGLE_PROVIDER},
        expires_delta=timedelta(minutes=5),
    )
    return {"requires_2fa": True, "otp_token": otp_token}
