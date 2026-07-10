# EPIC-07 — Sprints, Backlog & Board Scrum

**Objectif** : gérer les sprints (création, planification, démarrage, clôture), le backlog produit, et un board Scrum piloté par le sprint actif. Inclut la vélocité de base.

**Dépendances** : EPIC-05 (tickets), EPIC-06 (board).

---

## JIR-47 · Story · Modèle Sprint
**SP : 3**
Modèle `Sprint` : projet, nom, objectif, statut (future/active/completed), dates début/fin, ordre. Lien issue↔sprint. Migrations.

**Critères d'acceptation**
- [ ] Table `sprints` + FK `sprint_id` sur `issues`.
- [ ] Un seul sprint `active` par projet à la fois.
- [ ] Statuts : future → active → completed.

---

## JIR-48 · Story · API gestion des sprints
**SP : 5**
Endpoints : créer, éditer, démarrer, clôturer un sprint ; assigner/retirer des tickets au sprint ; à la clôture, gérer les tickets non terminés (retour backlog ou sprint suivant).

**Critères d'acceptation**
- [ ] Créer un sprint (future) et le renommer/dater.
- [ ] Démarrer un sprint (→ active) avec dates.
- [ ] Clôturer un sprint (→ completed) : tickets non Done déplacés selon choix.
- [ ] Ajouter/retirer des tickets au sprint.

---

## JIR-49 · Story · Vue Backlog (front)
**SP : 8**
Écran backlog type Jira : liste du backlog produit + sections par sprint (planifiés/actif). Drag & drop des tickets entre backlog et sprints, réordonnancement.

**Critères d'acceptation**
- [ ] Section « Backlog » + une section par sprint.
- [ ] Drag & drop ticket entre backlog et sprints (dnd-kit).
- [ ] Création rapide de ticket en ligne dans une section.
- [ ] Somme des story points par sprint affichée.

---

## JIR-50 · Story · Panneau de planification de sprint
**SP : 3**
Depuis le backlog : créer un sprint, définir objectif et dates, démarrer le sprint.

**Critères d'acceptation**
- [ ] Bouton « Créer un sprint » dans le backlog.
- [ ] Modale de démarrage (nom, objectif, dates, durée).
- [ ] Confirmation de démarrage → board Scrum activé.

---

## JIR-51 · Story · Board Scrum (sprint actif)
**SP : 5**
Board Kanban filtré sur le **sprint actif**, avec objectif du sprint et jours restants en en-tête. Réutilise le moteur de board (EPIC-06).

**Critères d'acceptation**
- [ ] Le board affiche uniquement les tickets du sprint actif.
- [ ] En-tête : nom du sprint, objectif, date de fin / jours restants.
- [ ] Message si aucun sprint actif (inviter à en démarrer un).

---

## JIR-52 · Story · Clôture de sprint & récapitulatif
**SP : 5**
Écran de clôture : résumé (tickets terminés vs non terminés, points complétés), choix de destination des tickets restants.

**Critères d'acceptation**
- [ ] Récap terminés/non terminés + points.
- [ ] Choix : renvoyer les restants au backlog ou au prochain sprint.
- [ ] Sprint marqué completed et archivé.

---

## JIR-53 · Story · Vélocité & indicateurs de sprint
**SP : 5**
Graphe de vélocité (points engagés vs complétés par sprint clôturé) et éventuel burndown simple du sprint actif.

**Critères d'acceptation**
- [ ] Graphe de vélocité sur les N derniers sprints.
- [ ] (Optionnel) burndown du sprint actif.
- [ ] Données calculées côté API.

---

## JIR-54 · Task · API données de reporting
**SP : 3**
Endpoints agrégés pour la vélocité/burndown (points par jour, par sprint).

**Critères d'acceptation**
- [ ] `GET /projects/{id}/velocity` renvoie les séries par sprint.
- [ ] `GET /sprints/{id}/burndown` renvoie la série journalière.

---

## JIR-55 · Story · Basculer entre board Kanban et Scrum
**SP : 2**
Permettre au projet de choisir/afficher le mode board (Kanban continu vs Scrum par sprint).

**Critères d'acceptation**
- [ ] Sélecteur de mode board au niveau projet.
- [ ] Kanban = tous les tickets ; Scrum = sprint actif.
- [ ] Préférence mémorisée.
