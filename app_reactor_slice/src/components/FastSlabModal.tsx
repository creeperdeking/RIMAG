import React, { useEffect, useState } from "react";
import { Alert, Button, Form, Modal } from "react-bootstrap";
import type { Setup, SimulationParams } from "../configurations";
import { slabLayersFromSetup, type SlabLayerSpec, type SlabRole } from "../slabShield";

type Props = {
  show: boolean;
  setup: Setup;
  params: SimulationParams;
  saving: boolean;
  error: string | null;
  onHide: () => void;
  onAppend: (simulation: SimulationParams) => void;
};

const COLORS: Record<SlabRole, string> = {
  reflector: "#0f766e",
  moderator: "#64748b",
  absorber: "#334155",
  detector: "#dbeafe",
};

const ROLE_LABEL: Record<SlabRole, string> = {
  reflector: "reflector",
  moderator: "moderator",
  absorber: "absorber",
  detector: "score",
};

function formatLength(cm: number): string {
  if (cm >= 100) {
    const metres = cm / 100;
    return `${metres.toFixed(metres >= 10 ? 1 : 2)} m`;
  }
  if (cm >= 10) return `${cm.toFixed(1)} cm`;
  return `${cm.toFixed(2)} cm`;
}

function clampInt(value: number, low: number, high: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(high, Math.max(low, Math.round(value)));
}

/** Rightmost `windowCm` of the stack, splitting the layer that the window cuts. */
function tailLayers(layers: SlabLayerSpec[], windowCm: number): SlabLayerSpec[] {
  const total = layers.reduce((sum, layer) => sum + layer.cm, 0);
  let skip = Math.max(0, total - windowCm);
  const shown: SlabLayerSpec[] = [];
  for (const layer of layers) {
    if (skip >= layer.cm - 1e-9) {
      skip -= layer.cm;
      continue;
    }
    shown.push({ ...layer, cm: layer.cm - skip });
    skip = 0;
  }
  return shown;
}

