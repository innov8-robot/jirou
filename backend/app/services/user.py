"""Logique métier autour des utilisateurs (persistance + authentification)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserRegister
from app.schemas.user import UserAdminUpdate, UserProfileUpdate


def get_user_by_email(db: Session, email: str) -> User | None:
    """Retourne l'utilisateur portant cet email, ou ``None``."""
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Retourne l'utilisateur portant cet identifiant, ou ``None``."""
    return db.get(User, user_id)


def create_user(db: Session, data: UserRegister) -> User:
    """Crée et persiste un utilisateur à partir d'un payload d'inscription.

    Le mot de passe est haché avant stockage. L'appelant est responsable de
    vérifier au préalable l'unicité de l'email (voir ``get_user_by_email``).
    """
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Retourne l'utilisateur si les identifiants sont valides, sinon ``None``."""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Liste paginée des utilisateurs, triés par identifiant croissant."""
    stmt = select(User).order_by(User.id).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_profile(db: Session, user: User, data: UserProfileUpdate) -> User:
    """Applique une mise à jour partielle du profil (champs fournis seulement)."""
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
    """Change le mot de passe si ``current_password`` est correct.

    Retourne ``True`` en cas de succès, ``False`` si le mot de passe actuel est
    invalide (aucune modification n'est alors persistée).
    """
    if not verify_password(current_password, user.hashed_password):
        return False
    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def admin_update_user(db: Session, user: User, data: UserAdminUpdate) -> User:
    """Applique une mise à jour d'administration (rôle / activation) sur ``user``."""
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
