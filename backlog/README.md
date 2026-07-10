# Jirou — Backlog produit

> **Jirou** : un clone de Jira pour la gestion de projet agile. Projets, tickets, sprints, backlog, boards Kanban & Scrum, timeline/roadmap.
> Ce dossier est la **source de vérité** du travail à réaliser. Un fichier Markdown par Epic, chaque Epic listant ses tickets.

---

## 1. Vision

Reproduire l'expérience Jira (structure, UX, workflow agile) avec une identité visuelle propre.
Application multi-utilisateurs, multi-projets, orientée équipes agiles (Scrum + Kanban).

## 2. Stack technique

| Couche | Choix |
|---|---|
| **Frontend** | React 18 + TypeScript + Vite |
| **Styling** | Tailwind CSS + shadcn/ui |
| **Data / état** | TanStack Query (server state) + Zustand (UI state) |
| **Drag & drop** | dnd-kit |
| **Backend** | FastAPI (Python 3.12) |
| **ORM / migrations** | SQLAlchemy 2.0 + Alembic |
| **Base de données** | PostgreSQL 16 |
| **Auth** | JWT (access + refresh), rôles Admin / Membre / Viewer |
| **Validation** | Pydantic v2 |
| **Conteneurisation** | Docker + docker-compose |
| **Tests** | Pytest (back), Vitest + React Testing Library (front) |
| **CI** | GitHub Actions (lint, tests, build) |

## 3. Structure du monorepo (cible)

```
jirou/
├── backlog/                 # ce dossier — tickets produit
├── backend/
│   ├── app/
│   │   ├── api/             # routes FastAPI (par ressource)
│   │   ├── core/            # config, sécurité, dépendances
│   │   ├── models/          # modèles SQLAlchemy
│   │   ├── schemas/         # schémas Pydantic
│   │   ├── services/        # logique métier
│   │   └── main.py
│   ├── alembic/             # migrations
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/      # composants UI (shadcn + métier)
│   │   ├── features/        # modules (projects, issues, board, sprints...)
│   │   ├── lib/             # api client, hooks, utils
│   │   ├── pages/ (routes)
│   │   └── main.tsx
│   └── package.json
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## 4. Identité visuelle (branding proposé)

- **Nom** : Jirou
- **Palette** (thème shadcn, ajustable) :
  - Primary : `#6D5AE6` (violet-indigo)
  - Primary hover : `#5B48D6`
  - Background app : `#FFFFFF` / sidebar `#1C1F3A` (violet sombre)
  - Surface / colonnes board : `#F4F5FB`
  - Texte : `#1A1A2E` / secondaire `#6B7280`
- **Couleurs par type de ticket** :
  - 🟣 Epic `#8B5CF6` · 🟢 Story `#22C55E` · 🔵 Task `#3B82F6` · 🔴 Bug `#EF4444`
- **Couleurs de statut** :
  - To Do `#8993A4` (gris) · In Progress `#3B82F6` (bleu) · In Review `#F59E0B` (ambre) · Done `#22C55E` (vert)
- **Priorités** (5 niveaux, icônes fléchées) : Highest, High, Medium, Low, Lowest.

## 5. Conventions métier

- **Clé de ticket** : `PREFIXE-NUMÉRO` (ex. `JIR-42`). Le préfixe (2-5 lettres) est défini à la création du projet, le numéro s'auto-incrémente **par projet**.
- **Types de tickets** : Epic, Story, Task, Bug.
- **Hiérarchie** : Epic → (Story | Task | Bug). Les Stories/Tasks/Bugs peuvent être rattachés à un Epic.
- **Statuts (workflow fixe)** : `To Do → In Progress → In Review → Done`.
- **Estimation** : story points en suite de Fibonacci (1, 2, 3, 5, 8, 13, 21).
- **Rôles** : `Admin` (gère projets, membres, tout éditer), `Membre` (crée/édite tickets, sprints), `Viewer` (lecture seule).

## 6. Échelle d'estimation des tickets de ce backlog

Les tickets ci-dessous sont estimés en **story points** (SP) sur la complexité de dev :

| SP | Sens |
|---|---|
| 1 | Trivial (config, petit composant) |
| 2 | Simple |
| 3 | Moyen |
| 5 | Conséquent (feature complète front+back) |
| 8 | Complexe (plusieurs sous-systèmes) |
| 13 | Très complexe (à découper si possible) |

## 7. Liste des Epics

| # | Epic | Objectif | Fichier |
|---|---|---|---|
| 01 | Fondations & Infrastructure | Monorepo, Docker, DB, CI, skeletons front/back | [EPIC-01](./EPIC-01-fondations-infra.md) |
| 02 | Authentification & Utilisateurs | JWT, register/login, rôles, profil | [EPIC-02](./EPIC-02-auth-utilisateurs.md) |
| 03 | Design System & Layout | Theming shadcn, branding, sidebar, navigation | [EPIC-03](./EPIC-03-design-system-layout.md) |
| 04 | Projets | CRUD projets, préfixe, membres, rôles projet | [EPIC-04](./EPIC-04-projets.md) |
| 05 | Tickets / Issues | CRUD tickets, types, champs, clé, détail | [EPIC-05](./EPIC-05-tickets-issues.md) |
| 06 | Board Kanban | Colonnes, drag & drop, filtres rapides | [EPIC-06](./EPIC-06-board-kanban.md) |
| 07 | Sprints, Backlog & Board Scrum | Sprints, backlog, planif, board Scrum | [EPIC-07](./EPIC-07-sprints-backlog-scrum.md) |
| 08 | Timeline / Roadmap | Vue timeline des epics, barres temporelles | [EPIC-08](./EPIC-08-timeline-roadmap.md) |
| 09 | Commentaires & Pièces jointes | Fil de commentaires, upload de fichiers | [EPIC-09](./EPIC-09-commentaires-pieces-jointes.md) |
| 10 | Recherche, Filtres & Activité | Recherche, filtres avancés, flux d'activité | [EPIC-10](./EPIC-10-recherche-filtres-activite.md) |

## 8. Ordre de réalisation conseillé

1. **EPIC-01** (fondations) → indispensable en premier.
2. **EPIC-02** (auth) + **EPIC-03** (design system) → en parallèle possible.
3. **EPIC-04** (projets) → dépend de auth.
4. **EPIC-05** (tickets) → cœur du produit, dépend de projets.
5. **EPIC-06** (Kanban) → dépend de tickets.
6. **EPIC-07** (sprints/scrum) → dépend de tickets + board.
7. **EPIC-08** (timeline), **EPIC-09** (commentaires/PJ), **EPIC-10** (recherche/activité) → finitions.
