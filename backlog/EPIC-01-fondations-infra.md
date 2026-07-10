# EPIC-01 — Fondations & Infrastructure

**Objectif** : mettre en place le monorepo, l'environnement conteneurisé, la base de données, les squelettes front/back et la CI, afin que toute l'équipe puisse développer sur une base commune.

**Dépendances** : aucune (premier Epic).

---

## JIR-1 · Task · Initialiser la structure du monorepo
**SP : 1**
Créer l'arborescence `backend/`, `frontend/`, `backlog/`, fichiers racine (`README.md`, `.gitignore`, `.editorconfig`, `.env.example`).

**Critères d'acceptation**
- [ ] Arborescence conforme à la section 3 du README backlog.
- [ ] `.gitignore` couvre Python, Node, Docker, IDE, `.env`.
- [ ] `.env.example` documente toutes les variables (DB, JWT secret, ports).

---

## JIR-2 · Task · Squelette backend FastAPI
**SP : 3**
Initialiser le projet FastAPI avec structure `app/api|core|models|schemas|services`, `main.py`, gestion de config via Pydantic Settings, endpoint `/health`.

**Critères d'acceptation**
- [ ] `pyproject.toml` (ou requirements) avec FastAPI, Uvicorn, SQLAlchemy, Alembic, psycopg, Pydantic, python-jose, passlib.
- [ ] `GET /health` renvoie `{"status": "ok"}`.
- [ ] Config lue depuis variables d'environnement.
- [ ] CORS configuré pour le front.

---

## JIR-3 · Task · Squelette frontend React + Vite + TS
**SP : 3**
Initialiser Vite + React + TypeScript, ESLint + Prettier, structure `src/{components,features,lib,pages}`, routeur (React Router), client API (axios/fetch) avec base URL configurable.

**Critères d'acceptation**
- [ ] `npm run dev` démarre l'app sur une page d'accueil.
- [ ] ESLint + Prettier configurés et passants.
- [ ] React Router avec routes placeholder (`/login`, `/projects`).
- [ ] Client HTTP centralisé lisant `VITE_API_URL`.

---

## JIR-4 · Task · Intégrer Tailwind CSS + shadcn/ui
**SP : 2**
Installer et configurer Tailwind, initialiser shadcn/ui, importer quelques composants de base (Button, Input, Dialog) pour valider le pipeline.

**Critères d'acceptation**
- [ ] Tailwind opérationnel (classes utilitaires appliquées).
- [ ] shadcn initialisé (`components.json`, dossier `components/ui`).
- [ ] Button/Input/Dialog shadcn rendus sur une page de démo.

---

## JIR-5 · Task · PostgreSQL + connexion SQLAlchemy
**SP : 3**
Configurer la connexion async/sync SQLAlchemy 2.0 à PostgreSQL, session factory, dépendance `get_db`.

**Critères d'acceptation**
- [ ] Engine + session configurés depuis l'URL DB.
- [ ] Dépendance `get_db` injectable dans les routes.
- [ ] `/health` vérifie optionnellement la connexion DB.

---

## JIR-6 · Task · Migrations Alembic
**SP : 2**
Initialiser Alembic, configurer `env.py` pour lire les modèles et l'URL DB depuis la config, script de première migration vide.

**Critères d'acceptation**
- [ ] `alembic upgrade head` s'exécute sans erreur.
- [ ] `alembic revision --autogenerate` détecte les modèles.
- [ ] Documentation des commandes dans le README backend.

---

## JIR-7 · Task · Docker & docker-compose
**SP : 5**
Dockerfiles multi-stage pour back et front, `docker-compose.yml` orchestrant `db` (Postgres), `backend`, `frontend`, avec volumes, réseau, healthchecks et hot-reload en dev.

**Critères d'acceptation**
- [ ] `docker compose up` démarre les 3 services + la DB.
- [ ] Front accessible (ex. `:5173`), back (ex. `:8000`), DB persistée via volume.
- [ ] Migrations Alembic jouées au démarrage du backend.
- [ ] Variables via `.env`, aucun secret en dur.

---

## JIR-8 · Task · Pipeline CI GitHub Actions
**SP : 3**
Workflow CI : lint + tests + build pour front et back, sur push et pull request.

**Critères d'acceptation**
- [ ] Job backend : lint (ruff), pytest, base Postgres de service.
- [ ] Job frontend : lint, `vitest run`, `vite build`.
- [ ] La CI échoue si un lint/test/build échoue.
- [ ] Badge de statut dans le README racine.
