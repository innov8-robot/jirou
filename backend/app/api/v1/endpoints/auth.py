"""Endpoints d'authentification : register, login, refresh, me (+ démo guard)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_role
from app.core.database import get_db
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    RefreshRequest,
    TokenPair,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.services.user import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_id,
)

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
)
def register(data: UserRegister, db: DbSession) -> User:
    """Crée un utilisateur (rôle ``member`` par défaut). 409 si email déjà pris."""
    if get_user_by_email(db, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email.",
        )
    return create_user(db, data)


@router.post("/login", response_model=TokenPair, summary="Connexion (access + refresh)")
def login(data: UserLogin, db: DbSession) -> TokenPair:
    """Vérifie les identifiants et renvoie une paire de jetons. 401 si invalides."""
    user = authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenPair, summary="Rafraîchir l'access token")
def refresh(data: RefreshRequest, db: DbSession) -> TokenPair:
    """Renvoie un nouvel access token à partir d'un refresh token valide. 401 sinon."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalide ou expiré.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(data.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        subject = payload.get("sub")
        if subject is None:
            raise invalid
        user_id = int(subject)
    except (JWTError, ValueError) as exc:
        raise invalid from exc

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise invalid
    return TokenPair(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead, summary="Utilisateur courant")
def me(current_user: CurrentUser) -> User:
    """Renvoie l'utilisateur authentifié via le Bearer access token."""
    return current_user


@router.get(
    "/admin-check",
    summary="Démo du guard de rôle (admin uniquement)",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def admin_check() -> dict[str, str]:
    """Endpoint de démonstration : accessible aux seuls administrateurs (sinon 403)."""
    return {"status": "ok", "scope": "admin"}
