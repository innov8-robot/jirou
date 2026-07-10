"""Logique métier des projets et de leurs membres (EPIC-04, JIR-24 / JIR-25).

Les fonctions lèvent :class:`ProjectServiceError` pour les erreurs métier
(conflit, garde-fou dernier admin, ...). La couche endpoint les traduit en
codes HTTP. Les erreurs d'autorisation (403) et d'existence (404) du *projet*
sont gérées en amont par les dépendances de ``app.api.deps``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ProjectRole
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.user import get_user_by_email


@dataclass
class ProjectServiceError(Exception):
    """Erreur métier des projets, traduite en HTTP par la couche endpoint.

    ``code`` est une étiquette stable (``conflict``, ``not_found``,
    ``last_admin``) et ``message`` un texte lisible pour le champ ``detail``.
    """

    code: str
    message: str


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
def get_project(db: Session, project_id: int) -> Project | None:
    """Retourne le projet portant cet identifiant, ou ``None``."""
    return db.get(Project, project_id)


def get_membership(db: Session, project_id: int, user_id: int) -> ProjectMember | None:
    """Retourne l'appartenance (user, projet), ou ``None`` si non membre."""
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def count_members(db: Session, project_id: int) -> int:
    """Nombre de membres d'un projet."""
    stmt = (
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project_id)
    )
    return int(db.execute(stmt).scalar_one())


def count_admins(db: Session, project_id: int) -> int:
    """Nombre de membres ayant le rôle projet ``admin``."""
    stmt = (
        select(func.count())
        .select_from(ProjectMember)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == ProjectRole.ADMIN,
        )
    )
    return int(db.execute(stmt).scalar_one())


def list_projects_for_user(
    db: Session, user: User, *, include_archived: bool = False
) -> list[Project]:
    """Projets dont ``user`` est membre (les membres sont préchargés).

    Filtre les projets archivés sauf si ``include_archived`` est vrai.
    """
    stmt = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .options(selectinload(Project.members).selectinload(ProjectMember.user))
        .order_by(Project.id)
    )
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    return list(db.execute(stmt).scalars().all())


def list_members(db: Session, project_id: int) -> list[ProjectMember]:
    """Membres d'un projet, triés par date d'adhésion puis identifiant."""
    stmt = (
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at, ProjectMember.id)
    )
    return list(db.execute(stmt).scalars().all())


# --------------------------------------------------------------------------- #
# Écriture — projet
# --------------------------------------------------------------------------- #
def create_project(db: Session, data: ProjectCreate, creator: User) -> Project:
    """Crée un projet ; ``creator`` en devient le lead ET un membre ``admin``.

    Lève ``ProjectServiceError(code="conflict")`` si la clé est déjà prise.
    """
    if db.execute(select(Project).where(Project.key == data.key)).scalar_one_or_none():
        raise ProjectServiceError("conflict", "Cette clé de projet est déjà utilisée.")

    project = Project(
        name=data.name,
        key=data.key,
        description=data.description,
        color=data.color,
        lead_id=creator.id,
    )
    project.members.append(ProjectMember(user_id=creator.id, role=ProjectRole.ADMIN))
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, data: ProjectUpdate) -> Project:
    """Applique une mise à jour partielle (champs explicitement fournis)."""
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def archive_project(db: Session, project: Project) -> None:
    """Archivage logique (soft delete) : ``is_archived = True``."""
    project.is_archived = True
    db.commit()


# --------------------------------------------------------------------------- #
# Écriture — membres
# --------------------------------------------------------------------------- #
def add_member(db: Session, project: Project, email: str, role: ProjectRole) -> ProjectMember:
    """Ajoute un membre par email.

    Lève ``ProjectServiceError`` : ``not_found`` (email inconnu), ``conflict``
    (déjà membre).
    """
    user = get_user_by_email(db, email)
    if user is None:
        raise ProjectServiceError("not_found", "Aucun utilisateur avec cet email.")
    if get_membership(db, project.id, user.id) is not None:
        raise ProjectServiceError("conflict", "Cet utilisateur est déjà membre du projet.")

    member = ProjectMember(project_id=project.id, user_id=user.id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_member_role(
    db: Session, project: Project, user_id: int, role: ProjectRole
) -> ProjectMember:
    """Change le rôle d'un membre.

    Garde-fou : impossible de rétrograder le lead, ou de retirer le rôle
    ``admin`` au dernier admin du projet (``ProjectServiceError("last_admin")``).
    """
    member = get_membership(db, project.id, user_id)
    if member is None:
        raise ProjectServiceError("not_found", "Ce membre est introuvable dans le projet.")

    if role != ProjectRole.ADMIN:
        if user_id == project.lead_id:
            raise ProjectServiceError("last_admin", "Impossible de rétrograder le lead du projet.")
        if member.role == ProjectRole.ADMIN and count_admins(db, project.id) <= 1:
            raise ProjectServiceError(
                "last_admin", "Impossible de rétrograder le dernier admin du projet."
            )

    member.role = role
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, project: Project, user_id: int) -> None:
    """Retire un membre du projet.

    Garde-fou : impossible de retirer le lead, ou le dernier admin
    (``ProjectServiceError("last_admin")``).
    """
    member = get_membership(db, project.id, user_id)
    if member is None:
        raise ProjectServiceError("not_found", "Ce membre est introuvable dans le projet.")

    if user_id == project.lead_id:
        raise ProjectServiceError("last_admin", "Impossible de retirer le lead du projet.")
    if member.role == ProjectRole.ADMIN and count_admins(db, project.id) <= 1:
        raise ProjectServiceError("last_admin", "Impossible de retirer le dernier admin du projet.")

    db.delete(member)
    db.commit()
