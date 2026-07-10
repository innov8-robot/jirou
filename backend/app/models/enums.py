"""Énumérations réutilisables partagées par les modèles ORM."""

from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    """Rôle global d'un utilisateur (voir docs/CONVENTIONS.md).

    ``StrEnum`` assure une sérialisation/validation transparente côté Pydantic
    et une valeur lisible en base.
    """

    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class IssueType(enum.StrEnum):
    """Type d'un ticket (EPIC-05, JIR-30).

    - ``epic``  : conteneur regroupant des enfants (story/task/bug).
    - ``story`` : besoin fonctionnel.
    - ``task``  : tâche technique.
    - ``bug``   : anomalie.
    """

    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    BUG = "bug"


class IssueStatus(enum.StrEnum):
    """Statut d'un ticket dans le workflow (EPIC-05)."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class IssuePriority(enum.StrEnum):
    """Priorité d'un ticket (EPIC-05)."""

    HIGHEST = "highest"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    LOWEST = "lowest"


class SprintStatus(enum.StrEnum):
    """Statut d'un sprint dans son cycle de vie (EPIC-07, JIR-47).

    Cycle : ``future`` (planifié) → ``active`` (en cours, un seul par projet) →
    ``completed`` (clôturé, archivé pour la vélocité).
    """

    FUTURE = "future"
    ACTIVE = "active"
    COMPLETED = "completed"


class DependencyType(enum.StrEnum):
    """Type d'une dépendance entre deux tickets (EPIC-08, JIR-61).

    - ``blocks`` : l'issue *from* **bloque** l'issue *to* (l'unique type pour
      l'instant, valeur par défaut).
    """

    BLOCKS = "blocks"


class NotificationType(enum.StrEnum):
    """Type d'une notification in-app (EPIC-09, JIR-67).

    - ``mention``    : l'utilisateur a été mentionné dans un commentaire.
    - ``assignment`` : l'utilisateur a été assigné à un ticket.
    """

    MENTION = "mention"
    ASSIGNMENT = "assignment"


class WatchStatus(enum.StrEnum):
    """Statut d'un nœud de veille R&D (domaine VEILLE).

    - ``to_test``     : piste identifiée, à évaluer.
    - ``in_progress`` : exploration en cours.
    - ``promising``   : prometteur, à approfondir.
    - ``abandoned``   : écarté.
    """

    TO_TEST = "to_test"
    IN_PROGRESS = "in_progress"
    PROMISING = "promising"
    ABANDONED = "abandoned"


class WatchMediaKind(enum.StrEnum):
    """Nature d'un média rattaché à un nœud de veille (domaine VEILLE).

    - ``image`` : fichier image téléversé.
    - ``video`` : fichier vidéo téléversé.
    - ``link``  : lien externe (ex. YouTube) — porté par ``url``.
    """

    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"


class WatchNodeType(enum.StrEnum):
    """Type d'un nœud de veille R&D (domaine VEILLE).

    Permet de catégoriser les nœuds « custom » côté frontend.

    - ``theme``    : thème/axe de veille (valeur par défaut).
    - ``techno``   : technologie explorée.
    - ``solution`` : solution/produit identifié.
    - ``resource`` : ressource (article, documentation, etc.).
    """

    THEME = "theme"
    TECHNO = "techno"
    SOLUTION = "solution"
    RESOURCE = "resource"


class ProjectRole(enum.StrEnum):
    """Rôle d'un utilisateur **au sein d'un projet** (EPIC-04).

    Volontairement distinct de :class:`UserRole` (rôle *global*) même si les
    valeurs coïncident : un utilisateur ``member`` global peut être ``admin``
    d'un projet donné et ``viewer`` d'un autre. Séparer les deux énumérations
    évite de coupler les autorisations globales et par projet.

    - ``admin``  : gère le projet (édition, membres, archivage).
    - ``member`` : contribue (créera/éditera des tickets en EPIC-05).
    - ``viewer`` : lecture seule.
    """

    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
