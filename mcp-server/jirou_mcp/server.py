"""Serveur MCP Jirou : expose les tickets, sprints, veille et docs à un agent.

Branché sur Claude Code (transport stdio), il permet de lire et d'écrire dans
Jirou pendant une session de code — créer le ticket d'un bug qu'on vient de
trouver, passer un ticket en « in_review » quand la PR part, consigner une
recherche technique dans la veille.

Deux partis pris qui structurent tout le fichier :

- **des identifiants lisibles, pas des entiers.** Les outils acceptent une clé
  de projet (``JIR``), une clé de ticket (``JIR-42``), un e-mail, un nom de
  sprint ; la traduction vers les identifiants numériques de l'API vit dans
  :mod:`jirou_mcp.client`. Un agent ne devrait jamais avoir à deviner un
  ``project_id``.
- **des réponses compactes.** Chaque outil ne renvoie que les champs utiles à
  une décision : les charges utiles de l'API sont bien plus larges, et tout ce
  qui remonte consomme du contexte.

Les docstrings des outils sont ce que le modèle lit pour choisir : elles disent
*quand* appeler l'outil, pas seulement ce qu'il fait.

La suppression n'est volontairement pas exposée : un agent peut créer, corriger
et commenter, mais pas effacer le travail de quelqu'un.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from jirou_mcp.client import JirouClient, JirouError
from jirou_mcp.context import current_client

_INSTRUCTIONS = """\
Jirou est le suivi de projet de l'équipe (tickets, sprints, veille R&D, docs).

Désigne les objets comme un humain : projet par sa clé (« JIR »), ticket par sa
clé (« JIR-42 »), personne par son e-mail, sprint par son nom. Les statuts sont
todo | in_progress | in_review | done ; les types epic | story | task | bug ; les
priorités highest | high | medium | low | lowest.

