"""User registration and password-based authentication.

Passwords are hashed with bcrypt (industry standard, salted). The
plaintext password never leaves this module — callers receive either a
``User`` instance on success or an ``AuthError`` on failure.
"""

from __future__ import annotations

import re

import bcrypt

from app.database import User, get_user_by_email, session_scope

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Raised for any user-facing authentication failure."""


# ----- Hashing --------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash — fail closed.
        return False


# ----- Validation -----------------------------------------------------


def _normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def _validate_signup(email: str, password: str, confirm: str) -> None:
    email = _normalise_email(email)
    if not email or not EMAIL_RE.match(email):
        raise AuthError("Please enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if password != confirm:
        raise AuthError("Passwords do not match.")


# ----- Public API -----------------------------------------------------


def create_user(
    email: str,
    password: str,
    confirm: str,
    display_name: str | None = None,
) -> User:
    """Create a new account. Raises ``AuthError`` on validation failure
    or duplicate email."""
    _validate_signup(email, password, confirm)
    email = _normalise_email(email)

    with session_scope() as session:
        if get_user_by_email(session, email) is not None:
            raise AuthError("An account with that email already exists.")

        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=(display_name or "").strip() or None,
            periods=[],
        )
        session.add(user)
        session.flush()  # populate user.id
        session.refresh(user)
        # Detach so the caller can read attributes after the session closes.
        session.expunge(user)
        return user


def authenticate(email: str, password: str) -> User:
    """Return the matching ``User`` if credentials are valid, else
    raise ``AuthError``."""
    email = _normalise_email(email)
    if not email or not password:
        raise AuthError("Email and password are required.")

    with session_scope() as session:
        user = get_user_by_email(session, email)
        if user is None or not verify_password(password, user.password_hash):
            # Generic message — don't leak which half is wrong.
            raise AuthError("Invalid email or password.")
        session.expunge(user)
        return user
