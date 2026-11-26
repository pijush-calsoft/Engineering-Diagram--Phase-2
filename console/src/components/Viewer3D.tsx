import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { api } from "../api";
import type { Mesh, Solid } from "../types";

// 3D viewer (plan Phase 6 console: "3D viewer"). Draws the model the parser read, with its
// edges, and marks each hole the parser found with a ring on its axis. Faces named by the
// selected value's locators (STEP entity ids) are highlighted.

const INK = 0x1f2b33;
const BODY = 0xdfe5e6;
const TRACE = 0x147a93;
const PEAK = 0xc62b35; // redline

type Props = {
  runId: string;
  solids: Solid[];
  traced: Set<string>;
  units: string | null;
  // "input": the uploaded STEP/IGES/STL; "model": the model block 5 generated from the drawing.
  source?: "input" | "model";
  // Peak stress point from block 6, in model millimetres, marked in red.
  peak?: [number, number, number] | null;
};

export function Viewer3D({ runId, solids, traced, units, source = "input", peak = null }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [mesh, setMesh] = useState<Mesh | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [edges, setEdges] = useState(true);
  const [holes, setHoles] = useState(true);
  const fit = useRef<() => void>(() => undefined);

  useEffect(() => {
    setMesh(null);
    setError(null);
    (source === "model" ? api.model(runId) : api.mesh(runId)).then(setMesh).catch((e) => setError((e as Error).message));
  }, [runId, source]);

  useEffect(() => {
    const el = host.current;
    if (!el || !mesh) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0xfbfcfb);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 1e7);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a979e, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    scene.add(sun);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(mesh.positions, 3));
    geo.setIndex(mesh.indices);
    geo.computeVertexNormals();
    // Faces whose entity id is traced get the trace material (geometry groups per face range).
    const ranges = mesh.faces.length ? mesh.faces : [{ handle: null, start: 0, count: mesh.indices.length / 3 }];
    for (const f of ranges) geo.addGroup(f.start * 3, f.count * 3, f.handle && traced.has(f.handle) ? 1 : 0);
    const materials = [
      new THREE.MeshStandardMaterial({ color: BODY, roughness: 0.75, metalness: 0.05, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }),
      new THREE.MeshStandardMaterial({ color: TRACE, roughness: 0.5, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }),
    ];
    const body = new THREE.Mesh(geo, materials);
    scene.add(body);
    const lines = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), new THREE.LineBasicMaterial({ color: INK }));
    lines.visible = edges;
    scene.add(lines);

    const [x0, y0, z0, x1, y1, z1] = mesh.bbox;
    const centre = new THREE.Vector3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    const size = Math.max(x1 - x0, y1 - y0, z1 - z0) || 1;

    const rings = new THREE.Group();
    for (const s of solids) {
      for (const h of s.holes) {
        // The hole's axis through the part's bounding box, with a ring of the hole's diameter at each end.
        const dir = new THREE.Vector3(...h.axis_direction).normalize();
        const o = new THREE.Vector3(...h.axis_origin);
        const mid = o.clone().add(dir.clone().multiplyScalar(dir.dot(centre.clone().sub(o))));
        const half = (Math.abs(dir.x) * (x1 - x0) + Math.abs(dir.y) * (y1 - y0) + Math.abs(dir.z) * (z1 - z0)) / 2 + size * 0.01;
        const ends = [-1, 1].map((sgn) => mid.clone().add(dir.clone().multiplyScalar(sgn * half)));
        for (const end of ends) {
          const ring = new THREE.Mesh(
            new THREE.TorusGeometry(h.diameter / 2, size * 0.004, 8, 48),
            new THREE.MeshBasicMaterial({ color: TRACE }),
          );
          ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir);
          ring.position.copy(end);
          rings.add(ring);
        }
        const axis = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(ends),
          new THREE.LineDashedMaterial({ color: TRACE, dashSize: size * 0.03, gapSize: size * 0.02 }),
        );
        axis.computeLineDistances();
        rings.add(axis);
      }
    }
    rings.visible = holes;
    scene.add(rings);
    if (peak) {
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(size * 0.012, 24, 16),
        new THREE.MeshBasicMaterial({ color: PEAK, depthTest: false }),
      );
      marker.position.set(...peak);
      marker.renderOrder = 2;
      scene.add(marker);
    }

    fit.current = () => {
      const dist = size * 2.2;
      camera.position.copy(centre).add(new THREE.Vector3(dist * 0.8, -dist * 1.1, dist * 0.9));
      camera.up.set(0, 0, 1);
      controls.target.copy(centre);
      sun.position.copy(camera.position);
      controls.update();
    };
    fit.current();

    const resize = () => {
      const w = el.clientWidth || 1;
      const hgt = el.clientHeight || 1;
      renderer.setSize(w, hgt);
      camera.aspect = w / hgt;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    resize();
    let frame = 0;
    const loop = () => {
      controls.update();
      sun.position.copy(camera.position);
      renderer.render(scene, camera);
      frame = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      geo.dispose();
      materials.forEach((m) => m.dispose());
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [mesh, solids, traced, edges, holes, peak]);

  const nHoles = solids.reduce((n, s) => n + s.holes.length, 0);
  return (
    <div className="workspace-pane">
      <div className="ws-toolbar" role="toolbar" aria-label="3D view">
        <div className="ws-zoom">
          <button className="tool" onClick={() => fit.current()}>
            Fit
          </button>
        </div>
        <div className="ws-layers" aria-label="Layers">
          <button className="layer" aria-pressed={edges} onClick={() => setEdges((v) => !v)}>
            Edges
          </button>
          <button className="layer" aria-pressed={holes} onClick={() => setHoles((v) => !v)} disabled={nHoles === 0}>
            Hole axes<span className="layer-count">{nHoles}</span>
          </button>
        </div>
      </div>
      <div
        className="ws-canvas viewer3d"
        ref={host}
        aria-label={`${source === "model" ? "3D model generated from the drawing" : "3D model as read by the parser"}. Drag to orbit, scroll to zoom, right-drag to pan.`}
      >
        {!mesh && !error && <p className="ws-readout">Loading the model…</p>}
        {error && <p className="ws-readout error-text">The model could not be drawn: {error}</p>}
        {mesh && (
          <p className="ws-readout">
            {source === "model" ? "Generated model. " : ""}
            {mesh.indices.length / 3} triangles, {mesh.faces.length || "no"} named faces{units ? `, ${units}` : ""}.
            {peak ? " Red dot: peak stress." : ""} Drag to orbit, scroll to zoom, right-drag to pan.
          </p>
        )}
      </div>
    </div>
  );
}
