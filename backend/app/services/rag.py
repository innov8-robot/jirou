"""Service du chatbot RAG (EPIC-10) : indexation Qdrant + réponses Mistral.

Architecture pensée pour être **testable sans réseau** : les seuls appels
sortants (Mistral) sont isolés dans :func:`embed_texts` et
:func:`chat_completion`, monkeypatchables dans les tests ; le client Qdrant est
fabriqué par :func:`get_qdrant_client`, lui aussi surchargeable (les tests
injectent un ``QdrantClient(location=":memory:")``).

Chaîne fonctionnelle :

- :func:`build_chunks` extrait, pour un ensemble de projets, les *chunks* à
  indexer (tickets, commentaires, documents — y compris les documents généraux
  ``project_id`` NULL, visibles de tous).
- :func:`reindex` calcule les embeddings par lots et les ``upsert`` dans Qdrant
  avec un *payload* complet.
- :func:`answer` restreint la recherche vectorielle aux projets dont
  l'utilisateur est membre (plus les documents généraux), construit un prompt et
  interroge le modèle de chat.

Aucun appel réseau n'est effectué à l'import du module.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import or_, select

from app.core.config import settings
from app.models.comment import Comment
from app.models.document import Document
from app.models.issue import Issue
from app.models.project import ProjectMember

if TYPE_CHECKING:  # pragma: no cover - imports de typage uniquement
    from qdrant_client import QdrantClient
    from sqlalchemy.orm import Session

    from app.models.user import User

# UUID de namespace stable pour dériver des identifiants de points déterministes
# (le même chunk réindexé écrase le point précédent au lieu d'en créer un autre).
_POINT_NAMESPACE = uuid.UUID("f1e2d3c4-b5a6-4788-9900-aabbccddeeff")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_SYSTEM_PROMPT = (
    "Tu es l'assistant Jirou, un chatbot d'aide sur un outil de gestion de "
    "projets et de tickets. Réponds en français, de façon concise, en "
    "t'appuyant UNIQUEMENT sur le contexte fourni ci-dessous. Cite les clés de "
    "tickets pertinentes (ex. JIR-42) quand elles existent. Si l'information ne "
    "figure pas dans le contexte, dis-le clairement sans inventer."
)


class RagNotConfigured(RuntimeError):
    """Le chatbot n'est pas configuré (clé API Mistral absente)."""


class RagUnavailable(RuntimeError):
    """Une dépendance externe (Qdrant / Mistral) est injoignable."""


# --------------------------------------------------------------------------- #
# Nettoyage de texte
# --------------------------------------------------------------------------- #
def strip_html(text: str | None) -> str:
    """Retire les balises HTML basiques et normalise les espaces."""
    if not text:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()


# --------------------------------------------------------------------------- #
# Appels Mistral (isolés pour être monkeypatchés dans les tests)
# --------------------------------------------------------------------------- #
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Calcule les embeddings de ``texts`` via l'API Mistral (``mistral-embed``).

    Lève :class:`RagNotConfigured` si la clé API est absente et
    :class:`RagUnavailable` en cas d'erreur réseau/HTTP.
    """
    if not settings.MISTRAL_API_KEY:
        raise RagNotConfigured("Chatbot non configuré : renseignez MISTRAL_API_KEY.")
    if not texts:
        return []
    try:
        resp = httpx.post(
            f"{settings.MISTRAL_API_BASE}/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
            json={"model": settings.MISTRAL_EMBED_MODEL, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
    except httpx.HTTPError as exc:
        raise RagUnavailable(f"Service d'embeddings Mistral injoignable : {exc}") from exc
    return [item["embedding"] for item in data]


def chat_completion(messages: list[dict]) -> str:
    """Appelle l'API de chat Mistral et renvoie le texte de la réponse.

    Lève :class:`RagNotConfigured` si la clé est absente et
    :class:`RagUnavailable` en cas d'erreur réseau/HTTP.
    """
    if not settings.MISTRAL_API_KEY:
        raise RagNotConfigured("Chatbot non configuré : renseignez MISTRAL_API_KEY.")
    try:
        resp = httpx.post(
            f"{settings.MISTRAL_API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
            json={"model": settings.MISTRAL_CHAT_MODEL, "messages": messages},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise RagUnavailable(f"Service de chat Mistral injoignable : {exc}") from exc
    return data["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------- #
# Client Qdrant
# --------------------------------------------------------------------------- #
_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Retourne un client Qdrant (mis en cache au niveau module).

    Surchargeable dans les tests pour injecter un client en mémoire.
    """
    global _client
    if _client is None:
        from qdrant_client import QdrantClient

        _client = QdrantClient(url=settings.QDRANT_URL)
    return _client


