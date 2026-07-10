# EPIC-09 — Commentaires & Pièces jointes

**Objectif** : permettre la collaboration sur un ticket via un fil de commentaires (avec mentions) et l'upload/gestion de pièces jointes.

**Dépendances** : EPIC-05 (tickets), EPIC-02 (users).

---

## JIR-62 · Story · Modèle & API commentaires
**SP : 3**
Modèle `Comment` (ticket, auteur, contenu rich text, dates). Endpoints CRUD + liste chronologique.

**Critères d'acceptation**
- [ ] Table `comments` liée à l'issue et à l'auteur.
- [ ] `POST/GET/PATCH/DELETE` commentaires.
- [ ] Édition/suppression réservées à l'auteur (ou admin).

---

## JIR-63 · Story · Fil de commentaires (front)
**SP : 5**
Section commentaires dans le détail du ticket : liste chronologique, éditeur rich text, édition/suppression inline.

**Critères d'acceptation**
- [ ] Ajout d'un commentaire avec éditeur rich text.
- [ ] Liste avec avatar, auteur, date relative.
- [ ] Édition/suppression de ses propres commentaires.

---

## JIR-64 · Story · Mentions @utilisateur
**SP : 5**
Autocomplétion `@` dans les commentaires pour mentionner un membre du projet, avec lien vers le user.

**Critères d'acceptation**
- [ ] Menu d'autocomplétion sur `@`.
- [ ] Mentions stockées et rendues comme liens.
- [ ] Restreint aux membres du projet.

---

## JIR-65 · Story · Modèle & API pièces jointes
**SP : 5**
Modèle `Attachment` (ticket, fichier, nom, taille, type, auteur). Upload (stockage local/volume ou S3-compatible), téléchargement, suppression. Limites de taille/type.

**Critères d'acceptation**
- [ ] `POST /issues/{key}/attachments` (multipart) stocke le fichier.
- [ ] Métadonnées persistées, URL de téléchargement sécurisée.
- [ ] Limite de taille + validation de type.
- [ ] Suppression réservée à l'auteur/ayants droit.

---

## JIR-66 · Story · Zone pièces jointes (front)
**SP : 3**
UI d'upload (drag & drop + bouton), aperçu (miniatures images), liste avec taille/type, téléchargement, suppression.

**Critères d'acceptation**
- [ ] Upload par drag & drop et sélection de fichier.
- [ ] Miniatures pour les images, icône générique sinon.
- [ ] Progression d'upload + gestion d'erreur.

---

## JIR-67 · Task · Notifications de mention (in-app)
**SP : 3**
Notifier (in-app) un utilisateur mentionné ou assigné : cloche dans la topbar + liste des notifications.

**Critères d'acceptation**
- [ ] Notification créée à la mention/assignation.
- [ ] Badge de compteur + liste déroulante.
- [ ] Marquer comme lu.
