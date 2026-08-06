"""Schémas de l'import CSV de sous-nœuds de veille.

Contrat de sortie de ``POST /watch/nodes/{id}/import``. L'import est *ancré* : les
nœuds créés sont rattachés au nœud choisi, pas à la racine — on enrichit une
branche existante au lieu de remplacer l'arbre.

Comme l'import CSV des tickets, il est **robuste** : chaque ligne est validée
indépendamment, une ligne invalide est ignorée et signalée dans ``errors`` sans
faire échouer le lot.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# En-tête attendu. Seul ``title`` est obligatoire ; les colonnes inconnues sont
# ignorées, et l'ordre n'importe pas (la lecture se fait par nom).
CSV_COLUMNS = ["title", "parent", "type", "status", "note", "links"]


class WatchCsvError(BaseModel):
    """Anomalie sur une ligne du CSV (erreur bloquante OU avertissement).

    ``row`` est le numéro de la ligne **de données** (1 = première ligne après
    l'en-tête). ``message`` distingue une ligne ignorée d'un simple
    avertissement.
    """

    row: int
    message: str


class WatchCsvImportResult(BaseModel):
    """Résultat d'un import CSV sous un nœud.

    - ``nodes_created`` / ``links_created`` : volumétrie effectivement créée ;
    - ``anchor_id`` : le nœud sous lequel l'import a été rattaché ;
    - ``error_count`` : nombre d'entrées dans ``errors`` (erreurs + avertissements).
    """

    anchor_id: int
    nodes_created: int
    links_created: int
    error_count: int
    errors: list[WatchCsvError] = Field(default_factory=list)
