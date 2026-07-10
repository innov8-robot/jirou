# EPIC-10 — Recherche, Filtres & Activité

**Objectif** : recherche globale des tickets, filtres avancés sauvegardables, journal d'activité par ticket/projet, et tableau de bord synthétique. Finitions transverses.

**Dépendances** : EPIC-05 (tickets) et la plupart des Epics précédents.

---

## JIR-68 · Story · Recherche globale
**SP : 5**
Recherche depuis la topbar : tickets par clé, résumé, description ; projets. Résultats groupés, navigation clavier.

**Critères d'acceptation**
- [ ] `GET /search?q=` renvoie tickets + projets pertinents.
- [ ] Recherche par clé exacte (`JIR-42`) et texte.
- [ ] UI de résultats avec navigation clavier + accès direct.

---

## JIR-69 · Story · Journal d'activité (audit)
**SP : 5**
Enregistrer les changements sur un ticket (statut, assigné, champs, commentaires) et les afficher dans un onglet « Activité » du détail.

**Critères d'acceptation**
- [ ] Modèle `ActivityLog` (ticket, user, action, ancienne/nouvelle valeur, date).
- [ ] Écriture automatique sur les mutations de ticket.
- [ ] Onglet « Activité » chronologique dans le détail.

---

## JIR-70 · Story · Filtres avancés & vues sauvegardées
**SP : 5**
Constructeur de filtres (type, statut, assigné, label, sprint, epic, priorité, dates) avec possibilité d'enregistrer une vue nommée.

**Critères d'acceptation**
- [ ] Combinaison de plusieurs critères.
- [ ] Sauvegarde/chargement d'une vue nommée (par user).
- [ ] Application de la vue à la liste des tickets.

---

## JIR-71 · Story · Tableau de bord projet
**SP : 5**
Dashboard projet : répartition par statut, par type, par assigné, tickets récents, avancement du sprint actif.

**Critères d'acceptation**
- [ ] Graphes de répartition (statut/type/assigné).
- [ ] Widget sprint actif (progression).
- [ ] Liste des tickets récemment mis à jour.

---

## JIR-72 · Story · Mes tickets / tableau de bord personnel
**SP : 3**
Vue « Mon travail » : tickets assignés à l'utilisateur, tous projets confondus, groupés par projet/statut.

**Critères d'acceptation**
- [ ] Liste des tickets assignés au user courant.
- [ ] Groupement par projet et/ou statut.
- [ ] Accès rapide depuis la sidebar.

---

## JIR-73 · Task · Raccourcis clavier
**SP : 3**
Raccourcis type Jira : `c` créer, `/` rechercher, navigation dans le board, etc.

**Critères d'acceptation**
- [ ] Au moins : créer (`c`), recherche (`/`), fermer modale (`Esc`).
- [ ] Aide des raccourcis (`?`).

---

## JIR-74 · Task · Documentation & seed de démo
**SP : 3**
README d'utilisation, script de seed (utilisateurs, projet démo, tickets, sprints) pour tester rapidement l'app.

**Critères d'acceptation**
- [ ] Script de seed peuplant une base de démo cohérente.
- [ ] README expliquant lancement (docker compose), comptes de démo.
- [ ] Données de démo couvrant board, backlog, sprint, timeline.
