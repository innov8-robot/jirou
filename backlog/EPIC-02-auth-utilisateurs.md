# EPIC-02 — Authentification & Utilisateurs

**Objectif** : permettre l'inscription/connexion sécurisée par JWT, gérer les utilisateurs et les rôles Admin / Membre / Viewer, et protéger les endpoints.

**Dépendances** : EPIC-01 (DB, skeletons).

---

## JIR-9 · Story · Modèle User & rôles
**SP : 3**
Modèle SQLAlchemy `User` (email unique, hash mot de passe, nom, avatar, rôle global, date création, actif) + enum de rôles `admin | member | viewer`. Migration Alembic.

**Critères d'acceptation**
- [ ] Table `users` créée via migration.
- [ ] Mot de passe stocké **hashé** (bcrypt via passlib), jamais en clair.
- [ ] Rôle par défaut `member`.
- [ ] Contrainte d'unicité sur l'email.

---

## JIR-10 · Story · Inscription (register)
**SP : 3**
Endpoint `POST /auth/register` (email, password, nom). Validation Pydantic (format email, robustesse mot de passe). Retour utilisateur créé (sans hash).

**Critères d'acceptation**
- [ ] Création d'un user avec mot de passe hashé.
- [ ] Erreur 409 si email déjà utilisé.
- [ ] Validation de la complexité du mot de passe (min 8 caractères).

---

## JIR-11 · Story · Connexion & JWT (access + refresh)
**SP : 5**
`POST /auth/login` renvoie access token (courte durée) + refresh token. `POST /auth/refresh` régénère un access token. Sécurité JWT via python-jose.

**Critères d'acceptation**
- [ ] Login valide → tokens signés, expiration configurable.
- [ ] Identifiants invalides → 401.
- [ ] `/auth/refresh` renvoie un nouvel access token à partir d'un refresh valide.
- [ ] `GET /auth/me` renvoie l'utilisateur courant à partir du token.

---

## JIR-12 · Story · Dépendances de sécurité & guard de rôles
**SP : 3**
Dépendance `get_current_user` (décode le JWT) et `require_role(...)` pour restreindre l'accès selon le rôle. Gestion des erreurs 401/403.

**Critères d'acceptation**
- [ ] Endpoint protégé refuse un token absent/invalide (401).
- [ ] `require_role("admin")` bloque un membre/viewer (403).
- [ ] Décorateur/dépendance réutilisable sur n'importe quelle route.

---

## JIR-13 · Story · Écrans Login & Register (front)
**SP : 5**
Pages `/login` et `/register` (shadcn Form + validation), stockage sécurisé des tokens, refresh automatique, redirection.

**Critères d'acceptation**
- [ ] Formulaires validés côté client (messages d'erreur clairs).
- [ ] Token stocké et attaché aux requêtes API (intercepteur).
- [ ] Refresh automatique du token expiré, sinon redirection vers `/login`.
- [ ] Redirection vers `/projects` après connexion.

---

## JIR-14 · Story · Routes protégées & contexte auth (front)
**SP : 3**
Garde de route (`<ProtectedRoute>`), store d'authentification (Zustand), hook `useAuth`, gestion du logout.

**Critères d'acceptation**
- [ ] Accès à une page protégée sans session → redirige vers `/login`.
- [ ] État utilisateur disponible globalement (nom, rôle, avatar).
- [ ] Logout efface les tokens et redirige.

---

## JIR-15 · Story · Profil utilisateur & gestion des membres (admin)
**SP : 3**
Page profil (éditer nom/avatar/mot de passe). Écran admin listant les utilisateurs, permettant de changer un rôle ou de désactiver un compte.

**Critères d'acceptation**
- [ ] Un user peut mettre à jour son profil et son mot de passe.
- [ ] Un admin voit la liste des users et peut modifier leur rôle.
- [ ] Un non-admin n'a pas accès à l'écran de gestion.
