"""Endpoints de gestion des jetons d'API personnels (``/users/me/tokens``).

Un jeton d'API authentifie un client non interactif — le serveur MCP branché sur
Claude Code, un script, une CI — avec les droits de son propriétaire, sans lui
confier le mot de passe du compte.

Ces routes exigent une **session interactive** (``CurrentSessionUser``) : un
jeton d'API ne peut ni en émettre d'autres ni révoquer ses pairs. Un jeton fuité
ne permet donc pas de se rendre persistant.

Le secret n'est renvoyé qu'à la création (``POST``) ; la liste ne porte que des
métadonnées. Il n'y a pas de « voir à nouveau » : un jeton perdu se révoque et se
recrée.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentSessionUser
from app.core.database import get_db
from app.schemas.api_token import ApiTokenCreate, ApiTokenCreated, ApiTokenRead
from app.services import api_token as api_token_service

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_TOKEN_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jeton introuvable.")


@router.get(
    "/me/tokens",
    response_model=list[ApiTokenRead],
    summary="Lister mes jetons d'API",
)
def list_my_tokens(current_user: CurrentSessionUser, db: DbSession) -> list[ApiTokenRead]:
    """Mes jetons, les plus récents d'abord (les révoqués restent listés).

    Ne renvoie jamais le secret — seulement son début (``prefix``) et ses
    métadonnées d'usage.
    """
    return [
        ApiTokenRead.model_validate(token)
        for token in api_token_service.list_tokens(db, current_user)
    ]


@router.post(
    "/me/tokens",
    response_model=ApiTokenCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un jeton d'API",
)
def create_my_token(
    data: ApiTokenCreate, current_user: CurrentSessionUser, db: DbSession
) -> ApiTokenCreated:
    """Crée un jeton et renvoie son secret — **affiché une seule fois**.

    ``expires_in_days`` borne la durée de vie ; absent, le jeton n'expire pas.
    Réservé à une session interactive (401 avec un jeton d'API).
    """
    token, raw = api_token_service.create_token(
        db,
        current_user,
        name=data.name,
        expires_in_days=data.expires_in_days,
    )
    return ApiTokenCreated(**ApiTokenRead.model_validate(token).model_dump(), token=raw)


@router.delete(
    "/me/tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révoquer un jeton d'API",
)
def revoke_my_token(token_id: int, current_user: CurrentSessionUser, db: DbSession) -> None:
    """Révoque un de mes jetons : l'accès est coupé immédiatement.

    Idempotent. 404 si le jeton est inconnu **ou** appartient à quelqu'un d'autre
    (ne pas révéler l'existence du jeton d'un tiers).
    """
    token = api_token_service.get_token(db, token_id)
    if token is None or token.user_id != current_user.id:
        raise _TOKEN_NOT_FOUND
    api_token_service.revoke_token(db, token)
