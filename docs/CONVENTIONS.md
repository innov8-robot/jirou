# Conventions techniques — contrat partagé front/back

> Ce document fige les décisions transverses pour que backend et frontend restent alignés.
> À respecter par tous les tickets et agents.

## Ports (dev)

Les conteneurs écoutent en interne sur les ports « standard » ; les ports **publiés côté hôte**
sont décalés pour éviter les conflits avec d'autres services locaux (configurables via `.env`).

| Service | Port conteneur | Port hôte (défaut) | URL (hôte) |
|---|---|---|---|
| Frontend (Vite) | 5173 | 5199 (`FRONTEND_PORT`) | http://localhost:5199 |
| Backend (FastAPI/Uvicorn) | 8000 | 8010 (`BACKEND_PORT`) | http://localhost:8010 |
| PostgreSQL | 5432 | 5433 (`POSTGRES_PORT`) | `localhost:5433` (interne : `db:5432`) |

## Variables d'environnement

Voir [../.env.example](../.env.example). Noms canoniques : `DATABASE_URL`, `JWT_SECRET_KEY`,
`JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS`,
`VITE_API_URL`.

## API

- **Base URL** : `http://localhost:8010` (port hôte ; `8000` dans le conteneur)
- **Préfixe** : toutes les routes métier sous `/api/v1`. Ex. `/api/v1/auth/login`, `/api/v1/projects`.
- **Format** : JSON. `camelCase` interdit côté payload — on reste en `snake_case` (Pydantic) ; le front adapte si besoin.
- **Docs** : Swagger auto sur `/docs`, OpenAPI JSON sur `/openapi.json`.
- **Santé** : `GET /health` → `{"status": "ok"}` (hors préfixe versionné).
- **Auth** : header `Authorization: Bearer <access_token>`.
- **Erreurs** : format FastAPI standard `{"detail": ...}`. Codes : 400 (validation), 401 (non authentifié), 403 (interdit), 404 (introuvable), 409 (conflit).

## Backend — stack imposée

- Python **3.12**, gestion via `pyproject.toml`.
- FastAPI, Uvicorn, SQLAlchemy **2.0** (style `Mapped`/`mapped_column`), Alembic, Pydantic **v2** + `pydantic-settings`.
- Driver Postgres : **psycopg** (v3) → URL `postgresql+psycopg://...`.
- Sécurité : `passlib[bcrypt]` (hash), `python-jose[cryptography]` (JWT).
- Lint/format : **ruff**. Tests : **pytest**.
- Layout : `app/{api,core,models,schemas,services}`, point d'entrée `app/main.py` (objet `app`).

## Frontend — stack imposée

- React **18** + TypeScript + **Vite**.
- **Tailwind CSS** + **shadcn/ui** (dossier `src/components/ui`).
- Données serveur : **TanStack Query** ; état UI : **Zustand**.
- Routing : **React Router**.
- HTTP : client centralisé lisant `import.meta.env.VITE_API_URL`, intercepteur d'auth (Bearer).
- Lint/format : **ESLint + Prettier**. Tests : **Vitest** + React Testing Library.
- Layout : `src/{components,features,lib,pages}`.

## Conventions métier (rappel)

- Clé ticket : `PREFIXE-NUMÉRO` (ex. `JIR-42`), compteur par projet.
- Types : `epic | story | task | bug`. Statuts : `todo | in_progress | in_review | done`.
- Priorités : `highest | high | medium | low | lowest`.
- Rôles : `admin | member | viewer`.
- Estimation : story points Fibonacci.
