"""Test du script de seed ``scripts.create_admin`` (fonction principale)."""

from __future__ import annotations

from scripts.create_admin import create_or_promote_admin
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User

VALID_PASSWORD = "s3cretpwd"


def test_create_admin_creates_new_user(db_session: Session) -> None:
    user, action = create_or_promote_admin(
        db_session, "seed-admin@example.com", "seedpwd123", "Seed Admin"
    )
    assert action == "created"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.email == "seed-admin@example.com"
    assert verify_password("seedpwd123", user.hashed_password)


def test_create_admin_is_idempotent(db_session: Session) -> None:
    create_or_promote_admin(db_session, "again@example.com", "pwd12345", "Again")
    user, action = create_or_promote_admin(db_session, "again@example.com", "ignored-pwd", "Again")
    assert action == "promoted"
    assert user.role == UserRole.ADMIN
    # Le mot de passe d'origine reste inchangé lors d'une promotion.
    assert verify_password("pwd12345", user.hashed_password)


def test_create_admin_promotes_existing_member(db_session: Session) -> None:
    existing = User(
        email="member-to-promote@example.com",
        hashed_password=hash_password(VALID_PASSWORD),
        full_name="Member",
        role=UserRole.MEMBER,
    )
    db_session.add(existing)
    db_session.commit()

    user, action = create_or_promote_admin(
        db_session, "member-to-promote@example.com", "whatever", "Member"
    )
    assert action == "promoted"
    assert user.id == existing.id
    assert user.role == UserRole.ADMIN
