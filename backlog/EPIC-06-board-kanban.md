# EPIC-06 — Board Kanban

**Objectif** : board visuel à colonnes (To Do / In Progress / In Review / Done) avec cartes de tickets, drag & drop pour changer de statut et réordonner, et filtres rapides.

**Dépendances** : EPIC-05 (tickets).

---

## JIR-40 · Story · API board & positions
**SP : 5**
Endpoint renvoyant les tickets groupés par statut pour un projet (ou un sprint actif), avec ordre. Endpoint de mise à jour de position/statut lors du drag & drop.

**Critères d'acceptation**
- [ ] `GET /projects/{id}/board` renvoie les colonnes + tickets ordonnés.
- [ ] `PATCH` de position gère statut + rang dans la colonne.
- [ ] Réordonnancement persistant et stable (stratégie de rang/position).

---

## JIR-41 · Story · Carte de ticket (Board card)
**SP : 3**
Composant carte : clé, résumé, type, priorité, assigné (avatar), story points, labels.

**Critères d'acceptation**
- [ ] Carte conforme au style Jira (compacte, lisible).
- [ ] Clic → ouvre le détail du ticket.
- [ ] Affiche tous les métadonnées clés listées.

---

## JIR-42 · Story · Colonnes & rendu du board
**SP : 5**
Board à colonnes fixes (To Do / In Progress / In Review / Done), compteur par colonne, scroll, en-têtes stylés.

**Critères d'acceptation**
- [ ] 4 colonnes de statut avec compteur de cartes.
- [ ] Colonnes scrollables indépendamment.
- [ ] Empty state par colonne.

---

## JIR-43 · Story · Drag & drop des cartes (dnd-kit)
**SP : 8**
Déplacer une carte entre colonnes (change le statut) et à l'intérieur d'une colonne (change l'ordre), avec mise à jour optimiste et persistance.

**Critères d'acceptation**
- [ ] Drag entre colonnes met à jour le statut via API.
- [ ] Drag dans une colonne met à jour l'ordre.
- [ ] Mise à jour optimiste + rollback si l'API échoue.
- [ ] Accessible (clavier) autant que possible.
- [ ] Viewer ne peut pas déplacer les cartes.

---

## JIR-44 · Story · Filtres rapides du board
**SP : 3**
Barre de filtres : par assigné (avatars cliquables), type, label, texte. Filtrage instantané côté client.

**Critères d'acceptation**
- [ ] Filtre par assigné via avatars.
- [ ] Filtres type/label/texte cumulables.
- [ ] Bouton « réinitialiser les filtres ».

---

## JIR-45 · Story · Regroupement par Epic (swimlanes)
**SP : 5**
Option d'affichage du board en swimlanes horizontales groupées par Epic (ou par assigné).

**Critères d'acceptation**
- [ ] Bascule « swimlanes par Epic / assigné / aucune ».
- [ ] Chaque swimlane affiche ses colonnes et cartes.
- [ ] Drag & drop fonctionne au sein des swimlanes.

---

## JIR-46 · Task · Persistance des préférences de board
**SP : 2**
Mémoriser (par user/projet) les filtres et le mode de regroupement choisis.

**Critères d'acceptation**
- [ ] Préférences restaurées au retour sur le board.
- [ ] Stockage local (ou API) documenté.
