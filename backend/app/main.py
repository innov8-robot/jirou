"""Point d'entrée de l'application FastAPI (objet `app`)."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import get_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS configuré depuis la liste d'origines de la config.
# ``expose_headers`` : le front étant sur une autre origine que l'API, le
# navigateur ne laisse lire ``Content-Disposition`` que s'il est explicitement
# exposé — nécessaire pour reprendre le nom de fichier proposé lors d'un
# téléchargement (ex. l'archive d'export de la veille).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Routes métier versionnées sous /api/v1.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Sonde de vivacité — ne dépend pas de la base de données."""
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Sonde de disponibilité de la base de données (ping SELECT 1)."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
