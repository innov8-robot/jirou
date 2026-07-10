"""Primitives de sécurité : hachage de mot de passe et jetons JWT.

Regroupe toute la logique cryptographique (passlib/bcrypt pour les mots de
passe, python-jose pour les JWT access/refresh) afin qu'elle soit testable
et réutilisable en dehors des routes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt via passlib. ``deprecated="auto"`` permet un futur rehash transparent.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Types de jetons transportés dans le claim ``type``.
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


# --------------------------------------------------------------------------- #
# Mots de passe
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Retourne le hash bcrypt d'un mot de passe en clair."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond à son hash bcrypt."""
    return _pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    """Fabrique un JWT signé (claims standard ``sub``/``exp``/``iat`` + ``type``)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | int) -> str:
    """Crée un access token de courte durée (``ACCESS_TOKEN_EXPIRE_MINUTES``)."""
    return _create_token(
        str(subject),
        TOKEN_TYPE_ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str | int) -> str:
    """Crée un refresh token de longue durée (``REFRESH_TOKEN_EXPIRE_DAYS``)."""
    return _create_token(
        str(subject),
        TOKEN_TYPE_REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """Décode et valide un JWT.

    Vérifie la signature et l'expiration ; si ``expected_type`` est fourni,
    vérifie aussi le claim ``type``.

    :raises JWTError: jeton invalide, expiré ou de type inattendu.
    """
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if expected_type is not None and payload.get("type") != expected_type:
        raise JWTError(f"Type de jeton attendu '{expected_type}', reçu {payload.get('type')!r}")
    return payload


__all__ = [
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
