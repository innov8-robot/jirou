import { describe, expect, it } from 'vitest';

import type { WatchNodeSummary } from './api';
import {
  CENTER_ID,
  HUB_SIZE,
  descendantIds,
  hubCenter,
  nextRootPosition,
  parentOptions,
  toRf,
} from './graph';

function node(over: Partial<WatchNodeSummary> = {}): WatchNodeSummary {
  return {
    id: 1,
    parent_id: null,
    title: 'Nœud',
    type: 'theme',
    status: null,
    pos_x: 0,
    pos_y: 0,
    media_count: 0,
    comment_count: 0,
    preview: null,
    ...over,
  };
}

/** Centre visuel du hub dans le graphe produit (position + demi-côté). */
function renderedHubCenter(summaries: WatchNodeSummary[]) {
  const hub = toRf(summaries).nodes.find((n) => n.id === CENTER_ID)!;
  return {
    x: hub.position.x + HUB_SIZE / 2,
    y: hub.position.y + HUB_SIZE / 2,
  };
}

describe('hubCenter', () => {
  it('se place au barycentre des thèmes racines', () => {
    const center = hubCenter([
      node({ id: 1, pos_x: 0, pos_y: 0 }),
      node({ id: 2, pos_x: 100, pos_y: 200 }),
    ]);
    expect(center).toEqual({ x: 50, y: 100 });
  });

  it('ignore les enfants dans le calcul', () => {
    const center = hubCenter([
      node({ id: 1, pos_x: 0, pos_y: 0 }),
      node({ id: 2, parent_id: 1, pos_x: 3000, pos_y: 3000 }),
    ]);
    expect(center).toEqual({ x: 0, y: 0 });
  });

  it('retombe sur tous les nœuds quand aucun n’est racine', () => {
    const center = hubCenter([
      node({ id: 2, parent_id: 99, pos_x: 10, pos_y: 20 }),
      node({ id: 3, parent_id: 99, pos_x: 30, pos_y: 40 }),
    ]);
    expect(center).toEqual({ x: 20, y: 30 });
  });

  it('retombe sur l’origine sur un graphe vide', () => {
    expect(hubCenter([])).toEqual({ x: 0, y: 0 });
  });
});

describe('toRf', () => {
  it('inclut toujours le hub, même sans aucun nœud', () => {
    const { nodes } = toRf([]);
    expect(nodes.map((n) => n.id)).toEqual([CENTER_ID]);
    expect(nodes[0].data).toEqual({ label: 'Veille' });
  });

  it('rend le hub non déplaçable, non sélectionnable, non supprimable', () => {
    const hub = toRf([]).nodes[0];
    expect(hub.draggable).toBe(false);
    expect(hub.selectable).toBe(false);
    expect(hub.deletable).toBe(false);
  });

  it('centre visuellement le hub sur le barycentre', () => {
    const summaries = [
      node({ id: 1, pos_x: 0, pos_y: 0 }),
      node({ id: 2, pos_x: 200, pos_y: 100 }),
    ];
    expect(renderedHubCenter(summaries)).toEqual({ x: 100, y: 50 });
  });

  it('rattache les racines au hub et les enfants à leur parent', () => {
    const { edges } = toRf([
      node({ id: 1 }),
      node({ id: 2, parent_id: 1 }),
    ]);
    expect(edges).toEqual([
      { id: 'e-center-1', source: CENTER_ID, target: '1', type: 'floating' },
      { id: 'e-1-2', source: '1', target: '2', type: 'floating' },
    ]);
  });

  it('garde le hub dans le cadrage d’un graphe très étalé', () => {
    // Régression : le hub était figé à (360, 320) alors que le graphe réel
    // s'étend sur des milliers de pixels. `fitView` cadrant tous les nœuds, le
    // hub sortait de l'écran — il disparaissait à chaque rechargement.
    const summaries = [
      node({ id: 1, pos_x: -83, pos_y: -408 }),
      node({ id: 2, pos_x: 3045, pos_y: 1759 }),
      node({ id: 3, parent_id: 1, pos_x: 1500, pos_y: 900 }),
    ];
    const { nodes } = toRf(summaries);
    const xs = nodes.map((n) => n.position.x);
    const ys = nodes.map((n) => n.position.y);
    const hub = renderedHubCenter(summaries);

    // Le hub est strictement à l'intérieur de la boîte englobante, donc visible
    // dès que celle-ci est cadrée.
    expect(hub.x).toBeGreaterThan(Math.min(...xs));
    expect(hub.x).toBeLessThan(Math.max(...xs));
    expect(hub.y).toBeGreaterThan(Math.min(...ys));
    expect(hub.y).toBeLessThan(Math.max(...ys));
  });
});

