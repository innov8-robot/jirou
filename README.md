# Jirou

Un clone de Jira pour la gestion de projet agile : projets, tickets (Epic/Story/Task/Bug), sprints, backlog, boards Kanban & Scrum, timeline/roadmap.

## Stack

- **Frontend** : React 18 + TypeScript + Vite + Tailwind + shadcn/ui + TanStack Query + Zustand
- **Backend** : FastAPI (Python 3.12) + SQLAlchemy 2.0 + Alembic + Pydantic v2
- **Base de données** : PostgreSQL 16
- **Auth** : JWT (access + refresh), rôles Admin / Membre / Viewer
- **Infra** : Docker + docker-compose, CI GitHub Actions

## Démarrage rapide

```bash
cp .env.example .env
docker compose up --build
```

- Frontend : http://localhost:5199
- Backend (API + docs Swagger) : http://localhost:8010/docs

> Les ports hôte (5199 / 8010 / 5433) sont décalés des ports internes pour éviter les conflits
> avec d'éventuels services locaux. Modifiables dans `.env` (`FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT`).

## Structure

```
jirou/
├── backlog/     # backlog produit (1 fichier .md par Epic)
├── backend/     # API FastAPI
├── frontend/    # SPA React
├── docs/        # conventions & documentation technique
├── docker-compose.yml
└── .env.example
```

## Documentation

- **Backlog produit** : [backlog/README.md](backlog/README.md)
- **Conventions techniques** (contrat partagé front/back) : [docs/CONVENTIONS.md](docs/CONVENTIONS.md)
