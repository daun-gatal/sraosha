import type { GraphEdge, GraphNode } from "../api/client";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (nodeId: string) => void;
}

export default function ImpactGraph({ nodes, edges, onNodeClick }: Props) {
  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border border-dashed border-gray-300">
        <p className="text-gray-500">No contracts registered. Add contracts to see the dependency graph.</p>
      </div>
    );
  }

  const width = 800;
  const height = 500;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) / 3;

  const positions = nodes.map((_, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  });

  const nodeIndex = new Map(nodes.map((n, i) => [n.id, i]));

  const statusColor: Record<string, string> = {
    active: "#22c55e",
    passing: "#22c55e",
    warning: "#f59e0b",
    failing: "#ef4444",
    inactive: "#9ca3af",
    unknown: "#6b7280",
  };

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full border rounded-lg bg-white">
      {edges.map((e, i) => {
        const si = nodeIndex.get(e.source);
        const ti = nodeIndex.get(e.target);
        if (si === undefined || ti === undefined) return null;
        return (
          <line
            key={i}
            x1={positions[si].x}
            y1={positions[si].y}
            x2={positions[ti].x}
            y2={positions[ti].y}
            stroke="#d1d5db"
            strokeWidth={2}
            markerEnd="url(#arrow)"
          />
        );
      })}
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
        </marker>
      </defs>
      {nodes.map((node, i) => (
        <g
          key={node.id}
          transform={`translate(${positions[i].x}, ${positions[i].y})`}
          onClick={() => onNodeClick?.(node.id)}
          className="cursor-pointer"
        >
          <circle r={18} fill={statusColor[node.status] ?? statusColor.unknown} opacity={0.9} />
          <text y={32} textAnchor="middle" className="text-xs fill-gray-700 font-medium">
            {node.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
