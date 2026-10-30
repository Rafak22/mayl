import { useMemo } from "react";
import { Background, BackgroundVariant, Controls, MarkerType, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AGENTS, ROLES } from "../agents";

const OWNER_SHORT = { lead: "Lead", ds: "DS", engineer: "Eng", domain: "Expert" };
const KIND = { objective: "Objective", requirement: "Rule", dataset: "Dataset", pipeline: "Pipeline", engine: "Engine" };

// The project graph on a dark dotted canvas. Pending nodes are amber; nodes in the open card glow.
export function ProjectMap({ product, highlight, onSelect }) {
  const hl = useMemo(() => new Set(highlight || []), [highlight]);
  const pending = useMemo(() => new Set(product.nodes.filter((n) => n.status === "pending").map((n) => n.id)), [product.nodes]);
  const hot = (id) => pending.has(id) || hl.has(id);
  // On a phone, fitting the whole graph makes labels unreadable: start zoomed in and let people pan.
  const narrow = typeof window !== "undefined" && window.innerWidth < 700;

  const nodes = product.nodes.map((n) => ({
    id: n.id,
    position: { x: n.position.x * 0.62, y: n.position.y * 0.8 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    className: `mnode st-${n.status}${hl.has(n.id) ? " hl" : ""}`,
    style: { "--c": AGENTS[n.owner].mapColor },
    data: {
      label: (
        <div className="mnode-box">
          <span className="mnode-kind">{KIND[n.kind] || n.kind} · {OWNER_SHORT[n.owner]}</span>
          <strong>{n.label}</strong>
          {n.status !== "ok" && <span className="mnode-status">{n.status}</span>}
        </div>
      ),
    },
  }));
  const edges = product.edges.map((e, i) => {
    const lit = hot(e.source) && hot(e.target);
    const constrains = e.kind === "constrains";
    const color = lit ? "#E7A548" : constrains ? "#56627F" : "#3A4664";
    return {
      id: `e${i}`, source: e.source, target: e.target, animated: lit && hl.size > 0,
      style: { stroke: color, strokeWidth: lit ? 2 : 1.5, strokeDasharray: constrains ? "5 4" : undefined },
      label: constrains ? "constrains" : undefined,
      labelStyle: { fill: "#AEB8D0", fontSize: 9 },
      labelBgStyle: { fill: "#172036" },
      markerEnd: { type: MarkerType.ArrowClosed, color },
    };
  });

  return (
    <section className="map" aria-label="Project map">
      <div className="map-legend">
        <span className="map-title">Project map</span>
        {ROLES.map((r) => <span key={r.id} className="lg"><i style={{ background: AGENTS[r.id].mapColor }} />{r.name}</span>)}
        <span className="map-hint">Tap a node to propose a change{narrow ? " · drag to see more" : ""}</span>
      </div>
      <div className="map-canvas">
        <ReactFlow key={product.id + product.nodes.length} nodes={nodes} edges={edges} fitView
          fitViewOptions={{ padding: 0.12, minZoom: narrow ? 0.7 : 0.3 }} minZoom={0.3} proOptions={{ hideAttribution: true }}
          nodesDraggable={false} nodesConnectable={false} colorMode="dark"
          onNodeClick={(_, n) => onSelect(product.nodes.find((x) => x.id === n.id))}>
          <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} color="#26304A" bgColor="#0F1626" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  );
}