def ensure_collection(client: QdrantClient) -> None:
    """Crée la collection RAG (taille ``RAG_EMBED_DIM``, distance Cosine) si absente."""
    from qdrant_client import models

    if client.collection_exists(settings.RAG_COLLECTION):
        return
    client.create_collection(
        collection_name=settings.RAG_COLLECTION,
        vectors_config=models.VectorParams(
            size=settings.RAG_EMBED_DIM, distance=models.Distance.COSINE
        ),
    )


# --------------------------------------------------------------------------- #
# Construction des chunks
# --------------------------------------------------------------------------- #
def _chunk_id(kind: str, obj_id: int) -> str:
    """Identifiant de point Qdrant déterministe pour un chunk donné."""
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{kind}:{obj_id}"))


def build_chunks(db: Session, project_ids: list[int]) -> list[dict]:
    """Construit les chunks à indexer pour ``project_ids``.

    Inclut :

    - un chunk par **ticket** des projets ;
    - un chunk par **commentaire** rattaché à un ticket de ces projets ;
    - un chunk par **document** de ces projets **plus les documents généraux**
      (``project_id`` NULL), accessibles à tous.

    Chaque chunk porte un ``point_id`` déterministe, un ``payload`` (kind,
    project_id, issue_key, title, is_general) et le ``text`` à embedder.
    """
    chunks: list[dict] = []

    if project_ids:
        issues = list(
            db.execute(select(Issue).where(Issue.project_id.in_(project_ids))).scalars().all()
        )
        issue_by_id = {issue.id: issue for issue in issues}
        for issue in issues:
            summary = issue.summary or ""
            description = strip_html(issue.description)
            status = getattr(issue.status, "value", issue.status)
            itype = getattr(issue.type, "value", issue.type)
            priority = getattr(issue.priority, "value", issue.priority)
            meta = f"Type: {itype} | Statut: {status} | Priorité: {priority}"
            if issue.story_points is not None:
                meta += f" | Points: {issue.story_points}"
            text = f"{issue.key} {summary}\n{meta}\n{description}".strip()
            chunks.append(
                {
                    "point_id": _chunk_id("issue", issue.id),
                    "payload": {
                        "kind": "issue",
                        "project_id": issue.project_id,
                        "issue_key": issue.key,
                        "title": summary,
                        "is_general": False,
                        "text": text,
                    },
                    "text": text,
                }
            )

        if issue_by_id:
            comments = list(
                db.execute(select(Comment).where(Comment.issue_id.in_(list(issue_by_id))))
                .scalars()
                .all()
            )
            for comment in comments:
                issue = issue_by_id[comment.issue_id]
                body = strip_html(comment.body)
                chunks.append(
                    {
                        "point_id": _chunk_id("comment", comment.id),
                        "payload": {
                            "kind": "comment",
                            "project_id": issue.project_id,
                            "issue_key": issue.key,
                            "title": issue.summary or "",
                            "is_general": False,
                            "text": body,
                        },
                        "text": body,
                    }
                )

    # Documents des projets ciblés + documents généraux (project_id NULL).
    doc_filter = Document.project_id.is_(None)
    if project_ids:
        doc_filter = or_(doc_filter, Document.project_id.in_(project_ids))
    documents = list(db.execute(select(Document).where(doc_filter)).scalars().all())
    for document in documents:
        is_general = document.project_id is None
        content = strip_html(document.content)
        text = f"{document.title}\n{content}".strip()
        chunks.append(
            {
                "point_id": _chunk_id("document", document.id),
                "payload": {
                    "kind": "document",
                    "project_id": document.project_id,
                    "issue_key": None,
                    "title": document.title,
                    "is_general": is_general,
                    "text": text,
                },
                "text": text,
            }
        )

    return chunks


