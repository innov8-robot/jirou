# Jirou — Backend

API FastAPI du clone de Jira **Jirou**.

## Stack

- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy 2.0 (`Mapped` / `mapped_column`), driver `postgresql+psycopg` (psycopg v3)
- Alembic (migrations)
- Pydantic v2 + `pydantic-settings`
- Auth : `passlib[bcrypt]`, `python-jose[cryptography]`
- Lint/format : `ruff` · Tests : `pytest`

## Arborescence

```
backend/
├── app/
│   ├── main.py            # objet `app` FastAPI, CORS, /health, montage /api/v1
│   ├── api/v1/router.py   # routeur agrégateur des routes métier (vide pour l'instant)
│   ├── core/
│   │   ├── config.py      # Settings (pydantic-settings) lus depuis l'env / .env
│   │   └── database.py    # engine, SessionLocal, Base (DeclarativeBase), get_db()
│   ├── models/            # modèles ORM (à venir) — importés par Alembic
│   ├── schemas/           # schémas Pydantic (à venir)
│   └── services/          # logique métier (à venir)
├── alembic/               # migrations (env.py lit l'URL depuis la config)
├── alembic.ini
├── entrypoint.sh          # alembic upgrade head puis uvicorn
├── Dockerfile             # multi-stage python:3.12-slim
├── pyproject.toml
└── tests/                 # pytest (test_health sans DB)
```

## Démarrage en local (hors Docker)

Prérequis : Python 3.12 et un PostgreSQL accessible.

```bash
cd backend

# 1. Environnement virtuel + dépendances (dev incluses)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configuration : le backend lit un .env (à la racine du repo ou depuis backend/).
#    En local hors Docker, remplacer "db" par "localhost" dans DATABASE_URL.
cp ../.env.example ../.env   # puis ajuster DATABASE_URL

# 3. Migrations
alembic upgrade head

# 4. Lancer l'API (http://localhost:8000, docs sur /docs)
uvicorn app.main:app --reload --port 8000
```

Vérifications rapides :

```bash
curl http://localhost:8000/health       # -> {"status":"ok"}
curl http://localhost:8000/health/db     # -> {"status":"ok","database":"ok"} (nécessite la DB)
```

## Variables d'environnement

Voir `../.env.example` (contrat partagé). Utilisées par le backend :
`DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`REFRESH_TOKEN_EXPIRE_DAYS`, `CORS_ORIGINS` (chaîne CSV acceptée).

## Alembic — commandes usuelles

```bash
# Générer une migration automatiquement à partir des modèles (app/models)
alembic revision --autogenerate -m "message décrivant le changement"

# Créer une migration vide (à écrire à la main)
alembic revision -m "message"

# Appliquer toutes les migrations jusqu'à la plus récente
alembic upgrade head

# Revenir en arrière d'une révision
alembic downgrade -1

# État courant / historique
alembic current
alembic history --verbose
```

> `alembic/env.py` lit `settings.DATABASE_URL` (jamais d'URL en dur dans `alembic.ini`)
> et importe `app.models` pour que l'autogenerate détecte les nouveaux modèles.
> **Pense à importer chaque nouveau modèle dans `app/models/__init__.py`.**

## Seed d'un administrateur

Le script `scripts/create_admin.py` crée (ou promeut) un utilisateur
administrateur. Il est **idempotent** : si l'email existe déjà, l'utilisateur
est promu `admin` (et réactivé) sans modifier son mot de passe ; sinon il est
créé avec le rôle `admin`.

```bash
cd backend
# Valeurs par défaut : admin@jirou.app / admin_dev_password / "Jirou Admin"
python -m scripts.create_admin

# Ou en surchargeant via l'environnement
ADMIN_EMAIL=root@innov8.fr ADMIN_PASSWORD='S3cure!pwd' ADMIN_NAME='Root' \
  python -m scripts.create_admin