Avant de créer un ticket, cherche avec jirou_search_issues s'il n'existe pas
déjà. Tu agis avec les droits du propriétaire du jeton — n'écris que ce qui a été
demandé.\
"""

mcp = MCPServer(
    name="jirou",
    title="Jirou — suivi de projet",
    version="0.1.0",
    instructions=_INSTRUCTIONS,
)

# Client du mode stdio, construit à la première utilisation : un import du module
# ne doit pas échouer faute de configuration (le serveur doit pouvoir démarrer et
# répondre, quitte à ce que l'appel d'un outil signale la configuration absente).
_client: JirouClient | None = None


def client() -> JirouClient:
    """Retourne le client API à utiliser pour l'appel d'outil en cours.

    Deux provenances selon le transport :

    - **HTTP** — le middleware d'authentification a posé un client construit
      avec le jeton porté par la requête (cf. :mod:`jirou_mcp.http`) ;
    - **stdio** — pas de contexte de requête : le client vient de
      l'environnement (``JIROU_API_URL`` / ``JIROU_TOKEN``).
    """
    from_request = current_client()
    if from_request is not None:
        return from_request

    global _client
    if _client is None:
        _client = JirouClient.from_env()
    return _client


# --------------------------------------------------------------------------- #
# Sérialisation compacte
# --------------------------------------------------------------------------- #
def _drop_empty(payload: dict[str, Any]) -> dict[str, Any]:
    """Retire les clés à ``None`` ou vides — allège la réponse envoyée au modèle."""
    return {k: v for k, v in payload.items() if v not in (None, [], "", {})}


def _issue_brief(issue: dict[str, Any]) -> dict[str, Any]:
    """Ticket en forme courte (listes, résultats de recherche)."""
    assignee = issue.get("assignee")
    return _drop_empty(
        {
            "key": issue["key"],
            "type": issue["type"],
            "summary": issue["summary"],
            "status": issue["status"],
            "priority": issue["priority"],
            "story_points": issue.get("story_points"),
            "assignee": assignee["email"] if assignee else None,
            "labels": [label["name"] for label in issue.get("labels", [])],
        }
    )


def _issue_full(issue: dict[str, Any]) -> dict[str, Any]:
    """Ticket en forme longue (détail) : description, parenté, dépendances."""
    reporter = issue.get("reporter")
    progress = issue.get("progress")
    return _drop_empty(
        {
            **_issue_brief(issue),
            "description": issue.get("description"),
            "reporter": reporter["email"] if reporter else None,
            "start_date": issue.get("start_date"),
            "due_date": issue.get("due_date"),
            "epic_id": issue.get("epic_id"),
            "sprint_id": issue.get("sprint_id"),
            "children": [_issue_brief(child) for child in issue.get("children", [])],
            "progress": (
                f"{progress['done']}/{progress['total']} enfants terminés" if progress else None
            ),
            "dependencies": [
                f"{dep['direction']}: {dep['issue']['key']} ({dep['type']})"
                for dep in issue.get("dependencies", [])
            ],
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
        }
    )


def _sprint_brief(sprint: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "name": sprint["name"],
            "status": sprint["status"],
            "goal": sprint.get("goal"),
            "start_date": sprint.get("start_date"),
            "end_date": sprint.get("end_date"),
            "issue_count": sprint.get("issue_count"),
        }
    )


def _comment_brief(comment: dict[str, Any]) -> dict[str, Any]:
    author = comment.get("author")
    return _drop_empty(
        {
            "author": author["email"] if author else None,
            "body": comment["body"],
            "created_at": comment.get("created_at"),
        }
    )


def _watch_brief(node: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "id": node["id"],
            "parent_id": node.get("parent_id"),
            "title": node["title"],
            "type": node.get("type"),
            "status": node.get("status"),
            "media_count": node.get("media_count"),
            "comment_count": node.get("comment_count"),
        }
    )


def _document_brief(document: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "id": document["id"],
            "title": document["title"],
            "project_id": document.get("project_id"),
            "updated_at": document.get("updated_at"),
        }
    )


# --------------------------------------------------------------------------- #
# Projets & tickets
# --------------------------------------------------------------------------- #
@mcp.tool()
def jirou_list_projects() -> list[dict[str, Any]]:
    """Liste les projets Jirou accessibles, avec leur clé.

    Appelle cet outil en premier quand tu ne sais pas quelle clé de projet
    utiliser, ou quand l'utilisateur parle d'un projet par son nom.
    """
    return [
        _drop_empty(
            {
                "key": project["key"],
                "name": project["name"],
                "description": project.get("description"),
                "my_role": project.get("my_role"),
            }
        )
        for project in client().projects(refresh=True)
    ]


@mcp.tool()
def jirou_search_issues(
    project: str,
    status: str | None = None,
    type: str | None = None,
    assignee_email: str | None = None,
    sprint: str | None = None,
    epic: str | None = None,
    search: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Cherche des tickets d'un projet, avec filtres cumulables.

    Utilise cet outil avant de créer un ticket (pour éviter un doublon), pour
    répondre à « où en est X ? », ou pour retrouver la clé d'un ticket dont on
    ne connaît que le sujet.

    Args:
        project: Clé du projet (ex. « JIR »).
        status: todo | in_progress | in_review | done.
        type: epic | story | task | bug.
        assignee_email: E-mail de l'assigné (doit être membre du projet).
        sprint: Nom du sprint, ou « active » pour le sprint en cours.
        epic: Clé ou résumé de l'epic parent.
        search: Texte cherché dans la clé, le résumé et la description.
        limit: Nombre maximal de tickets renvoyés (1 à 200).
    """
    project_id = client().project_id(project)
    return [
        _issue_brief(issue)
        for issue in client().get(
            f"/projects/{project_id}/issues",
            status=status,
            type=type,
            search=search,
            limit=max(1, min(limit, 200)),
            assignee_id=(
                client().resolve_user_id(project_id, assignee_email) if assignee_email else None
            ),
            sprint_id=client().resolve_sprint_id(project_id, sprint) if sprint else None,
            epic_id=client().resolve_epic_id(project_id, epic) if epic else None,
        )
        or []
    ]


@mcp.tool()
def jirou_get_issue(key: str) -> dict[str, Any]:
    """Détail complet d'un ticket : description, parenté, dépendances, dates.

    Appelle cet outil dès que tu dois travailler *sur* un ticket — la description
    contient l'énoncé, que la recherche ne renvoie pas.

    Args:
        key: Clé du ticket (ex. « JIR-42 »).
    """
    return _issue_full(client().resolve_issue(key))