function SlabBar({
  layers,
  y,
  label,
}: {
  layers: SlabLayerSpec[];
  y: number;
  label: string;
}) {
  const total = layers.reduce((sum, layer) => sum + layer.cm, 0);
  const x0 = 8;
  const width = 664;
  const height = 56;
  let cursor = x0;
  return (
    <g>
      <text x={x0} y={y - 8} fill="#475569" fontSize="12">
        {label}
      </text>
      {layers.map((layer, index) => {
        const span = total > 0 ? (layer.cm / total) * width : 0;
        const x = cursor;
        cursor += span;
        const ink = layer.role === "detector" ? "#0f172a" : "#f8fafc";
        const showText = span >= 56;
        return (
          <g key={`${layer.role}-${index}`}>
            <rect
              x={x}
              y={y}
              width={Math.max(span, 0.5)}
              height={height}
              fill={COLORS[layer.role]}
              stroke="#0f172a"
              strokeWidth={layer.role === "detector" ? 1 : 0.4}
            />
            {showText && (
              <text x={x + span / 2} y={y + 24} textAnchor="middle" fill={ink} fontSize="12">
                {layer.role === "detector" ? "score" : layer.name}
              </text>
            )}
            {showText && (
              <text x={x + span / 2} y={y + 42} textAnchor="middle" fill={ink} fontSize="11">
                {formatLength(layer.cm)}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

const FastSlabModal: React.FC<Props> = ({ show, setup, params, saving, error, onHide, onAppend }) => {
  const [particles, setParticles] = useState(8000);
  const [batches, setBatches] = useState(8);
  const [threads, setThreads] = useState(8);
  const layers = slabLayersFromSetup({ ...setup, simulation: params });
  const solids = layers.filter((layer) => layer.role !== "detector");
  const totalCm = layers.reduce((sum, layer) => sum + layer.cm, 0);
  const enlarged = totalCm > 40 ? tailLayers(layers, 40) : null;

  useEffect(() => {
    if (!show) return;
    setParticles(8000);
    setBatches(8);
    setThreads(8);
  }, [show]);

  const append = () => {
    onAppend({
      ...params,
      run_mode: "slab",
      n_batches: clampInt(batches, 1, 500, 8),
      n_threads: clampInt(threads, 1, 256, 8),
      weight_windows: "no",
      slab_particles: clampInt(particles, 100, 1_000_000, 8000),
      slab_layers: layers,
    });
  };

  return (
    <Modal show={show} onHide={() => { if (!saving) onHide(); }} size="lg" centered scrollable backdrop={saving ? "static" : true}>
      <Modal.Header closeButton={!saving}>
        <Modal.Title className="h5 mb-0">Fast simulation</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p className="small text-secondary mb-2">
          The bar is the fuel-to-cell chord. Fission neutrons enter from the left and fly
          straight through. The pale cell is empty, and that is where the damage-weighted
          flux is scored. The side faces are reflective, so the slab is infinite sideways.
        </p>
        <svg
          id="fast-slab-preview"
          viewBox={enlarged ? "0 0 680 230" : "0 0 680 130"}
          width="100%"
          role="img"
          aria-label={layers.map((layer) => `${formatLength(layer.cm)} ${layer.name}`).join(", ")}
        >
          <text x="8" y="16" fill="#0f172a" fontSize="13">
            fuel side
          </text>
          <text x="672" y="16" fill="#0f172a" fontSize="13" textAnchor="end">
            InGaAs side
          </text>
          <SlabBar layers={layers} y={28} label={`Full chord, ${formatLength(totalCm)}`} />
          {enlarged && (
            <SlabBar layers={enlarged} y={128} label="Last 40 cm, enlarged" />
          )}
        </svg>
        <div className="d-flex flex-wrap gap-3 small mt-2 mb-3">
          {layers.map((layer) => (
            <span key={`${layer.role}-${layer.name}`} className="d-inline-flex align-items-center gap-1">
              <span
                style={{
                  width: 12,
                  height: 12,
                  background: COLORS[layer.role],
                  border: "1px solid #0f172a",
                  display: "inline-block",
                }}
              />
              {ROLE_LABEL[layer.role]} · {layer.name} · {formatLength(layer.cm)}
            </span>
          ))}
        </div>
        <p className="small text-secondary mb-3">
          The number in the log is that flux per source neutron, weighted by the same GaAs
          damage table as the InGaAs DDD tally. It ranks the shield. It is not the dose in MeV/g.
          {totalCm > 150
            ? " A chord this long still takes minutes, and a short run can be noisy."
            : ""}
        </p>
        {error && <Alert variant="danger">{error}</Alert>}
        <div className="d-flex flex-wrap gap-3">
          <Form.Group>
            <Form.Label className="small mb-1">Particles / batch</Form.Label>
            <Form.Control
              type="number"
              min={100}
              max={1000000}
              value={particles}
              disabled={saving}
              onChange={(event) => setParticles(Number(event.target.value))}
            />
          </Form.Group>
          <Form.Group>
            <Form.Label className="small mb-1">Batches</Form.Label>
            <Form.Control
              type="number"
              min={1}
              max={500}
              value={batches}
              disabled={saving}
              onChange={(event) => setBatches(Number(event.target.value))}
            />
          </Form.Group>
          <Form.Group>
            <Form.Label className="small mb-1">Threads</Form.Label>
            <Form.Control
              type="number"
              min={1}
              max={256}
              value={threads}
              disabled={saving}
              onChange={(event) => setThreads(Number(event.target.value))}
            />
          </Form.Group>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="outline-secondary" size="sm" onClick={onHide} disabled={saving}>
          Cancel
        </Button>
        <Button variant="primary" size="sm" onClick={append} disabled={saving || solids.length === 0}>
          {saving ? "Appending…" : "Append"}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default FastSlabModal;
