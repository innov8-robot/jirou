"""Fixtures pytest : base de données de test isolée + TestClient FastAPI.

Stratégie d'isolation : chaque test s'exécute dans une transaction ouverte sur
une connexion dédiée, avec un SAVEPOINT interne restauré après chaque
``commit()`` applicatif. En fin de test, la transaction externe est annulée
(rollback), ce qui laisse la base vierge — tests isolés et rejouables.

L'URL de base est lue depuis ``DATABASE_URL`` (fournie par la CI / un Postgres
jetable) ou, à défaut, depuis la config applicative. Les tables sont créées via
``Base.metadata.create_all`` au démarrage de la session de tests.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Importer le package des modèles enregistre les tables sur Base.metadata.
import app.models  # noqa: F401  (effet de bord : peuplement du metadata)
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.enums import UserRole
from app.models.user import User


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Engine partagé pour la session de tests ; crée puis supprime les tables."""
    url = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
    eng = create_engine(url, pool_pre_ping=True, future=True)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """Session transactionnelle annulée après chaque test (isolation stricte)."""
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection, autoflush=False, expire_on_commit=False, class_=Session
    )
    session = session_factory()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # noqa: ANN001
        # Recrée un SAVEPOINT dès que celui-ci est consommé par un commit()
        # applicatif, afin que la transaction externe reste ouverte.
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient FastAPI avec la dépendance ``get_db`` surchargée sur la session de test."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


ADMIN_PASSWORD = "adminpwd123"


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Insère directement un utilisateur ``admin`` en base (register crée un member)."""
    user = User(
        email="root@example.com",
        hashed_password=hash_password(ADMIN_PASSWORD),
        full_name="Root Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(client: TestClient, admin_user: User) -> str:
    """Access token d'un administrateur (via le flux de login standard)."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