@mcp.tool()
def jirou_create_issue(
    project: str,
    summary: str,
    type: str = "task",
    description: str | None = None,
    priority: str | None = None,
    story_points: int | None = None,
    assignee_email: str | None = None,
    epic: str | None = None,
    labels: list[str] | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
) -> dict[str, Any]:
    """Crée un ticket et renvoie sa clé.

    Le ticket naît au statut ``todo`` — utilise jirou_update_issue pour le
    déplacer ensuite. Cherche d'abord avec jirou_search_issues qu'il n'existe pas
    déjà.

    Args:
        project: Clé du projet (ex. « JIR »).
        summary: Titre du ticket, court et actionnable.
        type: epic | story | task | bug (défaut : task).
        description: Énoncé détaillé (Markdown accepté).
        priority: highest | high | medium | low | lowest (défaut : medium).
        story_points: Estimation en points (échelle de Fibonacci).
        assignee_email: E-mail de l'assigné (doit être membre du projet).
        epic: Clé ou résumé de l'epic parent.
        labels: Noms de labels ; ceux qui n'existent pas sont créés.
        start_date: Date de début au format AAAA-MM-JJ.
        due_date: Date d'échéance au format AAAA-MM-JJ.
    """
    project_id = client().project_id(project)
    payload = {
        "type": type,
        "summary": summary,
        "description": description,
        "priority": priority,
        "story_points": story_points,
        "assignee_id": (
            client().resolve_user_id(project_id, assignee_email) if assignee_email else None
        ),
        "epic_id": client().resolve_epic_id(project_id, epic) if epic else None,
        "start_date": start_date,
        "due_date": due_date,
        "label_ids": client().resolve_label_ids(project_id, labels) if labels else None,
    }
    created = client().post(f"/projects/{project_id}/issues", payload)
    return _issue_brief(created)


@mcp.tool()
def jirou_update_issue(
    key: str,
    status: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    type: str | None = None,
    priority: str | None = None,
    story_points: int | None = None,
    assignee_email: str | None = None,
    epic: str | None = None,
    labels: list[str] | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
) -> dict[str, Any]:
    """Modifie un ticket : seuls les champs fournis changent.

    C'est l'outil pour faire avancer un ticket (``status``) au fil du travail :
    ``in_progress`` quand tu commences, ``in_review`` quand la PR part, ``done``
    quand c'est mergé. Pour déplacer un ticket entre backlog et sprint, utilise
    jirou_move_issue_to_sprint.

    Args:
        key: Clé du ticket (ex. « JIR-42 »).
        status: todo | in_progress | in_review | done.
        summary: Nouveau titre.
        description: Nouvel énoncé (remplace l'ancien).
        type: epic | story | task | bug.
        priority: highest | high | medium | low | lowest.
        story_points: Estimation en points.
        assignee_email: E-mail du nouvel assigné (membre du projet).
        epic: Clé ou résumé de la nouvelle epic parente.
        labels: Liste **complète** des labels voulus (remplace les actuels) ;
            ceux qui n'existent pas sont créés.
        start_date: Date de début au format AAAA-MM-JJ.
        due_date: Date d'échéance au format AAAA-MM-JJ.
    """
    issue = client().resolve_issue(key)
    project_id = int(issue["project_id"])
    payload = {
        "status": status,
        "summary": summary,
        "description": description,
        "type": type,
        "priority": priority,
        "story_points": story_points,
        "assignee_id": (
            client().resolve_user_id(project_id, assignee_email) if assignee_email else None
        ),
        "epic_id": client().resolve_epic_id(project_id, epic) if epic else None,
        "start_date": start_date,
        "due_date": due_date,
        "label_ids": client().resolve_label_ids(project_id, labels) if labels else None,
    }
    if not any(value is not None for value in payload.values()):
        raise JirouError("Rien à modifier : précisez au moins un champ.")
    return _issue_brief(client().patch(f"/issues/{issue['key']}", payload))


# --------------------------------------------------------------------------- #
# Commentaires
# --------------------------------------------------------------------------- #
@mcp.tool()
def jirou_list_comments(key: str) -> list[dict[str, Any]]:
    """Fil de commentaires d'un ticket, du plus ancien au plus récent.

    Appelle cet outil pour reprendre le contexte d'une discussion avant de
    répondre ou de reprendre un travail commencé par quelqu'un d'autre.

    Args:
        key: Clé du ticket (ex. « JIR-42 »).
    """
    issue = client().resolve_issue(key)
    return [
        _comment_brief(comment)
        for comment in client().get(f"/issues/{issue['key']}/comments") or []
    ]