# --------------------------------------------------------------------------- #
# Indexation
# --------------------------------------------------------------------------- #
def reindex(
    db: Session,
    project_ids: list[int],
    *,
    client: QdrantClient | None = None,
    batch_size: int = 64,
) -> int:
    """(Ré)indexe ``project_ids`` (+ documents généraux) dans Qdrant.

    Calcule les embeddings par lots puis ``upsert`` les points avec leur payload.
    Retourne le nombre de points indexés.
    """
    from qdrant_client import models

    client = client or get_qdrant_client()
    try:
        ensure_collection(client)
    except RagNotConfigured:
        raise
    except Exception as exc:  # noqa: BLE001 - Qdrant injoignable => 503 côté endpoint
        raise RagUnavailable(f"Qdrant injoignable : {exc}") from exc

    chunks = build_chunks(db, project_ids)
    if not chunks:
        return 0

    points: list[models.PointStruct] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embed_texts([c["text"] for c in batch])
        for chunk, vector in zip(batch, vectors, strict=True):
            points.append(
                models.PointStruct(id=chunk["point_id"], vector=vector, payload=chunk["payload"])
            )

    try:
        client.upsert(collection_name=settings.RAG_COLLECTION, points=points)
    except Exception as exc:  # noqa: BLE001
        raise RagUnavailable(f"Qdrant injoignable : {exc}") from exc
    return len(points)


# --------------------------------------------------------------------------- #
# Restriction d'accès
# --------------------------------------------------------------------------- #
def member_project_ids(db: Session, user: User) -> list[int]:
    """Identifiants des projets dont ``user`` est membre (archivés inclus)."""
    rows = db.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    ).scalars()
    return sorted(set(rows))


def _access_filter(project_ids: list[int]) -> object:
    """Filtre Qdrant : ``project_id IN project_ids`` OU document général.

    Garantit qu'un utilisateur ne récupère jamais le contenu d'un projet dont il
    n'est pas membre. Les documents généraux (``is_general``) sont accessibles à
    tous.
    """
    from qdrant_client import models

    should: list[object] = [
        models.FieldCondition(key="is_general", match=models.MatchValue(value=True)),
    ]
    if project_ids:
        should.append(
            models.FieldCondition(key="project_id", match=models.MatchAny(any=project_ids))
        )
    return models.Filter(should=should)


# --------------------------------------------------------------------------- #
# Question / réponse
# --------------------------------------------------------------------------- #
def answer(
    db: Session,
    user: User,
    question: str,
    *,
    client: QdrantClient | None = None,
    top_k: int = 6,
) -> dict:
    """Répond à ``question`` en s'appuyant sur les chunks accessibles à ``user``.

    Retourne ``{"answer": str, "sources": list[dict]}``. Lève
    :class:`RagNotConfigured` si la clé Mistral est absente et
    :class:`RagUnavailable` si Qdrant/Mistral est injoignable.
    """
    client = client or get_qdrant_client()
    project_ids = member_project_ids(db, user)

    query_vector = embed_texts([question])[0]

    try:
        ensure_collection(client)
        response = client.query_points(
            collection_name=settings.RAG_COLLECTION,
            query=query_vector,
            query_filter=_access_filter(project_ids),
            limit=top_k,
            with_payload=True,
        )
        hits = response.points
    except RagNotConfigured:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RagUnavailable(f"Qdrant injoignable : {exc}") from exc

    sources: list[dict] = []
    context_blocks: list[str] = []
    for hit in hits:
        payload = hit.payload or {}
        sources.append(
            {
                "kind": payload.get("kind"),
                "project_id": payload.get("project_id"),
                "issue_key": payload.get("issue_key"),
                "title": payload.get("title"),
            }
        )
        label = payload.get("issue_key") or payload.get("title") or payload.get("kind", "")
        context_blocks.append(f"[{payload.get('kind')}] {label}\n{payload.get('text', '')}".strip())

    context = "\n\n".join(context_blocks) if context_blocks else "(aucun contexte pertinent)"
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Contexte :\n{context}\n\nQuestion : {question}",
        },
    ]
    generated = chat_completion(messages)
    return {"answer": generated, "sources": sources}
