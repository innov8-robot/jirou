# EPIC-04 — Projets

**Objectif** : gérer les projets (CRUD), leur préfixe de clé, leurs membres et les rôles associés. Le projet est le conteneur de tous les tickets, sprints et boards.

**Dépendances** : EPIC-02 (auth/rôles), EPIC-03 (layout).

---

## JIR-23 · Story · Modèle Project & membres
**SP : 3**
Modèles `Project` (nom, clé/préfixe unique, description, lead, date création, avatar/couleur) et `ProjectMember` (user, projet, rôle projet). Migrations.

**Critères d'acceptation**
- [ ] Tables `projects` et `project_members` créées.
- [ ] Préfixe de clé unique, 2-5 lettres majuscules.
- [ ] Un projet a un lead (user) et une liste de membres avec rôle.
- [ ] Compteur de tickets par projet (pour la numérotation des clés).

---

## JIR-24 · Story · API CRUD projets
**SP : 5**
Endpoints : créer, lister (ceux dont le user est membre), détail, éditer, archiver/supprimer un projet. Contrôle des permissions.

**Critères d'acceptation**
- [ ] `POST /projects` (admin/membre) crée un projet et ajoute le créateur comme lead.
- [ ] `GET /projects` ne renvoie que les projets accessibles au user.
- [ ] `PATCH /projects/{id}` réservé au lead/admin.
- [ ] Suppression = archivage logique (soft delete) par défaut.
- [ ] Validation d'unicité du préfixe.

---

## JIR-25 · Story · Gestion des membres d'un projet
**SP : 3**
Endpoints pour ajouter/retirer un membre et changer son rôle projet (Admin/Membre/Viewer au niveau projet).

**Critères d'acceptation**
- [ ] Ajout d'un membre par email/sélection.
- [ ] Modification du rôle projet réservée au lead/admin projet.
- [ ] Retrait d'un membre (sans supprimer ses tickets).

---

## JIR-26 · Story · Liste des projets (front)
**SP : 3**
Page `/projects` : grille/liste des projets accessibles avec nom, clé, avatar/couleur, lead, accès rapide.

**Critères d'acceptation**
- [ ] Affichage des projets du user avec recherche/filtre simple.
- [ ] Bouton « Créer un projet » (selon permission).
- [ ] Clic sur un projet → vue projet.

---

## JIR-27 · Story · Création / édition de projet (front)
**SP : 3**
Modale/page de création & édition : nom, préfixe (auto-suggéré depuis le nom), description, couleur/avatar, lead.

**Critères d'acceptation**
- [ ] Préfixe auto-généré depuis le nom, éditable, validé (unicité en direct).
- [ ] Édition réservée aux ayants droit.
- [ ] Feedback toast + mise à jour du cache.

---

## JIR-28 · Story · Vue projet & navigation interne
**SP : 3**
Layout d'un projet avec sous-navigation : Board, Backlog, Timeline, Tickets, Paramètres. Header projet (nom, clé, membres).

**Critères d'acceptation**
- [ ] Sous-navigation projet persistante.
- [ ] Onglets pointant vers les vues (board/backlog/timeline/liste).
- [ ] Avatars des membres affichés dans le header.

---

## JIR-29 · Story · Paramètres du projet
**SP : 3**
Écran paramètres : infos générales, membres & rôles, archivage/suppression.

**Critères d'acceptation**
- [ ] Onglet « Général » (nom, description, couleur).
- [ ] Onglet « Membres » (ajout/retrait/rôle) réutilisant JIR-25.
- [ ] Zone « Danger » (archiver/supprimer) réservée au lead/admin.