describe('descendantIds', () => {
  const tree = [
    node({ id: 1 }),
    node({ id: 2, parent_id: 1 }),
    node({ id: 3, parent_id: 2 }),
    node({ id: 4, parent_id: 1 }),
    node({ id: 5 }),
  ];

  it('remonte toute la descendance, pas seulement les enfants directs', () => {
    expect(descendantIds(tree, 1)).toEqual(new Set([2, 3, 4]));
  });

  it('renvoie un ensemble vide pour une feuille', () => {
    expect(descendantIds(tree, 3)).toEqual(new Set());
  });

  it('ne boucle pas sur des données cycliques', () => {
    // Incohérence défensive : 1 → 2 → 1. Le parcours doit s'arrêter.
    const cyclic = [node({ id: 1, parent_id: 2 }), node({ id: 2, parent_id: 1 })];
    expect(descendantIds(cyclic, 1)).toEqual(new Set([2, 1]));
  });
});

describe('parentOptions', () => {
  const tree = [
    node({ id: 1, title: 'Racine' }),
    node({ id: 2, parent_id: 1, title: 'Enfant' }),
    node({ id: 3, parent_id: 2, title: 'Petit-enfant' }),
    node({ id: 4, title: 'Autre racine' }),
  ];

  it('exclut le nœud lui-même et sa descendance', () => {
    // Rattacher 1 sous 2 ou 3 créerait un cycle : l'API le refuserait (422).
    expect(parentOptions(tree, 1).map((s) => s.id)).toEqual([4]);
  });

  it('autorise un parent qui n’est pas un descendant', () => {
    expect(parentOptions(tree, 4).map((s) => s.id).sort()).toEqual([1, 2, 3]);
  });

  it('trie par titre', () => {
    expect(parentOptions(tree, 3).map((s) => s.title)).toEqual([
      'Autre racine',
      'Enfant',
      'Racine',
    ]);
  });

  it('ne propose rien quand le nœud est seul', () => {
    expect(parentOptions([node({ id: 1 })], 1)).toEqual([]);
  });
});

describe('nextRootPosition', () => {
  it('place le premier thème à distance du hub', () => {
    const { pos_x, pos_y } = nextRootPosition([]);
    // Rayon 320 autour de l'origine (graphe vide).
    expect(Math.hypot(pos_x, pos_y)).toBeCloseTo(320, 0);
  });

  it('tourne autour du hub à mesure que les racines s’ajoutent', () => {
    const first = nextRootPosition([]);
    const second = nextRootPosition([node({ id: 1, ...{ pos_x: 0, pos_y: 0 } })]);
    expect(second).not.toEqual(first);
  });

  it('suit le hub quand le graphe est décalé', () => {
    // Racines centrées sur (1000, 1000) : le nouveau thème doit naître autour de
    // ce point, pas autour d'une constante oubliée.
    const summaries = [
      node({ id: 1, pos_x: 800, pos_y: 1000 }),
      node({ id: 2, pos_x: 1200, pos_y: 1000 }),
    ];
    const { pos_x, pos_y } = nextRootPosition(summaries);
    expect(Math.hypot(pos_x - 1000, pos_y - 1000)).toBeCloseTo(320, 0);
  });
});
