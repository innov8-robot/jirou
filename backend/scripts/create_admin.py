"""Crée (ou promeut) un utilisateur administrateur — script de seed idempotent.

Usage ::

    python -m scripts.create_admin
    # ou
    python scripts/create_admin.py

Variables d'environnement (avec valeurs par défaut) ::

    ADMIN_EMAIL     (défaut: admin@jirou.app)
    ADMIN_PASSWORD  (défaut: admin_dev_password)
    ADMIN_NAME      (défaut: Jirou Admin)

Comportement idempotent : si l'email existe déjà, l'utilisateur est promu
administrateur (et réactivé) sans toucher à son mot de passe ; sinon il est créé
avec le rôle ``admin``.
"""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.services.user import get_user_by_email

# NB : éviter les TLD réservés (.local/.test) — rejetés par la validation
# EmailStr au login. On utilise un domaine valide par défaut.
DEFAULT_EMAIL = "admin@jirou.app"
DEFAULT_PASSWORD = "admin_dev_password"  # noqa: S105 - valeur de dev par défaut, à changer en prod
DEFAULT_NAME = "Jirou Admin"


def create_or_promote_admin(
    db: Session,
    email: str,
    password: str,
    full_name: str,
) -> tuple[User, str]:
    """Crée un admin, ou promeut l'utilisateur existant.

    Retourne ``(user, action)`` où ``action`` vaut ``"created"`` ou
    ``"promoted"`` (ce dernier même si l'utilisateur était déjà admin).
    """
    existing = get_user_by_email(db, email)
    if existing is not None:
        existing.role = UserRole.ADMIN
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing, "promoted"

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, "created"


def main() -> None:
    """Point d'entrée CLI : lit l'environnement et applique le seed."""
    email = os.environ.get("ADMIN_EMAIL", DEFAULT_EMAIL)
    password = os.environ.get("ADMIN_PASSWORD", DEFAULT_PASSWORD)
    full_name = os.environ.get("ADMIN_NAME", DEFAULT_NAME)

    db = SessionLocal()
    try:
        user, action = create_or_promote_admin(db, email, password, full_name)
    finally:
        db.close()

    if action == "created":
        print(f"[create_admin] Administrateur créé : {user.email} (id={user.id}).")
    else:
        print(
            f"[create_admin] Utilisateur existant promu administrateur : "
            f"{user.email} (id={user.id}). Mot de passe inchangé."
        )


if __name__ == "__main__":
    main()
