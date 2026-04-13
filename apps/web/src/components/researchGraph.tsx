import type { GraphPayload } from "../lib/types";

type ResearchGraphProps = {
  graph: GraphPayload;
};

type PositionedNode = {
  id: string;
  label: string;
  x: number;
  y: number;
};

const RELATIONSHIP_CLASS: Record<string, string> = {
  supports: "supports",
  contradicts: "contradicts",
  extends: "extends",
  qualifies: "qualifies",
};

function buildPositions(graph: GraphPayload): PositionedNode[] {
  const centerX = 340;
  const centerY = 220;
  const radius = 145;

  if (graph.nodes.length === 0) {
    return [];
  }

  return graph.nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / graph.nodes.length - Math.PI / 2;
    return {
      ...node,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });
}

function labelForNode(label: string) {
  return label.length > 30 ? `${label.slice(0, 30)}…` : label;
}

export function ResearchGraph({ graph }: ResearchGraphProps) {
  const nodes = buildPositions(graph);
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));

  return (
    <div className="graph-canvas">
      <svg
        className="graph-svg"
        viewBox="0 0 680 440"
        role="img"
        aria-label="Research graph"
      >
        {graph.edges.map((edge) => {
          const source = nodeMap.get(edge.source);
          const target = nodeMap.get(edge.target);

          if (!source || !target) {
            return null;
          }

          const relationshipClass =
            edge.status === "pending"
              ? "pending"
              : RELATIONSHIP_CLASS[edge.relationship_type] || "supports";

          return (
            <line
              key={edge.id}
              className={`graph-edge-line graph-edge-line--${relationshipClass}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              strokeWidth={Math.max(4, edge.visible_strength)}
            />
          );
        })}

        {nodes.map((node) => (
          <g key={node.id} className="graph-node-group">
            <circle className="graph-node-circle" cx={node.x} cy={node.y} r="32" />
            <text className="graph-node-text" x={node.x} y={node.y + 5} textAnchor="middle">
              {node.id.split("-").at(-1)}
            </text>
            <text className="graph-node-label" x={node.x} y={node.y + 58} textAnchor="middle">
              {labelForNode(node.label)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
