import type { Edge, Node } from 'reactflow';

import type { WatchNodeSummary } from './api';

/** Identifiant du hub central. Synthétique : ce nœud n'existe pas en base. */
export const CENTER_ID = 'center';

/** Côté du hub en pixels — doit suivre le `h-28 w-28` de `WatchCenterNode`. */
export const HUB_SIZE = 112;

/** Rayon de placement des nouveaux thèmes autour du hub. */
export const ROOT_RADIUS = 320;

/**
 * Centre du hub : le barycentre des thèmes racines.
 *
 * Le hub était auparavant figé à une position constante. Les nœuds, eux, ont
 * une position **persistée** que l'on déplace librement : au fil du temps le
 * graphe dérive (en production il s'étend de x=-83 à x=3045) et le hub se
 * retrouve loin de tout. `fitView` cadrant l'ensemble des nœuds, le hub tombait
 * alors hors de l'écran — il « disparaissait » à chaque rechargement de page,
 * puisque le rechargement remet la vue à ce cadrage.
 *
 * En le calculant depuis le graphe, le hub est toujours au milieu de sa
 * constellation : il est donc nécessairement dans le cadrage, et c'est aussi sa
 * place logique puisque les arêtes des racines en rayonnent.
 *
 * Replis successifs : les racines, sinon tous les nœuds, sinon l'origine.
 */
export function hubCenter(summaries: WatchNodeSummary[]): { x: number; y: number } {
  const roots = summaries.filter((s) => s.parent_id == null);
  const base = roots.length > 0 ? roots : summaries;
  if (base.length === 0) return { x: 0, y: 0 };
  return {
    x: base.reduce((sum, s) => sum + s.pos_x, 0) / base.length,
    y: base.reduce((sum, s) => sum + s.pos_y, 0) / base.length,
  };
}

/** Position d'un nouveau thème racine, réparti en cercle autour du hub. */
export function nextRootPosition(
  summaries: WatchNodeSummary[]
): { pos_x: number; pos_y: number } {
  const center = hubCenter(summaries);
  const rootCount = summaries.filter((s) => s.parent_id == null).length;
  const angle = rootCount * ((Math.PI * 2) / 6) + 0.5;
  return {
    pos_x: Math.round(center.x + Math.cos(angle) * ROOT_RADIUS),
    pos_y: Math.round(center.y + Math.sin(angle) * ROOT_RADIUS),
  };
}

/**
 * Identifiants des descendants d'un nœud (parcours en largeur, arbre à plat).
 *
 * Tolère les données incohérentes : un cycle éventuel dans `parent_id` ne fait
 * pas boucler le parcours, grâce au marquage des nœuds déjà vus.
 */
export function descendantIds(
  summaries: WatchNodeSummary[],
  id: number
): Set<number> {
  const childrenOf = new Map<number, number[]>();
  for (const s of summaries) {
    if (s.parent_id == null) continue;
    const siblings = childrenOf.get(s.parent_id);
    if (siblings) siblings.push(s.id);
    else childrenOf.set(s.parent_id, [s.id]);
  }

  const seen = new Set<number>();
  let frontier = childrenOf.get(id) ?? [];
  while (frontier.length > 0) {
    const next: number[] = [];
    for (const child of frontier) {
      if (seen.has(child)) continue;
      seen.add(child);
      next.push(...(childrenOf.get(child) ?? []));
    }
    frontier = next;
  }
  return seen;
}

/**
 * Nœuds pouvant devenir le parent de `id`, triés par titre.
 *
 * Exclut le nœud lui-même et ses descendants : les proposer garantirait un 422
 * (l'API refuse les cycles), autant ne pas les offrir.
 */
export function parentOptions(
  summaries: WatchNodeSummary[],
  id: number
): WatchNodeSummary[] {
  const forbidden = descendantIds(summaries, id);
  return summaries
    .filter((s) => s.id !== id && !forbidden.has(s.id))
    .sort((a, b) => a.title.localeCompare(b.title, 'fr'));
}

/**
 * Convertit les nœuds de l'API en graphe React Flow.
 *
 * Le hub est **toujours** présent, y compris quand la liste est vide : c'est le
 * point de départ visuel de la carte.
 */
export function toRf(summaries: WatchNodeSummary[]): { nodes: Node[]; edges: Edge[] } {
  const center = hubCenter(summaries);
  const nodes: Node[] = [
    {
      id: CENTER_ID,
      type: 'center',
      // `position` est le coin haut-gauche : on décale d'un demi-côté pour que
      // le hub soit visuellement centré sur le barycentre.
      position: { x: center.x - HUB_SIZE / 2, y: center.y - HUB_SIZE / 2 },
      data: { label: 'Veille' },
      draggable: false,
      selectable: false,
      deletable: false,
    },
    ...summaries.map((s) => ({
      id: String(s.id),
      type: 'watch',
      position: { x: s.pos_x, y: s.pos_y },
      data: {
        title: s.title,
        type: s.type,
        status: s.status,
        media_count: s.media_count,
        comment_count: s.comment_count,
        preview: s.preview,
      },
    })),
  ];
  // Chaque nœud a une arête entrante : depuis son parent, ou depuis le hub
  // central pour les thèmes racines. Arêtes flottantes (rendu radial).
  const edges: Edge[] = summaries.map((s) => ({
    id: `e-${s.parent_id ?? CENTER_ID}-${s.id}`,
    source: s.parent_id != null ? String(s.parent_id) : CENTER_ID,
    target: String(s.id),
    type: 'floating',
  }));
  return { nodes, edges };
}
