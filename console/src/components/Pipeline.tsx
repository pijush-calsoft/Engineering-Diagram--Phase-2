import { Handle, type Node, type NodeProps, Position, ReactFlow } from "@xyflow/react";
import { useMemo } from "react";
import type { BlockInfo, BlockState } from "../types";

// Names and outputs from plan §2.1 and Phases 2 to 6.
const BLOCK_META: Record<string, { title: string; output: string }> = {
  b1_parser: { title: "Drawing parser", output: "geometry" },
  b2_interpretation: { title: "Interpretation", output: "design graph" },
  b3_knowledge_graph: { title: "Knowledge graph", output: "similar parts" },
  b4_generation: { title: "Generation", output: "CAD script" },
  b5_opencad: { title: "OpenCAD adapters", output: "STEP" },
  b6_solvers: { title: "Solver connectors", output: "margins" },
  b7_surrogate: { title: "Surrogate, envelope", output: "failure envelope" },
  b8_report: { title: "Insight report", output: "report" },
};

const STATE_TEXT: Record<BlockState, string> = {
  waiting: "Waiting",
  running: "Running",
  done: "Done",
  review: "Needs review",
  failed: "Failed",
};

type BlockNodeData = { index: number; info: BlockInfo; state: BlockState };
type BlockNode = Node<BlockNodeData, "block">;

function BlockCard({ data }: NodeProps<BlockNode>) {
  const meta = BLOCK_META[data.info.name] ?? { title: data.info.name, output: "" };
  return (
    <div className={`block-card state-${data.state}`} aria-label={`${meta.title}: ${STATE_TEXT[data.state]}`}>
      <Handle type="target" position={Position.Top} isConnectable={false} />
      <span className="block-index">{data.index}</span>
      <div className="block-body">
        <div className="block-title">
          {meta.title}
          {!data.info.real && <span className="block-stub">stub</span>}
        </div>
        <div className="block-output">produces {meta.output}</div>
      </div>
      <span className="block-state">{STATE_TEXT[data.state]}</span>
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}

const nodeTypes = { block: BlockCard };
const ROW = 74;

export function Pipeline({ blocks, states }: { blocks: BlockInfo[]; states: Record<string, BlockState> }) {
  const nodes = useMemo<BlockNode[]>(
    () =>
      blocks.map((info, i) => ({
        id: info.name,
        type: "block",
        position: { x: 0, y: i * ROW },
        data: { index: i + 1, info, state: states[info.name] ?? "waiting" },
        draggable: false,
        selectable: false,
      })),
    [blocks, states],
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
    <div className="pipeline" aria-label="Pipeline, in run order">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.04 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
      />
    </div>
  );
}