```

Variables lues : `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`. Le script utilise
`DATABASE_URL` (via `app.core.config.settings`) ; lancer les migrations avant
(`alembic upgrade head`).

## Seed de démonstration

Le script `scripts/seed_demo.py` peuple une base de démonstration **cohérente**
(EPIC-10, JIR-74) : quelques utilisateurs, un projet `DEMO` avec ses labels, un
backlog varié (epics + enfants, statuts/priorités/assignations divers, quelques
dates) et deux sprints — dont un **actif** peuplé. De quoi illustrer board,
backlog, sprint, timeline et tableaux de bord.

Il est **idempotent** : si le projet `DEMO` existe déjà, il ne recrée rien.

```bash
cd backend
alembic upgrade head          # les tables doivent exister au préalable
python -m scripts.seed_demo   # crée le projet DEMO peuplé (relançable sans doublon)
```

Comptes de démo créés (mot de passe commun `demo_password123`) :

| Email | Rôle projet |
|---|---|
| `demo.lead@jirou.app` | lead / admin |
| `demo.dev@jirou.app` | member |
| `demo.qa@jirou.app` | viewer |

Le script lit `DATABASE_URL` (via `app.core.config.settings`).

## Import CSV de tickets

`POST /api/v1/projects/{project_id}/issues/import` crée des tickets en lot à
partir d'un fichier CSV (multipart `file`, réservé aux membres non-viewer).

En-tête **obligatoire** (séparateur virgule, UTF-8, noms de colonnes
insensibles à la casse) :

```
type,summary,description,priority,story_points,status,labels,assignee_email,epic_key
```

| Colonne | Requis | Valeurs / format | Défaut |
|---|---|---|---|
| `type` | non | `epic` \| `story` \| `task` \| `bug` | `task` |
| `summary` | **oui** | texte | — |
| `description` | non | texte / HTML libre | vide |
| `priority` | non | `highest` \| `high` \| `medium` \| `low` \| `lowest` | `medium` |
| `story_points` | non | entier (vide → null ; non entier → avertissement + null) | null |
| `status` | non | `todo` \| `in_progress` \| `in_review` \| `done` | `todo` |
| `labels` | non | plusieurs séparés par `;` (créés au besoin, réutilisés sinon) | aucun |
| `assignee_email` | non | email d'un **membre** du projet (sinon avertissement, ticket sans assigné) | aucun |
| `epic_key` | non | clé d'une epic existante **ou** `summary` d'une epic définie plus haut dans le CSV | aucun |

Règles :

- **Robuste** : chaque ligne est validée seule. Une ligne invalide (`summary`
  vide, `type`/`status`/`priority` inconnu) est ignorée et listée dans `errors`
  (avec son numéro de ligne, 1 = première ligne de données) ; les autres lignes
  sont créées. Les avertissements non bloquants figurent aussi dans `errors`.
- **Rattachement à une epic** (lignes non-epic), dans l'ordre : (1) `epic_key`
  = clé d'une epic existante ; (2) sinon `epic_key` = `summary` d'une ligne
  `type=epic` plus haut dans le même CSV ; (3) sinon le champ de formulaire
  optionnel `epic_id` (epic cible choisie dans l'UI). Une ligne `epic` ignore
  tout rattachement. `epic_key` introuvable → avertissement, ticket sans parent.
- Limite : **1000** lignes de données (au-delà → 400). En-tête manquant ou
  fichier illisible/vide → 400 ; `epic_id` du formulaire pointant autre chose
  qu'une epic du projet → 422.

Exemple — une epic suivie de ses deux enfants, importables en un seul CSV :

```
type,summary,description,priority,story_points,status,labels,assignee_email,epic_key
epic,Authentification,Gestion des comptes,high,,todo,,,
story,Page de connexion,Formulaire email + mot de passe,high,5,in_progress,frontend;auth,dev@example.com,Authentification
bug,Déconnexion cassée,Le bouton ne répond pas,medium,2,todo,auth,,Authentification
```

Réponse `200` (`ImportResult`) :

```json
{
  "created": 3,
  "error_count": 1,
  "errors": [
    { "row": 2, "message": "assignee_email « dev@example.com » n'est pas membre du projet : ticket créé sans assigné." }
  ],
  "issues": [
    { "id": 1, "key": "JIR-1", "type": "epic", "summary": "Authentification", "status": "todo", "epic_id": null, "...": "..." },
    { "id": 2, "key": "JIR-2", "type": "story", "summary": "Page de connexion", "status": "in_progress", "epic_id": 1, "...": "..." },
    { "id": 3, "key": "JIR-3", "type": "bug", "summary": "Déconnexion cassée", "status": "todo", "epic_id": 1, "...": "..." }
  ]
}
```

## Tests & lint

```bash
pytest            # test_health ne nécessite pas de base de données
ruff check .      # lint
ruff format .     # format
```

## Docker

Image multi-stage (`Dockerfile`). Le conteneur exécute `alembic upgrade head`
via `entrypoint.sh` avant de démarrer Uvicorn sur le port **8000**.

Dans le futur `docker-compose.yml` (hors périmètre de ce ticket), le service
est attendu sous le nom **`backend`**, exposé sur **8000**, et dépend du service
**`db`** (PostgreSQL). L'URL par défaut de `DATABASE_URL` pointe déjà vers l'hôte
`db` du réseau Docker.
