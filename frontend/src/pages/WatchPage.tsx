import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ReactFlow, {
  Background,
  Controls,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Download, Network, Plus, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';
import { WatchGraphNode } from '@/features/watch/WatchGraphNode';
import { WatchCenterNode } from '@/features/watch/WatchCenterNode';
import { FloatingEdge } from '@/features/watch/FloatingEdge';
import { WatchNodePanel } from '@/features/watch/WatchNodePanel';
import { WatchImportDialog } from '@/features/watch/WatchImportDialog';
import {
  createNode,
  exportWatchArchive,
  fetchNodes,
  updateNode,
  type WatchNodeSummary,
  type WatchNodeType,
} from '@/features/watch/api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const NODE_TYPES = { watch: WatchGraphNode, center: WatchCenterNode };
const EDGE_TYPES = { floating: FloatingEdge };
const CENTER_ID = 'center';
const CENTER_POS = { x: 360, y: 320 };

function toRf(summaries: WatchNodeSummary[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    {
      id: CENTER_ID,
      type: 'center',
      position: CENTER_POS,
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

function WatchInner() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);

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
    // Dispose les thèmes racines en cercle autour du hub central (mindmap).
    const rootCount = summaries.filter((s) => s.parent_id == null).length;
    const angle = rootCount * ((Math.PI * 2) / 6) + 0.5;
    const radius = 320;
    createMut.mutate({
      title: 'Nouveau thème',
      type: 'theme',
      parent_id: null,
      pos_x: Math.round(CENTER_POS.x + Math.cos(angle) * radius),
      pos_y: Math.round(CENTER_POS.y + Math.sin(angle) * radius),
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

  const empty = !isLoading && summaries.length === 0;

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
            title="Télécharger toute la veille (arbre, notes, liens, fichiers)"
          >
            <Download className="h-4 w-4" />
            {exportMut.isPending ? 'Export…' : 'Exporter'}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4" />
            Importer
          </Button>
        </div>

        {empty ? (
          <div className="flex h-full items-center justify-center p-6">
            <EmptyState
              icon={Network}
              title="Aucun nœud"
              description="Créez un premier thème (ex. Mocap suit, Téléopération) pour démarrer votre veille, ou importez une archive existante."
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

      <WatchImportDialog open={importOpen} onOpenChange={setImportOpen} />
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
