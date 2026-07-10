"""Routeur agrégateur de l'API v1.

Toutes les routes métier (auth, projects, tickets, ...) sont montées ici,
puis incluses dans l'application sous le préfixe `/api/v1`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    activity,
    attachments,
    auth,
    comments,
    documents,
    issues,
    labels,
    notifications,
    projects,
    rag,
    reports,
    saved_views,
    search,
    sprints,
    stats,
    users,
    watch,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# Recherche globale (transverse, sans préfixe de ressource).
api_router.include_router(search.router, tags=["search"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
# Labels, issues et sprints rattachés à un projet (montés sous /projects).
api_router.include_router(labels.project_router, prefix="/projects", tags=["labels"])
api_router.include_router(issues.project_router, prefix="/projects", tags=["issues"])
api_router.include_router(sprints.project_router, prefix="/projects", tags=["sprints"])
api_router.include_router(stats.project_router, prefix="/projects", tags=["stats"])
api_router.include_router(saved_views.project_router, prefix="/projects", tags=["saved-views"])
api_router.include_router(documents.project_router, prefix="/projects", tags=["documents"])
# Commentaires, pièces jointes et activité rattachés à une issue (montés sous /issues).
api_router.include_router(comments.issue_router, prefix="/issues", tags=["comments"])
api_router.include_router(attachments.issue_router, prefix="/issues", tags=["attachments"])
api_router.include_router(activity.issue_router, prefix="/issues", tags=["activity"])
# Labels, issues et sprints adressés par identifiant/clé.
api_router.include_router(labels.router, prefix="/labels", tags=["labels"])
api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(sprints.router, prefix="/sprints", tags=["sprints"])
# Commentaires, pièces jointes, notifications et vues adressés par identifiant.
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(attachments.router, prefix="/attachments", tags=["attachments"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(saved_views.router, prefix="/views", tags=["saved-views"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# Chatbot RAG (EPIC-10) : statut, réindexation, conversation.
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
# Génération de rapports (stats + synthèse LLM), réservée à l'admin global.
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
# Veille R&D (domaine VEILLE) : arbre/graphe de connaissances, médias, commentaires.
api_router.include_router(watch.router, prefix="/watch", tags=["watch"])
