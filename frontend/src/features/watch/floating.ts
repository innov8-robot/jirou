import type { Node } from 'reactflow';

/**
 * Calcule le point d'intersection du bord de `node` avec la droite vers
 * `target` (pour des arêtes « flottantes » qui partent du bord des nœuds,
 * donnant un rendu radial de type mindmap). Adapté de l'exemple officiel
 * React Flow « floating edges ».
 */
function nodeIntersection(node: Node, target: Node) {
  const w = (node.width ?? 120) / 2;
  const h = (node.height ?? 40) / 2;
  const np = node.positionAbsolute ?? node.position;
  const tp = target.positionAbsolute ?? target.position;

  const x2 = np.x + w;
  const y2 = np.y + h;
  const tx = tp.x + (target.width ?? 120) / 2;
  const ty = tp.y + (target.height ?? 40) / 2;

  const xx1 = (tx - x2) / (2 * w) - (ty - y2) / (2 * h);
  const yy1 = (tx - x2) / (2 * w) + (ty - y2) / (2 * h);
  const a = 1 / (Math.abs(xx1) + Math.abs(yy1) || 1);
  const xx3 = a * xx1;
  const yy3 = a * yy1;
  return {
    x: w * (xx3 + yy3) + x2,
    y: h * (-xx3 + yy3) + y2,
  };
}

export function getEdgeParams(source: Node, target: Node) {
  const s = nodeIntersection(source, target);
  const t = nodeIntersection(target, source);
  return { sx: s.x, sy: s.y, tx: t.x, ty: t.y };
}