@mcp.tool()
def jirou_add_comment(key: str, body: str) -> dict[str, Any]:
    """Ajoute un commentaire à un ticket.

    Utile pour consigner sur le ticket ce que tu viens de faire — approche
    retenue, commit ou PR, écueil rencontré — plutôt que de le laisser
    uniquement dans la conversation.

    Args:
        key: Clé du ticket (ex. « JIR-42 »).
        body: Contenu du commentaire (Markdown accepté).
    """
    issue = client().resolve_issue(key)
    return _comment_brief(client().post(f"/issues/{issue['key']}/comments", {"body": body}))


# --------------------------------------------------------------------------- #
# Sprints & backlog
# --------------------------------------------------------------------------- #
@mcp.tool()
def jirou_list_sprints(project: str) -> list[dict[str, Any]]:
    """Sprints d'un projet, avec leur statut (future | active | completed).

    Appelle cet outil pour savoir ce qui est en cours, ou avant de déplacer un
    ticket dans un sprint.

    Args:
        project: Clé du projet (ex. « JIR »).
    """
    project_id = client().project_id(project)
    return [
        _sprint_brief(sprint) for sprint in client().get(f"/projects/{project_id}/sprints") or []
    ]


@mcp.tool()
def jirou_get_backlog(project: str) -> dict[str, Any]:
    """Vue backlog d'un projet : tickets par sprint, plus le backlog produit.

    Chaque groupe porte la somme de ses points, ce qui suffit à raisonner sur le
    remplissage d'un sprint. Appelle cet outil pour répondre à « qu'est-ce qui
    est prévu ? » ou pour proposer un contenu de sprint.

    Args:
        project: Clé du projet (ex. « JIR »).
    """
    project_id = client().project_id(project)
    backlog = client().get(f"/projects/{project_id}/backlog") or {}
    product = backlog.get("backlog") or {}
    return {
        "sprints": [
            {
                **_sprint_brief(entry["sprint"]),
                "points": entry.get("points"),
                "issues": [_issue_brief(issue) for issue in entry.get("issues", [])],
            }
            for entry in backlog.get("sprints", [])
        ],
        "backlog": {
            "points": product.get("points"),
            "issues": [_issue_brief(issue) for issue in product.get("issues", [])],
        },
    }


@mcp.tool()
def jirou_move_issue_to_sprint(
    key: str, sprint: str | None = None, position: int = 0
) -> dict[str, Any]:
    """Déplace un ticket dans un sprint, ou le renvoie au backlog.

    Args:
        key: Clé du ticket (ex. « JIR-42 »).
        sprint: Nom du sprint, ou « active » pour le sprint en cours. Laisse vide
            pour renvoyer le ticket au backlog produit.
        position: Rang cible dans la liste d'arrivée (0 = en tête).
    """
    issue = client().resolve_issue(key)
    project_id = int(issue["project_id"])
    payload: dict[str, Any] = {
        "sprint_id": client().resolve_sprint_id(project_id, sprint) if sprint else None,
        "position": max(0, position),
    }
    # ``sprint_id: null`` est significatif ici (= backlog) : la clé doit partir.
    moved = client().request(
        "PATCH",
        f"/issues/{issue['key']}/backlog-move",
        json=payload,
        keep_none=("sprint_id",),
    )
    return _issue_brief(moved)


# --------------------------------------------------------------------------- #
# Veille R&D
# --------------------------------------------------------------------------- #
@mcp.tool()
def jirou_list_watch_nodes() -> list[dict[str, Any]]:
    """Arbre de veille R&D à plat : tous les nœuds avec leur parent.

    La veille est globale (hors projet). Appelle cet outil pour situer un sujet
    avant d'y ajouter quelque chose, ou pour retrouver ce que l'équipe a déjà
    exploré sur une techno.
    """
    return [_watch_brief(node) for node in client().get("/watch/nodes") or []]


@mcp.tool()
def jirou_get_watch_node(node_id: int) -> dict[str, Any]:
    """Détail d'un nœud de veille : sa note Markdown et ses médias.

    Args:
        node_id: Identifiant du nœud (donné par jirou_list_watch_nodes).
    """
    node = client().get(f"/watch/nodes/{node_id}")
    return _drop_empty(
        {
            **_watch_brief(node),
            "note": node.get("note"),
            "media": [
                _drop_empty(
                    {
                        "kind": m["kind"],
                        "title": m.get("title"),
                        "url": m.get("url"),
                        "filename": m.get("filename"),
                    }
                )
                for m in node.get("media", [])
            ],
        }
    )


