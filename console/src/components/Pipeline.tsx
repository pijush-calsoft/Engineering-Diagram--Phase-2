import { Handle, type Node, type NodeProps, Position, ReactFlow } from "@xyflow/react";
import { useMemo } from "react";
import type { BlockInfo, BlockState } from "../types";

// Pipeline map (plan Phase 1 "pipeline map with live block status", §4.3 React Flow), drawn as a
// strip across the top so the drawing gets the width. Names and outputs from plan §2.1.
const BLOCK_META: Record<string, { title: string; output: string }> = {
  b1_parser: { title: "Drawing parser", output: "geometry" },
  b2_interpretation: { title: "Interpretation", output: "design graph" },
  b3_knowledge_graph: { title: "Knowledge graph", output: "similar parts" },
  b4_generation: { title: "Generation", output: "CAD script" },
  b5_opencad: { title: "OpenCAD adapters", output: "STEP" },
  b6_solvers: { title: "Solver connectors", output: "margins" },
  b7_surrogate: { title: "Surrogate", output: "failure envelope" },
  b8_report: { title: "Insight report", output: "report" },
};

const STATE_TEXT: Record<BlockState, string> = {
  waiting: "Waiting",
  running: "Running",
  done: "Done",
  review: "Needs review",
  failed: "Failed",
};

type BlockNodeData = { index: number; info: BlockInfo; state: BlockState; flags: number };
type BlockNode = Node<BlockNodeData, "block">;

function BlockCard({ data }: NodeProps<BlockNode>) {
  const meta = BLOCK_META[data.info.name] ?? { title: data.info.name, output: "" };
  return (
    <div
      className={`block-card state-${data.state}`}
      aria-label={`${data.index}. ${meta.title}: ${STATE_TEXT[data.state]}${data.flags ? `, ${data.flags} flags` : ""}`}
      title={`Produces ${meta.output}${data.info.real ? "" : " (stub: not built yet)"}`}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="block-index">{data.index}</span>
      <span className="block-title">{meta.title}</span>
      <span className="block-state">
        {STATE_TEXT[data.state]}
        {!data.info.real && <span className="block-stub">stub</span>}
        {data.flags > 0 && <span className="block-flags">{data.flags}</span>}
      </span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const nodeTypes = { block: BlockCard };
const COL = 178;

type Props = { blocks: BlockInfo[]; states: Record<string, BlockState>; flags: Record<string, number> };

export function Pipeline({ blocks, states, flags }: Props) {
  const nodes = useMemo<BlockNode[]>(
    () =>
      blocks.map((info, i) => ({
        id: info.name,
        type: "block",
        position: { x: i * COL, y: 0 },
        data: { index: i + 1, info, state: states[info.name] ?? "waiting", flags: flags[info.name] ?? 0 },
        draggable: false,
        selectable: false,
      })),
    [blocks, states, flags],
  );
  const edges = useMemo(
    () =>
      blocks.slice(1).map((b, i) => ({
        id: `${blocks[i].name}-${b.name}`,
        source: blocks[i].name,
        target: b.name,
        className: states[b.name] && states[b.name] !== "waiting" ? "edge-reached" : "",
      })),
    [blocks, states],
  );
  return (
    <nav className="pipeline" aria-label="Pipeline, in run order">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.02 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
      />
    </nav>
  );
}
