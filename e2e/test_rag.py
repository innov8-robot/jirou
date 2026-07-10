"""Chatbot RAG — end-to-end. S'adapte à la présence ou non de MISTRAL_API_KEY."""

from __future__ import annotations

import httpx


def test_rag_status_shape(api: httpx.Client, new_user: dict) -> None:
    r = api.get('/rag/status', headers=new_user['auth_header'])
    assert r.status_code == 200
    assert isinstance(r.json().get('enabled'), bool)


def test_rag_chat_flow(api: httpx.Client, new_user: dict) -> None:
    h = new_user['auth_header']
    enabled = api.get('/rag/status', headers=h).json()['enabled']

    if not enabled:
        # Sans clé Mistral configurée : le chat doit répondre 503 (pas 500).
        r = api.post('/rag/chat', headers=h, json={'question': 'test'})
        assert r.status_code == 503, r.text
    else:
        # Clé configurée : réindexation puis question réelle.
        api.post('/rag/reindex', headers=h)
        r = api.post(
            '/rag/chat',
            headers=h,
            json={'question': 'Quels tickets sont en cours ?'},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body['answer'], str) and body['answer']
        assert isinstance(body['sources'], list)
