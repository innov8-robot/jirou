# EPIC-05 — Tickets / Issues

**Objectif** : cœur du produit. CRUD des tickets avec types (Epic/Story/Task/Bug), tous les champs (priorité, story points, assigné, reporter, labels, dates), génération de clé, hiérarchie Epic→enfants, et vue détail.

**Dépendances** : EPIC-04 (projets).

---

## JIR-30 · Story · Modèle Issue & énumérations
**SP : 5**
Modèle `Issue` : projet, clé (`PREFIXE-N`), type (epic/story/task/bug), résumé, description (rich text/markdown), statut (todo/in_progress/in_review/done), priorité, story_points, assignee, reporter, epic_parent, dates (created, updated, due, start), position (ordre). Migrations.

**Critères d'acceptation**
- [ ] Table `issues` avec toutes les colonnes ci-dessus.
- [ ] Enums pour type, statut, priorité.
- [ ] Clé générée automatiquement à partir du préfixe projet + compteur.
- [ ] `epic_parent` (self-FK) pour rattacher story/task/bug à un Epic.

---

## JIR-31 · Story · Modèle Label & association
**SP : 2**
Modèle `Label` (nom, couleur, projet) + table d'association issue↔label (N-N).

**Critères d'acceptation**
- [ ] Labels propres à un projet.
- [ ] Un ticket peut avoir plusieurs labels.
- [ ] CRUD labels au niveau projet.

---

## JIR-32 · Story · API création de ticket
**SP : 5**
`POST /projects/{id}/issues` : validation, génération de clé, valeurs par défaut (statut To Do, reporter = user courant).

**Critères d'acceptation**
- [ ] Clé auto-incrémentée et unique par projet (transactionnelle, sans collision).
- [ ] Reporter = utilisateur courant par défaut.
- [ ] Type/statut/priorité validés.
- [ ] Permissions : viewer interdit de créer.

---

## JIR-33 · Story · API lecture & liste de tickets
**SP : 5**
`GET /issues/{key}` (détail) et `GET /projects/{id}/issues` avec filtres (statut, type, assigné, label, sprint, epic, texte) + tri + pagination.

**Critères d'acceptation**
- [ ] Détail par clé retourne le ticket enrichi (assignee, reporter, labels, epic).
- [ ] Liste filtrable/triable/paginée.
- [ ] Requêtes optimisées (pas de N+1).

---

## JIR-34 · Story · API mise à jour & suppression de ticket
**SP : 3**
`PATCH /issues/{key}` (mise à jour partielle de n'importe quel champ, y compris statut, assignee, points, epic, dates) et `DELETE /issues/{key}`.

**Critères d'acceptation**
- [ ] Mise à jour partielle champ par champ.
- [ ] Changement de statut respectant le workflow.
- [ ] Suppression réservée aux ayants droit (reporter/lead/admin).
- [ ] `updated_at` mis à jour automatiquement.

---

## JIR-35 · Story · Hiérarchie Epic ↔ enfants
**SP : 3**
Gérer le rattachement des stories/tasks/bugs à un Epic et l'agrégation (progression de l'Epic = enfants Done / total).

**Critères d'acceptation**
- [ ] Rattacher/détacher un enfant à un Epic.
- [ ] Un Epic expose la liste de ses enfants et une barre de progression.
- [ ] Un Epic ne peut pas être enfant d'un autre Epic.

---

## JIR-36 · Story · Liste des tickets (front)
**SP : 5**
Vue liste type Jira (tableau dense) : clé, type, résumé, statut, priorité, assigné, points, labels. Filtres et tri interactifs.

**Critères d'acceptation**
- [ ] Tableau triable par colonne.
- [ ] Barre de filtres (type, statut, assigné, label, texte).
- [ ] Clic sur une ligne → panneau/detail du ticket.

---

## JIR-37 · Story · Vue détail du ticket (front)
**SP : 8**
Panneau/page de détail complet : résumé éditable inline, description rich text, changement de statut, assigné, priorité, points, dates, labels, epic parent, sidebar de métadonnées. Édition inline avec sauvegarde optimiste.

**Critères d'acceptation**
- [ ] Tous les champs éditables inline avec persistance API.
- [ ] Description en éditeur rich text / markdown.
- [ ] Sidebar métadonnées (reporter, assigné, dates, labels, epic).
- [ ] Mise à jour optimiste + rollback en cas d'erreur.
- [ ] Emplacements pour commentaires (EPIC-09) et activité (EPIC-10).

---

## JIR-38 · Story · Éditeur de description rich text
**SP : 5**
Intégrer un éditeur (ex. Tiptap) : gras/italique, listes, titres, liens, code, checklists. Sérialisation stockable.

**Critères d'acceptation**
- [ ] Barre d'outils de formatage.
- [ ] Rendu en lecture cohérent avec l'édition.
- [ ] Contenu stocké et rechargé fidèlement.

---

## JIR-39 · Story · Gestion des labels (front)
**SP : 3**
UI de création/sélection de labels colorés sur un ticket et écran de gestion des labels du projet.

**Critères d'acceptation**
- [ ] Ajout/retrait de labels sur un ticket (multi-select coloré).
- [ ] Création de label à la volée.
- [ ] Gestion (renommer/couleur/supprimer) dans les paramètres projet.
