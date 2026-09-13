"""Regression: a password over bcrypt's 72 byte limit must not fault.

bcrypt reads at most 72 bytes of a password and ignores the rest. What differs
between library versions is what happens when it is handed more: bcrypt 4.x
truncates silently, and bcrypt 5.0.0, which this app pins, raises

    ValueError: password cannot be longer than 72 bytes

A character is not a byte, so 72 accented, CJK or emoji characters are 144 bytes
or more. Such a password passed every character-counting length check, reached
`bcrypt.hashpw`, and became a 500. Signup, password reset and password change
were all affected.

`webbpulse.security` truncates to 72 **bytes** before bcrypt sees the value, on a
byte boundary rather than a character boundary, so these now hash and verify like
any other password. Byte truncation is what keeps the hash identical to what any
other implementation writes for the same input; trimming back to the last whole
character would feed bcrypt different bytes.

Row 13 of `docs/identity-adoption.md` deleted the four routers under `/api/auth`,
and the users domain follow up deleted `POST /api/users/` and the password change
on `PUT /api/users/{user_id}`. No route in this application takes a password any
more, so what is left here is the primitive: the hashing helpers that
`app/api/dependencies/auth.py` still exports. Every password-carrying route is
the identity package's, and the package's own tests cover them.
"""

from __future__ import annotations

from app.api.dependencies.auth import get_password_hash, verify_password

BCRYPT_BYTE_LIMIT = 72

OVER_LIMIT_PASSWORD = "é" * BCRYPT_BYTE_LIMIT


def test_the_test_password_is_the_shape_this_regression_is_about() -> None:
    """Guard the fixture itself: 72 characters, and over bcrypt's byte limit."""
    assert len(OVER_LIMIT_PASSWORD) == BCRYPT_BYTE_LIMIT
    assert len(OVER_LIMIT_PASSWORD.encode("utf-8")) > BCRYPT_BYTE_LIMIT


def test_hashing_a_password_over_72_bytes_does_not_raise() -> None:
    """The primitive itself. bcrypt 5 raised ValueError here before the swap."""
    hashed = get_password_hash(OVER_LIMIT_PASSWORD)

    assert hashed.startswith("$2")
    assert hashed.split("$")[2] == "12"
    assert verify_password(OVER_LIMIT_PASSWORD, hashed) is True


def test_a_wrong_password_still_fails_against_an_over_limit_hash() -> None:
    """Truncation must not turn verification into a rubber stamp."""
    hashed = get_password_hash(OVER_LIMIT_PASSWORD)

    assert verify_password("something else entirely", hashed) is False
