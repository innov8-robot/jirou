"""Logique métier des jetons d'API personnels (accès machine à l'API).

Deux usages :

1. **gestion** — :func:`create_token`, :func:`list_tokens`, :func:`revoke_token`,
   appelés depuis ``/users/me/tokens`` (réservé à une session interactive) ;
2. **authentification** — :func:`authenticate` est appelée par la dépendance de
   sécurité à chaque requête portant un jeton, et résout l'utilisateur.

Le secret n'existe en clair qu'entre :func:`generate_token` et la réponse HTTP
de création : la base ne conserve que son empreinte SHA-256. SHA-256 (et non
bcrypt) est le bon choix ici — le jeton est un secret aléatoire de 256 bits, pas
un mot de passe devinable : il n'y a rien à ralentir pour un attaquant, et
l'empreinte doit être calculable à chaque requête sans coût.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_token import ApiToken
from app.models.user import User

# Préfixe des jetons : rend le secret reconnaissable dans un log ou un dépôt
# (et permet à la couche d'authentification de le distinguer d'un JWT).
TOKEN_PREFIX = "jir_pat_"

# Nombre d'octets d'entropie du secret (32 → 256 bits, ~43 caractères urlsafe).
_TOKEN_BYTES = 32

# Longueur du début de jeton conservé en clair pour l'affichage.
_DISPLAY_PREFIX_LEN = 12

# Granularité de rafraîchissement de ``last_used_at`` : évite une écriture en
# base à chaque appel d'API tout en gardant une trace utile.
_LAST_USED_REFRESH = timedelta(minutes=1)


def generate_token() -> str:
    """Génère un jeton en clair (``jir_pat_...``), jamais persisté tel quel."""
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(_TOKEN_BYTES)}"


def hash_token(token: str) -> str:
    """Empreinte SHA-256 hexadécimale d'un jeton en clair."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_api_token(credential: str) -> bool:
    """Vrai si ``credential`` a la forme d'un jeton d'API (et non d'un JWT)."""
    return credential.startswith(TOKEN_PREFIX)


def create_token(
    db: Session,
    user: User,
    *,
    name: str,
    expires_in_days: int | None = None,
) -> tuple[ApiToken, str]:
    """Crée un jeton pour ``user`` et retourne ``(ligne persistée, jeton en clair)``.

    Le jeton en clair est la **seule** occasion de le lire : l'appelant doit le
    transmettre à l'utilisateur immédiatement. ``expires_in_days`` à ``None``
    crée un jeton sans expiration.
    """
    raw = generate_token()
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days is not None else None
    )
    token = ApiToken(
        user_id=user.id,
        name=name,
        token_hash=hash_token(raw),
        prefix=raw[:_DISPLAY_PREFIX_LEN],
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, raw


def list_tokens(db: Session, user: User) -> list[ApiToken]:
    """Jetons de ``user``, les plus récents d'abord (révoqués inclus)."""
    stmt = (
        select(ApiToken)
        .where(ApiToken.user_id == user.id)
        .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_token(db: Session, token_id: int) -> ApiToken | None:
    """Retourne le jeton portant cet identifiant, ou ``None``."""
    return db.get(ApiToken, token_id)


def revoke_token(db: Session, token: ApiToken) -> ApiToken:
    """Révoque un jeton (idempotent : une seconde révocation ne change rien)."""
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        db.commit()
        db.refresh(token)
    return token


def is_usable(token: ApiToken, *, now: datetime | None = None) -> bool:
    """Vrai si le jeton n'est ni révoqué ni expiré."""
    moment = now or datetime.now(UTC)
    if token.revoked_at is not None:
        return False
    return token.expires_at is None or token.expires_at > moment


def authenticate(db: Session, raw_token: str) -> User | None:
    """Résout l'utilisateur derrière un jeton en clair, ou ``None``.

    Retourne ``None`` si le jeton est inconnu, révoqué, expiré, ou si son
    propriétaire est désactivé — l'appelant traduit cela en 401 sans distinguer
    les cas (ne pas renseigner un attaquant sur la validité d'un secret).

    Effet de bord : rafraîchit ``last_used_at``, au plus une fois par minute.
    """
    stmt = select(ApiToken).where(ApiToken.token_hash == hash_token(raw_token))
    token = db.execute(stmt).scalar_one_or_none()
    if token is None:
        return None

    now = datetime.now(UTC)
    if not is_usable(token, now=now):
        return None

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return None

    if token.last_used_at is None or now - token.last_used_at > _LAST_USED_REFRESH:
        token.last_used_at = now
        db.commit()
    return user