@mcp.tool()
def jirou_create_watch_node(
    title: str,
    parent_id: int | None = None,
    type: str = "solution",
    note: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Crée un nœud dans l'arbre de veille R&D.

    Utile pour consigner une recherche technique : la solution évaluée, ce qui a
    été testé, la conclusion. Rattache-le à un thème existant via ``parent_id``
    plutôt que de créer une racine, sauf s'il s'agit d'un nouvel axe de veille.

    Args:
        title: Intitulé du nœud (ex. « Xsens MTw Awinda »).
        parent_id: Nœud parent ; absent = nouveau thème racine.
        type: theme | techno | solution | resource (défaut : solution).
        note: Note au format Markdown — le corps de la recherche.
        status: to_test | in_progress | promising | abandoned.
    """
    created = client().post(
        "/watch/nodes",
        {
            "title": title,
            "parent_id": parent_id,
            "type": type,
            "note": note or "",
            "status": status,
        },
    )
    return _watch_brief(created)


@mcp.tool()
def jirou_update_watch_node(
    node_id: int,
    title: str | None = None,
    note: str | None = None,
    status: str | None = None,
    type: str | None = None,
    parent_id: int | None = None,
) -> dict[str, Any]:
    """Modifie un nœud de veille : seuls les champs fournis changent.

    Sert notamment à faire évoluer le ``status`` d'une piste (``to_test`` →
    ``promising`` ou ``abandoned``) et à enrichir sa note.

    Args:
        node_id: Identifiant du nœud.
        title: Nouvel intitulé.
        note: Nouvelle note Markdown (remplace l'ancienne).
        status: to_test | in_progress | promising | abandoned.
        type: theme | techno | solution | resource.
        parent_id: Nouveau parent (refusé si cela crée un cycle).
    """
    payload = {
        "title": title,
        "note": note,
        "status": status,
        "type": type,
        "parent_id": parent_id,
    }
    if not any(value is not None for value in payload.values()):
        raise JirouError("Rien à modifier : précisez au moins un champ.")
    return _watch_brief(client().patch(f"/watch/nodes/{node_id}", payload))


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@mcp.tool()
def jirou_list_documents(project: str | None = None) -> list[dict[str, Any]]:
    """Liste les documents : ceux d'un projet, ou tous les documents visibles.

    Args:
        project: Clé du projet ; absent = tous les documents visibles, y compris
            les documents généraux (hors projet).
    """
    if project:
        project_id = client().project_id(project)
        documents = client().get(f"/projects/{project_id}/documents") or []
    else:
        documents = client().get("/documents") or []
    return [_document_brief(document) for document in documents]


@mcp.tool()
def jirou_get_document(document_id: int) -> dict[str, Any]:
    """Contenu complet d'un document.

    Args:
        document_id: Identifiant du document (donné par jirou_list_documents).
    """
    document = client().get(f"/documents/{document_id}")
    return _drop_empty({**_document_brief(document), "content": document.get("content")})


@mcp.tool()
def jirou_create_document(
    title: str, content: str = "", project: str | None = None
) -> dict[str, Any]:
    """Crée un document Markdown, dans un projet ou en document général.

    Utile pour déposer une note d'architecture, un compte rendu d'investigation
    ou une procédure là où l'équipe la retrouvera.

    Args:
        title: Titre du document.
        content: Contenu au format Markdown.
        project: Clé du projet ; absent = document général (hors projet).
    """
    payload = {"title": title, "content": content}
    if project:
        project_id = client().project_id(project)
        created = client().post(f"/projects/{project_id}/documents", payload)
    else:
        created = client().post("/documents", payload)
    return _document_brief(created)


@mcp.tool()
def jirou_update_document(
    document_id: int, title: str | None = None, content: str | None = None
) -> dict[str, Any]:
    """Modifie un document : seuls les champs fournis changent.

    Args:
        document_id: Identifiant du document.
        title: Nouveau titre.
        content: Nouveau contenu Markdown (remplace l'ancien — récupère d'abord
            l'existant avec jirou_get_document si tu veux l'enrichir).
    """
    payload = {"title": title, "content": content}
    if not any(value is not None for value in payload.values()):
        raise JirouError("Rien à modifier : précisez un titre ou un contenu.")
    return _document_brief(client().patch(f"/documents/{document_id}", payload))


def main() -> None:
    """Point d'entrée : sert le protocole MCP sur stdio (client : Claude Code)."""
    mcp.run(transport="stdio")
