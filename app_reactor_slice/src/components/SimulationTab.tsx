import React, { useEffect, useRef, useState } from "react";
import { Alert, Button, Col, Form, Row } from "react-bootstrap";
import {
  NSM_MATERIALS,
  PARTICLE_TYPES,
  RUN_MODES,
  WEIGHT_WINDOWS,
  type NsmMaterial,
  type ParticleType,
  type RunMode,
  type WeightWindows,
} from "../constants";
import type { Setup } from "../configurations";

export type SimulationParams = {
  run_mode: RunMode;
  n_batches: number;
  nsm_material: NsmMaterial;
  nsm_thickness: number;
  conical_pitch: number;
  particle_type: ParticleType;
  weight_windows: WeightWindows;
  dose_time: number;
  print_core_characteristics: boolean;
};

export const DEFAULT_SIMULATION_PARAMS: SimulationParams = {
  run_mode: "render",
  n_batches: 200,
  nsm_material: "Graphite",
  nsm_thickness: 25,
  conical_pitch: 15,
  particle_type: "neutron",
  weight_windows: "no",
  dose_time: 10,
  print_core_characteristics: true,
};

type Props = {
  params: SimulationParams;
  onChange: (next: SimulationParams) => void;
  setup: Setup;
};

function stamp(): string {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

const SimulationTab: React.FC<Props> = ({ params, onChange, setup }) => {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const setField = <K extends keyof SimulationParams>(key: K, value: SimulationParams[K]) => {
    onChange({ ...params, [key]: value });
  };

  const append = (line: string) => {
    setOutput((prev) => `${prev}${prev ? "\n" : ""}[${stamp()}] ${line}`);
  };

  const closeStream = () => {
    sourceRef.current?.close();
    sourceRef.current = null;
  };

  useEffect(() => () => closeStream(), []);

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [output]);

  const openStream = () => {
    closeStream();
    const source = new EventSource("/api/simulation/stream");
    sourceRef.current = source;
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { type: string; line?: string; code?: number; running?: boolean };
        if (payload.type === "log" && payload.line) {
          append(payload.line);
          if (payload.line.startsWith("[runner] done exit=")) {
            setRunning(false);
            closeStream();
          }
        } else if (payload.type === "done") {
          setRunning(false);
          closeStream();
        } else if (payload.type === "ready" && payload.running) {
          setRunning(true);
        }
      } catch {
        append(event.data);
      }
    };
    source.onerror = () => {
      // Browser retries EventSource; leave it unless we intentionally closed.
      if (!sourceRef.current) return;
    };
  };

  const onStart = async () => {
    if (running) return;
    setError(null);
    setOutput("");
    setRunning(true);
    openStream();

    const body = {
      setup,
      simulation: params,
    };

    try {
      const response = await fetch("/api/simulation/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as { ok?: boolean; error?: string };
      if (!response.ok) {
        setError(data.error || `Start failed (${response.status})`);
        setRunning(false);
        closeStream();
        append(data.error || `Start failed (${response.status})`);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setRunning(false);
      closeStream();
      append(message);
    }
  };

  const onStop = async () => {
    try {
      await fetch("/api/simulation/stop", { method: "POST" });
    } catch {
      // The stream will still report process exit if the kill worked.
    }
  };

  const onClear = () => {
    if (running) return;
    setOutput("");
    setError(null);
  };

  return (
    <Row className="g-3 simulation-tab">
      <Col lg={4}>
        <div className="border rounded p-3 bg-white h-100">
          <h2 className="h6 mb-3">RIMAG run parameters</h2>
          <p className="small text-secondary mb-3">
            Starts <code>simulation_app_slice.py</code> in Docker with the current calculator setup (zones, layers,
            enrichment, columns) plus these run knobs. Output streams below.
          </p>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Run mode</Form.Label>
            <Form.Select
              size="sm"
              value={params.run_mode}
              disabled={running}
              onChange={(event) => setField("run_mode", event.target.value as RunMode)}
            >
              {RUN_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Batches</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={1}
              step={1}
              value={params.n_batches}
              disabled={running}
              onChange={(event) => {
                const next = Math.max(1, Math.round(Number(event.target.value) || 1));
                setField("n_batches", next);
              }}
            />
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Neutron shield moderator</Form.Label>
            <Form.Select
              size="sm"
              value={params.nsm_material}
              disabled={running}
              onChange={(event) => setField("nsm_material", event.target.value as NsmMaterial)}
            >
              {NSM_MATERIALS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">NSM thickness (cm)</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={0}
              step={0.1}
              value={params.nsm_thickness}
              disabled={running}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next) && next >= 0) setField("nsm_thickness", next);
              }}
            />
            <div className="small text-secondary mt-1">Stored for the run config; app-slice CSG uses the zone layout.</div>
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Conical pitch (°)</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={0}
              max={45}
              step={0.1}
              value={params.conical_pitch}
              disabled={running}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next) && next >= 0) setField("conical_pitch", next);
              }}
            />
            <div className="small text-secondary mt-1">
              Layer bounds become cones about the disk axis (0° = flat disks).
            </div>
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Particle type</Form.Label>
            <Form.Select
              size="sm"
              value={params.particle_type}
              disabled={running}
              onChange={(event) => setField("particle_type", event.target.value as ParticleType)}
            >
              {PARTICLE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Weight windows</Form.Label>
            <Form.Select
              size="sm"
              value={params.weight_windows}
              disabled={running}
              onChange={(event) => setField("weight_windows", event.target.value as WeightWindows)}
            >
              {WEIGHT_WINDOWS.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Dose time (years)</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={0}
              step={0.1}
              value={params.dose_time}
              disabled={running}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next) && next >= 0) setField("dose_time", next);
              }}
            />
          </Form.Group>

          <Form.Check
            type="checkbox"
            id="print-core-characteristics"
            className="small mb-3"
            label="Print core characteristics"
            checked={params.print_core_characteristics}
            disabled={running}
            onChange={(event) => setField("print_core_characteristics", event.target.checked)}
          />

          <div className="d-flex gap-2">
            <Button variant="primary" className="flex-grow-1" disabled={running} onClick={() => void onStart()}>
              {running ? "Running…" : "Start simulation"}
            </Button>
            <Button variant="outline-danger" disabled={!running} onClick={() => void onStop()}>
              Stop
            </Button>
            <Button variant="outline-secondary" disabled={running || !output} onClick={onClear}>
              Clear
            </Button>
          </div>

          {error && (
            <Alert variant="danger" className="py-2 px-3 small mt-3 mb-0">
              {error}
            </Alert>
          )}
          {running && (
            <Alert variant="info" className="py-2 px-3 small mt-3 mb-0">
              Streaming Docker / RIMAG output. Requires Docker Desktop and a built <code>rimag</code> image.
            </Alert>
          )}
        </div>
      </Col>

      <Col lg={8}>
        <div className="border rounded p-3 bg-white h-100 d-flex flex-column simulation-output-card">
          <div className="d-flex justify-content-between align-items-baseline mb-2">
            <h2 className="h6 mb-0">Simulation output</h2>
            <span className="small text-secondary">{running ? "live" : output ? "idle" : "empty"}</span>
          </div>
          <pre ref={logRef} className="simulation-output mb-0" aria-live="polite">
            {output || "Start a simulation to stream RIMAG stdout here."}
          </pre>
        </div>
      </Col>
    </Row>
  );
};

export default SimulationTab;
