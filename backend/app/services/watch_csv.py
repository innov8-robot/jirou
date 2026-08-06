"""Import CSV de sous-nœuds sous un nœud de veille existant.

Pendant *ancré* de l'export d'archive : au lieu de remplacer l'arbre entier, on
greffe une branche sous un nœud choisi. C'est le geste courant — « voilà ce que
j'ai trouvé sur cette techno, ajoute-le sous ce thème » — et il est bien moins
risqué qu'un import global.

Format attendu (en-tête obligatoire, virgule, UTF-8, noms de colonnes
insensibles à la casse) ::

    title,parent,type,status,note,links

- ``title`` : **obligatoire**, l'intitulé du nœud ;
- ``parent`` : titre d'une **autre ligne du fichier**. Vide = enfant direct du
  nœud d'ancrage. C'est ce qui permet de décrire un sous-arbre sur plusieurs
  niveaux sans connaître les identifiants de la base ;
- ``type`` : ``theme|techno|solution|resource`` (défaut ``solution``) ;
- ``status`` : ``to_test|in_progress|promising|abandoned`` (optionnel) ;
- ``note`` : note libre en Markdown ;
- ``links`` : URLs externes séparées par ``;``.

Robustesse — l'import ne doit jamais échouer en bloc à cause d'une ligne
douteuse, car le CSV est souvent produit par un LLM :

- une ligne sans ``title`` est ignorée et signalée ;
- un ``type``/``status`` inconnu est ignoré (valeur par défaut) avec un
  avertissement, la ligne est conservée ;
- un ``parent`` introuvable, ou impliqué dans un cycle, rattache la ligne au
  nœud d'ancrage avec un avertissement ;
- un titre en doublon est signalé : les références ``parent`` pointent alors sur
  sa première occurrence.

L'ensemble est persisté en **une seule transaction** (commit final).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.enums import WatchMediaKind, WatchNodeType, WatchStatus
from app.models.user import User
from app.models.watch import WatchMedia, WatchNode
from app.schemas.watch_csv import WatchCsvError, WatchCsvImportResult
from app.services.watch import WatchServiceError

# Nombre maximal de lignes de données acceptées (au-delà → 400).
MAX_ROWS = 500

# Colonne sans laquelle le fichier n'a pas de sens.
_REQUIRED_HEADER = "title"

# Type appliqué quand la colonne est absente ou invalide : sous un nœud existant,
# on décrit presque toujours des solutions/pistes, pas des thèmes.
_DEFAULT_TYPE = WatchNodeType.SOLUTION

# Séparateur des URLs dans la colonne ``links`` (aligné sur les labels de
# l'import CSV des tickets).
_LINK_SEPARATOR = ";"


@dataclass
class _Row:
    """Ligne validée, prête à devenir un :class:`WatchNode`."""

    row: int
    title: str
    parent: str | None
    type: WatchNodeType
    status: WatchStatus | None
    note: str
    links: list[str] = field(default_factory=list)


def _clean(value: str | None) -> str:
    """Normalise une cellule : ``None``/espaces → chaîne vide nettoyée."""
    return (value or "").strip()


def _decode(csv_bytes: bytes) -> list[list[str]]:
    """Décode l'UTF-8 (BOM toléré) et renvoie les lignes. Lève 400 si illisible."""
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WatchServiceError("bad_csv", "Le fichier n'est pas encodé en UTF-8.") from exc
    try:
        return list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise WatchServiceError("bad_csv", "CSV illisible.") from exc


def _parse_row(raw: dict[str, str], row: int) -> tuple[_Row | None, list[str]]:
    """Valide une ligne brute. ``(None, erreurs)`` si la ligne est rejetée."""
    title = _clean(raw.get("title"))
    if not title:
        return None, ["Ligne ignorée : la colonne « title » est obligatoire."]

    warnings: list[str] = []

    type_raw = _clean(raw.get("type")).lower()
    try:
        node_type = WatchNodeType(type_raw) if type_raw else _DEFAULT_TYPE
    except ValueError:
        node_type = _DEFAULT_TYPE
        warnings.append(f"type « {type_raw} » inconnu : « {_DEFAULT_TYPE.value} » appliqué.")

    status_raw = _clean(raw.get("status")).lower()
    status: WatchStatus | None = None
    if status_raw:
        try:
            status = WatchStatus(status_raw)
        except ValueError:
            warnings.append(f"statut « {status_raw} » inconnu : laissé vide.")

    links = [
        url
        for url in (part.strip() for part in _clean(raw.get("links")).split(_LINK_SEPARATOR))
        if url
    ]

    parsed = _Row(
        row=row,
        title=title,
        parent=_clean(raw.get("parent")) or None,
        type=node_type,
        status=status,
        note=_clean(raw.get("note")),
        links=links,
    )
    return parsed, warnings


