"""Tests des outils MCP : câblage, traduction des arguments, forme des réponses.

Trois choses sont vérifiées ici :

1. **le câblage** — les outils attendus sont enregistrés sur le serveur, avec un
   schéma d'entrée et une description (c'est ce que le modèle lit pour choisir) ;
2. **la traduction** — un e-mail devient un ``assignee_id``, un nom de sprint un
   ``sprint_id``, une clé de projet un ``project_id`` : on inspecte la requête
   réellement envoyée à l'API ;
3. **la compacité** — les réponses ne portent que les champs utiles, sans les
   entiers internes ni les clés vides.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx
from tests.conftest import ISSUE, ISSUE_DETAIL, PROJECT

from jirou_mcp import server
from jirou_mcp.client import JirouError
from jirou_mcp.server import (
    jirou_add_comment,
    jirou_create_document,
    jirou_create_issue,
    jirou_create_watch_node,
    jirou_get_backlog,
    jirou_get_issue,
    jirou_list_comments,
    jirou_list_projects,
    jirou_list_sprints,
    jirou_list_watch_nodes,
    jirou_move_issue_to_sprint,
    jirou_search_issues,
    jirou_update_document,
    jirou_update_issue,
    jirou_update_watch_node,
)


def _body(route: respx.Route) -> dict[str, Any]:
    """Corps JSON de la dernière requête interceptée."""
    return json.loads(route.calls.last.request.read().decode())


def _mock_projects(api: respx.MockRouter) -> None:
    api.get("/projects").mock(return_value=httpx.Response(200, json=[PROJECT]))


def _mock_issue(api: respx.MockRouter) -> None:
    api.get("/issues/JIR-42").mock(return_value=httpx.Response(200, json=ISSUE_DETAIL))


# --------------------------------------------------------------------------- #
# Câblage MCP
# --------------------------------------------------------------------------- #
def test_expected_tools_are_registered() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "jirou_list_projects",
        "jirou_search_issues",
        "jirou_get_issue",
        "jirou_create_issue",
        "jirou_update_issue",
        "jirou_list_comments",
        "jirou_add_comment",
        "jirou_list_sprints",
        "jirou_get_backlog",
        "jirou_move_issue_to_sprint",
        "jirou_list_watch_nodes",
        "jirou_get_watch_node",
        "jirou_create_watch_node",
        "jirou_update_watch_node",
        "jirou_list_documents",
        "jirou_get_document",
        "jirou_create_document",
        "jirou_update_document",
    } <= names


def test_no_destructive_tool_is_exposed() -> None:
    """Un agent peut créer, corriger, commenter — pas supprimer."""
    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert not [n for n in names if "delete" in n or "remove" in n or "revoke" in n]


def test_every_tool_has_a_description_and_schema() -> None:
    for tool in asyncio.run(server.mcp.list_tools()):
        assert tool.description, f"{tool.name} sans description"
        assert tool.input_schema.get("type") == "object", f"{tool.name} sans schéma"


def test_tool_schema_uses_readable_identifiers() -> None:
    """La signature exposée parle en clés/e-mails, pas en identifiants numériques."""
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    props = tools["jirou_create_issue"].input_schema["properties"]
    assert "project" in props and "assignee_email" in props
    assert "project_id" not in props and "assignee_id" not in props


# --------------------------------------------------------------------------- #
# Projets & recherche
# --------------------------------------------------------------------------- #
def test_list_projects_is_compact(api: respx.MockRouter) -> None:
    _mock_projects(api)
    assert jirou_list_projects() == [
        {
            "key": "JIR",
            "name": "Jirou",
            "description": "Le suivi de projet",
            "my_role": "admin",
        }
    ]


def test_search_issues_translates_filters(api: respx.MockRouter) -> None:
    _mock_projects(api)
    api.get("/projects/7").mock(return_value=httpx.Response(200, json=PROJECT))
    api.get("/projects/7/sprints").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "name": "Sprint 2", "status": "active"}])
    )
    route = api.get("/projects/7/issues").mock(return_value=httpx.Response(200, json=[ISSUE]))

    result = jirou_search_issues(
        project="JIR",
        status="todo",
        assignee_email="dev@example.com",
        sprint="active",
        limit=5,
    )

    url = str(route.calls.last.request.url)
    assert "status=todo" in url
    assert "assignee_id=3" in url
    assert "sprint_id=2" in url
    assert "limit=5" in url
    assert result == [
        {
            "key": "JIR-42",
            "type": "bug",
            "summary": "Le bouton ne répond pas",
            "status": "todo",
            "priority": "high",
            "story_points": 3,
            "assignee": "dev@example.com",
            "labels": ["frontend"],
        }
    ]


def test_search_issues_clamps_limit(api: respx.MockRouter) -> None:
    _mock_projects(api)
    route = api.get("/projects/7/issues").mock(return_value=httpx.Response(200, json=[]))
    jirou_search_issues(project="JIR", limit=9999)
    assert "limit=200" in str(route.calls.last.request.url)


def test_get_issue_returns_description(api: respx.MockRouter) -> None:
    _mock_issue(api)
    detail = jirou_get_issue("jir-42")
    assert detail["description"] == "Cliquer ne déclenche rien en Safari."
    assert detail["reporter"] == "lead@example.com"
    # Les clés vides sont retirées.
    assert "children" not in detail
    assert "dependencies" not in detail


def test_get_issue_uppercases_the_key(api: respx.MockRouter) -> None:
    route = api.get("/issues/JIR-42").mock(return_value=httpx.Response(200, json=ISSUE_DETAIL))
    jirou_get_issue("  jir-42 ")
    assert route.call_count == 1


# --------------------------------------------------------------------------- #
# Création & modification de tickets
# --------------------------------------------------------------------------- #
def test_create_issue_resolves_assignee_epic_and_labels(api: respx.MockRouter) -> None:
    _mock_projects(api)
    api.get("/projects/7").mock(return_value=httpx.Response(200, json=PROJECT))
    api.get("/projects/7/issues").mock(
        return_value=httpx.Response(200, json=[{"id": 11, "key": "JIR-3", "summary": "Socle"}])
    )
    api.get("/projects/7/labels").mock(return_value=httpx.Response(200, json=[]))
    api.post("/projects/7/labels").mock(
        return_value=httpx.Response(201, json={"id": 9, "name": "perf"})
    )
    route = api.post("/projects/7/issues").mock(return_value=httpx.Response(201, json=ISSUE))

    jirou_create_issue(
        project="JIR",
        summary="Le bouton ne répond pas",
        type="bug",
        priority="high",
        assignee_email="dev@example.com",
        epic="Socle",
        labels=["perf"],
    )

    body = _body(route)
    assert body["assignee_id"] == 3
    assert body["epic_id"] == 11
    assert body["label_ids"] == [9]
    assert body["type"] == "bug"
    # Les champs non fournis ne sont pas envoyés (l'API refuse les extras nuls).
    assert "story_points" not in body
    assert "due_date" not in body


def test_create_issue_defaults_to_task(api: respx.MockRouter) -> None:
    _mock_projects(api)
    route = api.post("/projects/7/issues").mock(return_value=httpx.Response(201, json=ISSUE))
    jirou_create_issue(project="JIR", summary="Une tâche")
    assert _body(route)["type"] == "task"


def test_update_issue_sends_only_given_fields(api: respx.MockRouter) -> None:
    _mock_issue(api)
    route = api.patch("/issues/JIR-42").mock(return_value=httpx.Response(200, json=ISSUE))
    jirou_update_issue(key="JIR-42", status="in_review")
    assert _body(route) == {"status": "in_review"}


def test_update_issue_without_any_field_is_rejected(api: respx.MockRouter) -> None:
    _mock_issue(api)
    with pytest.raises(JirouError) as excinfo:
        jirou_update_issue(key="JIR-42")
    assert "Rien à modifier" in str(excinfo.value)


def test_update_issue_resolves_assignee_within_the_issue_project(
    api: respx.MockRouter,
) -> None:
    """Le projet vient du ticket : pas besoin de le préciser pour assigner."""
    _mock_issue(api)
    api.get("/projects/7").mock(return_value=httpx.Response(200, json=PROJECT))
    route = api.patch("/issues/JIR-42").mock(return_value=httpx.Response(200, json=ISSUE))
    jirou_update_issue(key="JIR-42", assignee_email="dev@example.com")
    assert _body(route) == {"assignee_id": 3}


# --------------------------------------------------------------------------- #
# Commentaires
# --------------------------------------------------------------------------- #
def test_list_comments(api: respx.MockRouter) -> None:
    _mock_issue(api)
    api.get("/issues/JIR-42/comments").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "body": "Reproduit en Safari 17.",
                    "created_at": "2026-07-02T09:00:00Z",
                    "author": {
                        "id": 3,
                        "email": "dev@example.com",
                        "full_name": "Dev",
                        "role": "member",
                    },
                }
            ],
        )
    )
    assert jirou_list_comments("JIR-42") == [
        {
            "author": "dev@example.com",
            "body": "Reproduit en Safari 17.",
            "created_at": "2026-07-02T09:00:00Z",
        }
    ]


def test_add_comment(api: respx.MockRouter) -> None:
    _mock_issue(api)
    route = api.post("/issues/JIR-42/comments").mock(
        return_value=httpx.Response(
            201, json={"id": 2, "body": "Corrigé dans abc123.", "author": None}
        )
    )
    result = jirou_add_comment("JIR-42", "Corrigé dans abc123.")
    assert _body(route) == {"body": "Corrigé dans abc123."}
    assert result["body"] == "Corrigé dans abc123."


# --------------------------------------------------------------------------- #
# Sprints & backlog
# --------------------------------------------------------------------------- #
def test_list_sprints(api: respx.MockRouter) -> None:
    _mock_projects(api)
    api.get("/projects/7/sprints").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 2,
                    "name": "Sprint 2",
                    "status": "active",
                    "goal": "Sortir l'export",
                    "issue_count": 4,
                }
            ],
        )
    )
    assert jirou_list_sprints("JIR") == [
        {
            "name": "Sprint 2",
            "status": "active",
            "goal": "Sortir l'export",
            "issue_count": 4,
        }
    ]


def test_get_backlog_groups_by_sprint(api: respx.MockRouter) -> None:
    """``backlog`` est un objet ``{issues, points}`` côté API, pas une liste."""
    _mock_projects(api)
    api.get("/projects/7/backlog").mock(
        return_value=httpx.Response(
            200,
            json={
                "sprints": [
                    {
                        "sprint": {"id": 2, "name": "Sprint 2", "status": "active"},
                        "issues": [ISSUE],
                        "points": 3,
                    }
                ],
                "backlog": {"issues": [ISSUE], "points": 3},
            },
        )
    )
    backlog = jirou_get_backlog("JIR")
    assert backlog["sprints"][0]["name"] == "Sprint 2"
    assert backlog["sprints"][0]["points"] == 3
    assert backlog["sprints"][0]["issues"][0]["key"] == "JIR-42"
    assert backlog["backlog"]["points"] == 3
    assert backlog["backlog"]["issues"][0]["key"] == "JIR-42"


def test_move_issue_to_sprint(api: respx.MockRouter) -> None:
    _mock_issue(api)
    api.get("/projects/7/sprints").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "name": "Sprint 2", "status": "active"}])
    )
    route = api.patch("/issues/JIR-42/backlog-move").mock(
        return_value=httpx.Response(200, json=ISSUE)
    )
    jirou_move_issue_to_sprint("JIR-42", sprint="active", position=1)
    assert _body(route) == {"sprint_id": 2, "position": 1}


def test_move_issue_back_to_backlog_sends_null_sprint(api: respx.MockRouter) -> None:
    """``sprint_id: null`` est significatif ici : la clé doit être envoyée."""
    _mock_issue(api)
    route = api.patch("/issues/JIR-42/backlog-move").mock(
        return_value=httpx.Response(200, json=ISSUE)
    )
    jirou_move_issue_to_sprint("JIR-42")
    assert _body(route) == {"sprint_id": None, "position": 0}


# --------------------------------------------------------------------------- #
# Veille
# --------------------------------------------------------------------------- #
def test_list_watch_nodes(api: respx.MockRouter) -> None:
    api.get("/watch/nodes").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "parent_id": None,
                    "title": "Mocap suit",
                    "type": "theme",
                    "status": None,
                    "pos_x": 0,
                    "pos_y": 0,
                    "media_count": 0,
                    "comment_count": 0,
                    "preview": None,
                }
            ],
        )
    )
    # Les positions du graphe (pos_x/pos_y) et le preview nul sont écartés ;
    # les compteurs restent, y compris à zéro (« rien attaché » est une info).
    assert jirou_list_watch_nodes() == [
        {
            "id": 1,
            "title": "Mocap suit",
            "type": "theme",
            "media_count": 0,
            "comment_count": 0,
        }
    ]


def test_create_watch_node(api: respx.MockRouter) -> None:
    route = api.post("/watch/nodes").mock(
        return_value=httpx.Response(
            201, json={"id": 5, "parent_id": 1, "title": "Xsens", "type": "techno"}
        )
    )
    jirou_create_watch_node(title="Xsens", parent_id=1, type="techno", note="# Essais")
    assert _body(route) == {
        "title": "Xsens",
        "parent_id": 1,
        "type": "techno",
        "note": "# Essais",
    }


def test_update_watch_node_requires_a_field(api: respx.MockRouter) -> None:
    with pytest.raises(JirouError):
        jirou_update_watch_node(node_id=5)


def test_update_watch_node_status(api: respx.MockRouter) -> None:
    route = api.patch("/watch/nodes/5").mock(
        return_value=httpx.Response(
            200, json={"id": 5, "title": "Xsens", "type": "techno", "status": "promising"}
        )
    )
    jirou_update_watch_node(node_id=5, status="promising")
    assert _body(route) == {"status": "promising"}


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
def test_create_document_in_a_project(api: respx.MockRouter) -> None:
    _mock_projects(api)
    route = api.post("/projects/7/documents").mock(
        return_value=httpx.Response(201, json={"id": 3, "title": "Archi", "project_id": 7})
    )
    jirou_create_document(title="Archi", content="# Archi", project="JIR")
    assert _body(route) == {"title": "Archi", "content": "# Archi"}


def test_create_general_document_without_project(api: respx.MockRouter) -> None:
    route = api.post("/documents").mock(
        return_value=httpx.Response(201, json={"id": 4, "title": "Notes", "project_id": None})
    )
    result = jirou_create_document(title="Notes")
    assert route.call_count == 1
    assert "project_id" not in result


def test_update_document_requires_a_field(api: respx.MockRouter) -> None:
    with pytest.raises(JirouError):
        jirou_update_document(document_id=3)
