"""Connexion base de données : engine, session factory et Base déclarative (SQLAlchemy 2.0)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Engine synchrone construit depuis l'URL de configuration (driver postgresql+psycopg).
# pool_pre_ping évite les connexions mortes après une coupure réseau / redémarrage DB.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

# Session factory. expire_on_commit=False garde les objets utilisables après commit.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI fournissant une session DB par requête.

    Usage : `def route(db: Session = Depends(get_db)) -> ...`
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
