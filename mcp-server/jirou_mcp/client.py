"""Client HTTP de l'API Jirou, taillé pour un usage par un agent.

Deux responsabilités :

1. **transport** — un ``httpx.Client`` authentifié par jeton d'API personnel,
   qui traduit les erreurs HTTP en :class:`JirouError` portant le ``detail``
   renvoyé par l'API (c'est ce texte que l'agent lira) ;
2. **résolution des identifiants lisibles** — l'API travaille avec des entiers
   (``project_id``, ``assignee_id``, ``sprint_id``, ``label_ids``), l'agent
   raisonne avec ce qu'il voit dans le dépôt et la conversation : une clé de
   projet (``JIR``), une clé de ticket (``JIR-42``), un e-mail, un nom de
   sprint. Les helpers ``resolve_*`` font la traduction, avec un cache par
   processus pour éviter de re-lister à chaque appel.

Configuration par variables d'environnement (cf. le README) :
``JIROU_API_URL`` et ``JIROU_TOKEN``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# Timeout généreux : certaines routes (rapports LLM, réindexation) sont lentes.
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Préfixe versionné de l'API métier (cf. docs/CONVENTIONS.md).
_API_PREFIX = "/api/v1"


class JirouError(RuntimeError):
    """Erreur renvoyée à l'agent : message lisible, sans trace technique.

    Le texte est celui du champ ``detail`` de l'API quand il existe — l'agent
    peut donc lire « Rôle projet insuffisant pour cette action. » plutôt qu'un
    code HTTP nu.
    """


class ConfigError(JirouError):
    """Configuration absente ou invalide (variables d'environnement)."""


def _clean(value: str | None) -> str | None:
    """Normalise une chaîne optionnelle : vide ou blancs → ``None``."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class JirouClient:
    """Accès à l'API Jirou avec résolution des identifiants lisibles.

    Instancié une fois par processus (le serveur MCP est mono-utilisateur) ;
    ``close()`` libère la connexion.
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._http = httpx.Client(
            base_url=f"{base_url.rstrip('/')}{_API_PREFIX}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
        # Caches de résolution, remplis à la demande.
        self._projects: list[dict[str, Any]] | None = None
        self._members: dict[int, list[dict[str, Any]]] = {}

    @classmethod
    def from_env(cls) -> JirouClient:
        """Construit le client depuis l'environnement.

        Lève :class:`ConfigError` si ``JIROU_API_URL`` ou ``JIROU_TOKEN`` manque —
        message explicite, car c'est l'erreur de configuration la plus probable.
        """
        base_url = _clean(os.environ.get("JIROU_API_URL"))
        token = _clean(os.environ.get("JIROU_TOKEN"))
        missing = [
            name
            for name, value in (("JIROU_API_URL", base_url), ("JIROU_TOKEN", token))
            if value is None
        ]
        if missing:
            raise ConfigError(
                f"Variable(s) d'environnement manquante(s) : {', '.join(missing)}. "
                "Renseignez-les dans la configuration MCP (cf. mcp-server/README.md)."
            )
        assert base_url is not None and token is not None
        return cls(base_url, token)

    def close(self) -> None:
        """Ferme la connexion HTTP sous-jacente."""
        self._http.close()

    # ----------------------------------------------------------------- #
    # Transport
    # ----------------------------------------------------------------- #
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        keep_none: tuple[str, ...] = (),
    ) -> Any:
        """Appelle l'API et retourne le JSON décodé (``None`` sur 204).

        Les paramètres et champs à ``None`` sont retirés par défaut : les mises à
        jour de l'API sont partielles (``exclude_unset``), donc « non fourni »
        doit vouloir dire « ne pas toucher », pas « mettre à ``null`` ».

        ``keep_none`` liste les champs pour lesquels ``None`` est **significatif**
        et doit partir tel quel — typiquement ``sprint_id: null`` qui veut dire
        « renvoyer au backlog ».
        """
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        clean_json = {k: v for k, v in (json or {}).items() if v is not None or k in keep_none}
        try:
            response = self._http.request(
                method,
                path,
                params=clean_params or None,
                json=clean_json if json is not None else None,
            )
        except httpx.HTTPError as exc:
            raise JirouError(f"Appel à l'API Jirou impossible : {exc}") from exc

        if response.status_code == 401:
            raise JirouError(
                "Jeton d'API refusé (401). Il est peut-être révoqué ou expiré : "
                "créez-en un nouveau dans Jirou → Mon profil → Jetons d'API."
            )
        if response.status_code >= 400:
            raise JirouError(f"{response.status_code} — {self._detail(response)}")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        """Extrait un message lisible du corps d'erreur de l'API."""
        try:
            payload = response.json()
        except ValueError:
            return response.text[:400] or response.reason_phrase
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, str):
            return detail
        # Erreur de validation FastAPI : liste d'objets {loc, msg, ...}.
        if isinstance(detail, list):
            return "; ".join(
                f"{'.'.join(str(p) for p in item.get('loc', [])[1:])}: {item.get('msg', '')}"
                for item in detail
                if isinstance(item, dict)
            )
        return str(payload)[:400]

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, json=payload or {})

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PATCH", path, json=payload)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # ----------------------------------------------------------------- #
    # Résolution : projet
    # ----------------------------------------------------------------- #
    def projects(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        """Mes projets (mis en cache pour la durée du processus)."""
        if self._projects is None or refresh:
            self._projects = self.get("/projects") or []
        return self._projects

    def resolve_project(self, ref: str | int) -> dict[str, Any]:
        """Résout un projet par clé (``JIR``), identifiant numérique ou nom.

        La correspondance sur la clé et le nom est insensible à la casse. Lève
        :class:`JirouError` en listant les projets disponibles si rien ne
        correspond — l'agent peut alors corriger seul.
        """
        needle = str(ref).strip()
        if not needle:
            raise JirouError("Projet non précisé : donnez sa clé (ex. « JIR »).")

        for attempt in (False, True):
            projects = self.projects(refresh=attempt)
            if needle.isdigit():
                match = next((p for p in projects if p["id"] == int(needle)), None)
                if match:
                    return match
            lowered = needle.lower()
            match = next((p for p in projects if p["key"].lower() == lowered), None)
            if match:
                return match
            match = next((p for p in projects if p["name"].lower() == lowered), None)
            if match:
                return match

        available = ", ".join(f"{p['key']} ({p['name']})" for p in self.projects()) or "aucun"
        raise JirouError(f"Projet « {needle} » introuvable. Projets accessibles : {available}.")

    def project_id(self, ref: str | int) -> int:
        """Identifiant numérique d'un projet désigné de façon lisible."""
        return int(self.resolve_project(ref)["id"])

    # ----------------------------------------------------------------- #
    # Résolution : membres, epics, sprints, labels
    # ----------------------------------------------------------------- #
    def members(self, project_id: int, *, refresh: bool = False) -> list[dict[str, Any]]:
        """Membres d'un projet (mis en cache par projet)."""
        if project_id not in self._members or refresh:
            detail = self.get(f"/projects/{project_id}")
            self._members[project_id] = detail.get("members", [])
        return self._members[project_id]

    def resolve_user_id(self, project_id: int, email: str) -> int:
        """Identifiant d'un membre du projet à partir de son e-mail.

        Lève :class:`JirouError` en listant les membres si l'e-mail n'est pas
        celui d'un membre — un ticket ne peut être assigné qu'à un membre.
        """
        needle = email.strip().lower()
        for attempt in (False, True):
            for member in self.members(project_id, refresh=attempt):
                if member["user"]["email"].lower() == needle:
                    return int(member["user_id"])
        emails = ", ".join(m["user"]["email"] for m in self.members(project_id)) or "aucun"
        raise JirouError(f"« {email} » n'est pas membre de ce projet. Membres : {emails}.")

    def resolve_issue(self, key: str) -> dict[str, Any]:
        """Détail d'un ticket par sa clé (``JIR-42``), insensible à la casse."""
        needle = key.strip().upper()
        if not needle:
            raise JirouError("Clé de ticket non précisée (ex. « JIR-42 »).")
        return self.get(f"/issues/{needle}")

    def resolve_epic_id(self, project_id: int, ref: str) -> int:
        """Identifiant d'une epic du projet, par clé (``JIR-3``) ou par résumé."""
        needle = ref.strip()
        epics = self.get(f"/projects/{project_id}/issues", type="epic", limit=200) or []
        match = next((e for e in epics if e["key"].lower() == needle.lower()), None)
        if match is None:
            match = next((e for e in epics if e["summary"].lower() == needle.lower()), None)
        if match is None:
            available = ", ".join(f"{e['key']} ({e['summary']})" for e in epics) or "aucune"
            raise JirouError(f"Epic « {ref} » introuvable. Epics du projet : {available}.")
        return int(match["id"])

    def resolve_sprint_id(self, project_id: int, ref: str) -> int:
        """Identifiant d'un sprint du projet, par nom ou identifiant numérique.

        ``ref`` valant ``active`` désigne le sprint actif.
        """
        needle = ref.strip()
        sprints = self.get(f"/projects/{project_id}/sprints") or []
        if needle.isdigit():
            match = next((s for s in sprints if s["id"] == int(needle)), None)
        elif needle.lower() == "active":
            match = next((s for s in sprints if s["status"] == "active"), None)
        else:
            match = next((s for s in sprints if s["name"].lower() == needle.lower()), None)
        if match is None:
            available = ", ".join(f"{s['name']} [{s['status']}]" for s in sprints) or "aucun"
            raise JirouError(f"Sprint « {ref} » introuvable. Sprints du projet : {available}.")
        return int(match["id"])

    def resolve_label_ids(self, project_id: int, names: list[str]) -> list[int]:
        """Identifiants des labels nommés, **créant** ceux qui n'existent pas.

        Aligné sur l'import CSV, qui crée aussi les labels à la volée : l'agent
        peut poser un label sans avoir à le déclarer d'abord.
        """
        existing = self.get(f"/projects/{project_id}/labels") or []
        by_name = {label["name"].lower(): label for label in existing}
        resolved: list[int] = []
        seen: set[str] = set()
        for raw in names:
            name = raw.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            label = by_name.get(name.lower())
            if label is None:
                label = self.post(
                    f"/projects/{project_id}/labels",
                    {"name": name, "color": "#94A3B8"},
                )
                by_name[name.lower()] = label
            resolved.append(int(label["id"]))
        return resolved
