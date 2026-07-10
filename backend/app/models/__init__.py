"""Modèles ORM SQLAlchemy.

Importer ici chaque modèle pour qu'il soit enregistré sur `Base.metadata`
et détecté par l'autogenerate d'Alembic (voir alembic/env.py).
"""

from __future__ import annotations

from app.models.activity import ActivityLog
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.dependency import IssueDependency
from app.models.enums import (
    DependencyType,
    IssuePriority,
    IssueStatus,
    IssueType,
    NotificationType,
    ProjectRole,
    SprintStatus,
    UserRole,
)
from app.models.issue import Issue, Label, issue_labels
from app.models.notification import Notification
from app.models.project import Project, ProjectMember
from app.models.saved_view import SavedView
from app.models.sprint import Sprint
from app.models.user import User

__all__ = [
    "ActivityLog",
    "Attachment",
    "Comment",
    "DependencyType",
    "Issue",
    "IssueDependency",
    "IssuePriority",
    "IssueStatus",
    "IssueType",
    "Label",
    "Notification",
    "NotificationType",
    "Project",
    "ProjectMember",
    "ProjectRole",
    "SavedView",
    "Sprint",
    "SprintStatus",
    "User",
    "UserRole",
    "issue_labels",
]