def _order_rows(rows: list[_Row], errors: list[WatchCsvError]) -> list[tuple[_Row, str | None]]:
    """Ordonne les lignes parents-avant-enfants et normalise les parents douteux.

    Retourne ``(ligne, titre du parent effectif)`` ; ``None`` signifie « rattaché
    au nœud d'ancrage ». Un ``parent`` inconnu, auto-référent ou cyclique est
    ramené à ``None`` avec un avertissement — la branche importée reste
    exploitable au lieu d'être rejetée.
    """
    by_title: dict[str, _Row] = {}
    for row in rows:
        key = row.title.lower()
        if key in by_title:
            errors.append(
                WatchCsvError(
                    row=row.row,
                    message=(
                        f"titre « {row.title} » en doublon : les références « parent » "
                        "pointent sur la première occurrence."
                    ),
                )
            )
            continue
        by_title[key] = row

    children: dict[str | None, list[_Row]] = defaultdict(list)
    for row in rows:
        parent = row.parent
        if parent is not None:
            key = parent.lower()
            if key == row.title.lower():
                errors.append(
                    WatchCsvError(
                        row=row.row,
                        message="« parent » désigne la ligne elle-même : rattaché au nœud choisi.",
                    )
                )
                parent = None
            elif key not in by_title:
                errors.append(
                    WatchCsvError(
                        row=row.row,
                        message=(
                            f"parent « {parent} » absent du fichier : rattaché au nœud choisi."
                        ),
                    )
                )
                parent = None
        children[parent.lower() if parent else None].append(row)

    # Parcours en largeur depuis les lignes ancrées : parents avant enfants.
    ordered: list[tuple[_Row, str | None]] = []
    frontier = list(children[None])
    ordered.extend((row, None) for row in frontier)
    seen = {row.row for row in frontier}
    while frontier:
        next_frontier: list[_Row] = []
        for parent in frontier:
            for child in children[parent.title.lower()]:
                if child.row in seen:
                    continue
                seen.add(child.row)
                ordered.append((child, parent.title.lower()))
                next_frontier.append(child)
        frontier = next_frontier

    # Non atteintes : cycle de parents entre lignes → rattachées à l'ancrage.
    for row in rows:
        if row.row not in seen:
            seen.add(row.row)
            errors.append(
                WatchCsvError(
                    row=row.row,
                    message="cycle de « parent » détecté : rattaché au nœud choisi.",
                )
            )
            ordered.append((row, None))
    return ordered


def import_children_from_csv(
    db: Session,
    anchor: WatchNode,
    csv_bytes: bytes,
    creator: User,
) -> WatchCsvImportResult:
    """Crée des sous-nœuds de ``anchor`` depuis un CSV.

    Les nouveaux nœuds sont positionnés en éventail sous l'ancre, pour rester
    lisibles dans le graphe sans que l'utilisateur ait à les replacer un par un.

    :raises WatchServiceError: ``bad_csv`` (→ 400) si le fichier est illisible,
        vide, d'en-tête invalide, ou dépasse :data:`MAX_ROWS` lignes.
    """
    raw_rows = _decode(csv_bytes)
    if not raw_rows:
        raise WatchServiceError("bad_csv", "Le fichier CSV est vide.")

    header = [cell.strip().lower() for cell in raw_rows[0]]
    if _REQUIRED_HEADER not in header:
        raise WatchServiceError(
            "bad_csv", "En-tête invalide : la colonne « title » est obligatoire."
        )

    data_rows = raw_rows[1:]
    if len(data_rows) > MAX_ROWS:
        raise WatchServiceError(
            "bad_csv", f"Trop de lignes ({len(data_rows)}), maximum {MAX_ROWS}."
        )

    errors: list[WatchCsvError] = []
    parsed: list[_Row] = []
    for offset, cells in enumerate(data_rows, start=1):
        if not any(cell.strip() for cell in cells):
            continue  # ligne entièrement vide : ignorée silencieusement
        row, warnings = _parse_row(dict(zip(header, cells, strict=False)), offset)
        errors.extend(WatchCsvError(row=offset, message=msg) for msg in warnings)
        if row is None:
            continue
        parsed.append(row)

    ordered = _order_rows(parsed, errors)
    created_by_title: dict[str, WatchNode] = {}
    links_created = 0

    for index, (row, parent_key) in enumerate(ordered):
        parent_node = created_by_title.get(parent_key) if parent_key else None
        base = parent_node or anchor
        node = WatchNode(
            parent_id=base.id,
            title=row.title,
            type=row.type,
            note=row.note,
            status=row.status,
            # Éventail sous le parent : évite l'empilement de tous les nœuds au
            # même point, sans prétendre à une mise en page optimale.
            pos_x=base.pos_x + (index % 5 - 2) * 220,
            pos_y=base.pos_y + 180,
            created_by_id=creator.id,
        )
        db.add(node)
        db.flush()
        created_by_title.setdefault(row.title.lower(), node)

        for url in row.links:
            db.add(
                WatchMedia(
                    node_id=node.id,
                    kind=WatchMediaKind.LINK,
                    url=url[:2048],
                    created_by_id=creator.id,
                )
            )
            links_created += 1

    db.commit()
    return WatchCsvImportResult(
        anchor_id=anchor.id,
        nodes_created=len(ordered),
        links_created=links_created,
        error_count=len(errors),
        errors=errors,
    )
