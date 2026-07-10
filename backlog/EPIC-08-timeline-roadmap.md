# EPIC-08 — Timeline / Roadmap

**Objectif** : vue timeline (type Gantt) des Epics et de leurs tickets dans le temps, avec barres temporelles déplaçables/redimensionnables, échelles (semaines/mois/trimestres) et dépendances simples.

**Dépendances** : EPIC-05 (tickets, dates, hiérarchie Epic).

---

## JIR-56 · Story · API données de timeline
**SP : 3**
Endpoint renvoyant les Epics d'un projet avec dates début/fin, progression, et leurs enfants, pour l'affichage timeline.

**Critères d'acceptation**
- [ ] `GET /projects/{id}/timeline` renvoie epics + dates + progression.
- [ ] Inclut les enfants rattachés pour l'expansion.
- [ ] Gère les epics sans dates (affichage neutre).

---

## JIR-57 · Story · Rendu de la timeline (barres temporelles)
**SP : 8**
Composant timeline : lignes par Epic, barres positionnées selon dates début/fin, en-tête d'échelle temporelle, colonne de gauche listant les Epics.

**Critères d'acceptation**
- [ ] Barres positionnées correctement sur l'axe temps.
- [ ] Colonne latérale (nom Epic + progression).
- [ ] Scroll horizontal fluide sur de longues périodes.

---

## JIR-58 · Story · Échelles de temps (semaine/mois/trimestre)
**SP : 3**
Basculer l'échelle de l'axe (semaines, mois, trimestres) avec recalcul des positions.

**Critères d'acceptation**
- [ ] Sélecteur d'échelle.
- [ ] En-têtes de dates adaptés à l'échelle.
- [ ] Positions/largeurs recalculées correctement.

---

## JIR-59 · Story · Édition des dates par drag & resize
**SP : 8**
Déplacer une barre (décale début+fin) et redimensionner (change début ou fin) avec persistance des dates via l'API ticket.

**Critères d'acceptation**
- [ ] Drag d'une barre met à jour les dates de l'Epic.
- [ ] Resize des bords met à jour début/fin.
- [ ] Persistance API + mise à jour optimiste.
- [ ] Viewer en lecture seule.

---

## JIR-60 · Story · Expansion des enfants d'un Epic
**SP : 5**
Déplier un Epic pour afficher ses stories/tasks/bugs en sous-lignes, avec leurs propres barres.

**Critères d'acceptation**
- [ ] Chevron d'expansion par Epic.
- [ ] Sous-lignes des enfants avec barres.
- [ ] Progression de l'Epic reflétant les enfants Done.

---

## JIR-61 · Story · Dépendances entre tickets (simple)
**SP : 5**
Modéliser et afficher des dépendances « bloque / est bloqué par » entre tickets, visualisées par des liens sur la timeline.

**Critères d'acceptation**
- [ ] Modèle de dépendance (from/to, type) + API.
- [ ] Création/suppression d'une dépendance depuis le détail du ticket.
- [ ] Lignes de liaison affichées sur la timeline.
