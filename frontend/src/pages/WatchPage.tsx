import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ReactFlow, {
  Background,
  Controls,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Connection,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Download, Network, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';
import { WatchGraphNode } from '@/features/watch/WatchGraphNode';
import { WatchCenterNode } from '@/features/watch/WatchCenterNode';
import { FloatingEdge } from '@/features/watch/FloatingEdge';
import { WatchNodePanel } from '@/features/watch/WatchNodePanel';
import {
  createNode,
  exportWatchArchive,
  fetchNodes,
  updateNode,
  type WatchNodeType,
} from '@/features/watch/api';
import {
  CENTER_ID,
  nextRootPosition,
  toRf,
} from '@/features/watch/graph';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const NODE_TYPES = { watch: WatchGraphNode, center: WatchCenterNode };
const EDGE_TYPES = { floating: FloatingEdge };
function WatchInner() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: summaries = [], isLoading } = useQuery({
    queryKey: queryKeys.watch.nodes,
    queryFn: fetchNodes,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges] = useEdgesState([]);

  // Reconstruit le graphe quand la structure change (hors drag local).
  useEffect(() => {
    const { nodes: n, edges: e } = toRf(summaries);
    setNodes(n);
    setEdges(e);
  }, [summaries, setNodes, setEdges]);

  const posMut = useMutation({
    mutationFn: (v: { id: number; pos_x: number; pos_y: number }) =>
      updateNode(v.id, { pos_x: v.pos_x, pos_y: v.pos_y }),
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const reparentMut = useMutation({
    mutationFn: (v: { id: number; parent_id: number }) =>
      updateNode(v.id, { parent_id: v.parent_id }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes }),
    onError: (err) => toast.error('Lien impossible', getErrorMessage(err)),
  });
  const createMut = useMutation({
    mutationFn: (v: {
      title: string;
      type?: WatchNodeType;
      parent_id?: number | null;
      pos_x: number;
      pos_y: number;
    }) => createNode(v),
    onSuccess: (node) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes });
      setSelectedId(node.id);
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const exportMut = useMutation({
    mutationFn: exportWatchArchive,
    onSuccess: (filename) => toast.success('Export prêt', filename),
    onError: () =>
      toast.error('Export échoué', "L'archive n'a pas pu être générée."),
  });

  function addRoot() {
    // Dispose les thèmes racines en cercle autour du hub, dont la position suit
    // le barycentre du graphe (cf. features/watch/graph.ts).
    createMut.mutate({
      title: 'Nouveau thème',
      type: 'theme',
      parent_id: null,
      ...nextRootPosition(summaries),
    });
  }

  function addChild(parentId: number) {
    const parent = summaries.find((s) => s.id === parentId);
    createMut.mutate({
      title: 'Nouveau nœud',
      type: 'solution',
      parent_id: parentId,
      pos_x: (parent?.pos_x ?? 0) + Math.round(Math.random() * 80 - 40),
      pos_y: (parent?.pos_y ?? 0) + 140,
    });
  }

  function onConnect(conn: Connection) {
    if (conn.source && conn.target && conn.source !== conn.target) {
      reparentMut.mutate({
        id: Number(conn.target),
        parent_id: Number(conn.source),
      });
    }
  }

  const empty = summaries.length === 0;

  const displayNodes = useMemo(
    () => nodes.map((n) => ({ ...n, selected: Number(n.id) === selectedId })),
    [nodes, selectedId]
  );

  return (
    <div className="flex h-full">
      <div className="relative flex-1">
        <div className="absolute left-3 top-3 z-10 flex flex-wrap gap-2">
          <Button size="sm" onClick={addRoot} disabled={createMut.isPending}>
            <Plus className="h-4 w-4" />
            Nouveau thème
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportMut.mutate()}
            disabled={exportMut.isPending}
            title="Sauvegarder toute la veille (arbre, notes, liens, fichiers)"
          >
            <Download className="h-4 w-4" />
            {exportMut.isPending ? 'Export…' : 'Exporter'}
          </Button>
        </div>

        {isLoading ? (
          // On ne monte pas React Flow avant d'avoir les nœuds. Son `fitView`
          // est à un seul coup : il se déclenche à la première mesure de
          // dimensions et se marque « fait » définitivement (cf. son
          // updateNodeDimensions). Monté pendant le chargement, il se cadrerait
          // sur le seul hub, puis les vrais nœuds arriveraient sans recadrage —
          // c'est ce qui faisait « disparaître » le hub après un rechargement,
          // alors qu'un changement d'onglet (données en cache) allait bien.
          <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
            Chargement de la veille…
          </div>
        ) : empty ? (
          <div className="flex h-full items-center justify-center p-6">
            <EmptyState
              icon={Network}
              title="Aucun nœud"
              description="Créez un premier thème (ex. Mocap suit, Téléopération) pour démarrer votre veille."
              actionLabel="Nouveau thème"
              onAction={addRoot}
            />
          </div>
        ) : (
          <ReactFlow
            nodes={displayNodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            onNodesChange={onNodesChange}
            onNodeDragStop={(_, node) => {
              if (node.id === CENTER_ID) return;
              posMut.mutate({
                id: Number(node.id),
                pos_x: Math.round(node.position.x),
                pos_y: Math.round(node.position.y),
              });
            }}
            onConnect={onConnect}
            onNodeClick={(_, node) => {
              if (node.id !== CENTER_ID) setSelectedId(Number(node.id));
            }}
            onPaneClick={() => setSelectedId(null)}
            fitView
            // Défaut React Flow : 0.5, trop haut pour cadrer un graphe qui
            // s'étale sur plusieurs milliers de pixels.
            minZoom={0.2}
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls />
          </ReactFlow>
        )}
      </div>

      {selectedId !== null && (
        <WatchNodePanel
          nodeId={selectedId}
          onClose={() => setSelectedId(null)}
          onDeleted={() => setSelectedId(null)}
          onAddChild={addChild}
        />
      )}
    </div>
  );
}

export default function WatchPage() {
  return (
    <ReactFlowProvider>
      <WatchInner />
    </ReactFlowProvider>
  );
}
