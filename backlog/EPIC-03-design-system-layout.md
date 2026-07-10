# EPIC-03 — Design System & Layout

**Objectif** : poser l'identité visuelle Jirou (theming shadcn/Tailwind), le layout applicatif (sidebar, topbar), et les composants transverses réutilisables, pour une UX cohérente type Jira.

**Dépendances** : EPIC-01 (Tailwind + shadcn).

---

## JIR-16 · Task · Thème & tokens de design
**SP : 3**
Configurer les variables de thème shadcn (couleurs, radius, typographie) selon la palette Jirou. Mode clair (et base pour dark mode).

**Critères d'acceptation**
- [ ] Palette de la section 4 du README appliquée via variables CSS/Tailwind.
- [ ] Couleur primaire, surfaces, texte cohérentes dans tous les composants shadcn.
- [ ] Police et échelle typographique définies.

---

## JIR-17 · Task · Layout applicatif (sidebar + topbar)
**SP : 5**
Shell de l'app : sidebar sombre gauche (navigation projets, board, backlog, timeline), topbar (recherche, création rapide, avatar/menu utilisateur), zone de contenu.

**Critères d'acceptation**
- [ ] Sidebar avec sections et items actifs surlignés.
- [ ] Topbar avec logo Jirou, barre de recherche, bouton « Créer », menu utilisateur.
- [ ] Layout responsive (sidebar rétractable).

---

## JIR-18 · Task · Composants transverses (badges, avatars, icônes)
**SP : 3**
Composants réutilisables : badge de type de ticket (couleur+icône), badge de statut, icône de priorité, avatar utilisateur (initiales/photo), pastille de story points.

**Critères d'acceptation**
- [ ] `IssueTypeBadge`, `StatusBadge`, `PriorityIcon`, `UserAvatar`, `StoryPoints` implémentés.
- [ ] Couleurs conformes aux conventions (types/statuts/priorités).
- [ ] Documentés dans une page « styleguide » interne.

---

## JIR-19 · Task · Système de notifications (toasts)
**SP : 2**
Intégrer un système de toasts (shadcn `sonner`/toast) pour les retours d'action (succès/erreur) globaux.

**Critères d'acceptation**
- [ ] Toast de succès/erreur déclenchable depuis n'importe où.
- [ ] Erreurs API génériques affichées automatiquement.

---

## JIR-20 · Task · États de chargement, vides et erreurs
**SP : 3**
Composants standard : skeletons de chargement, écrans « aucun résultat / liste vide », écran d'erreur avec retry.

**Critères d'acceptation**
- [ ] Skeletons pour listes et board.
- [ ] Empty states illustrés avec call-to-action.
- [ ] Error boundary + composant d'erreur réutilisable.

---

## JIR-21 · Task · Modale de création rapide (Create issue)
**SP : 3**
Modale globale « Créer » accessible depuis la topbar : choix du projet, type, résumé, champs principaux. Réutilisée partout.

**Critères d'acceptation**
- [ ] Ouvrable depuis la topbar et via raccourci clavier (`c`).
- [ ] Sélection projet + type + résumé minimum requis.
- [ ] Création via API et feedback toast + invalidation du cache.

*(Note : l'API sous-jacente vient d'EPIC-05.)*

---

## JIR-22 · Task · Configuration TanStack Query + Zustand
**SP : 2**
Mettre en place le `QueryClient` (cache, retry, invalidation), les conventions de query keys, et les stores Zustand pour l'état UI (filtres, modales).

**Critères d'acceptation**
- [ ] `QueryClientProvider` global avec config par défaut cohérente.
- [ ] Convention de query keys documentée.
- [ ] Store UI Zustand en place (ex. état de la modale de création).
