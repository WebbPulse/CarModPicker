"""Pydantic schemas for WebAuthn (passkey) endpoints.

Options and results are passed to/from the browser as JSON matching the
WebAuthn spec shape produced by py_webauthn's options_to_json helper. The
client hands the raw credential-response object back on verify — we don't
validate its internal structure server-side; py_webauthn does.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class WebAuthnRegisterOptionsRequest(BaseModel):
    nickname: str


class WebAuthnRegisterOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge_token: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    challenge_token: str
    credential: dict[str, Any]
    nickname: str


class WebAuthnLoginOptionsRequest(BaseModel):
    username: Optional[str] = None


class WebAuthnLoginOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge_token: str


class WebAuthnLoginVerifyRequest(BaseModel):
    challenge_token: str
    credential: dict[str, Any]


class WebAuthnCredentialSummary(BaseModel):
    id: UUID
    nickname: str
    aaguid: Optional[str] = None
    transports: Optional[list[str]] = None
    backup_eligible: bool
    backup_state: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebAuthnCredentialRename(BaseModel):
    nickname: str
