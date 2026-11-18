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

export type SimulationParams = {
  run_mode: RunMode;
  n_batches: number;
  nsm_material: NsmMaterial;
  nsm_thickness: number;
  conical_pitch: number;
  particle_type: ParticleType;
  weight_windows: WeightWindows;
  dose_time: number;
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
};

type Props = {
  params: SimulationParams;
  onChange: (next: SimulationParams) => void;
};

function stamp(): string {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

const SimulationTab: React.FC<Props> = ({ params, onChange }) => {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const logRef = useRef<HTMLPreElement>(null);
  const timersRef = useRef<number[]>([]);

  const setField = <K extends keyof SimulationParams>(key: K, value: SimulationParams[K]) => {
    onChange({ ...params, [key]: value });
  };

  const append = (line: string) => {
    setOutput((prev) => `${prev}${prev ? "\n" : ""}[${stamp()}] ${line}`);
  };

  const clearTimers = () => {
    for (const id of timersRef.current) window.clearTimeout(id);
    timersRef.current = [];
  };

  useEffect(() => () => clearTimers(), []);

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [output]);

  const onStart = () => {
    if (running) return;
    clearTimers();
    setRunning(true);
    setOutput("");

    const payload = {
      nsm_material: params.nsm_material,
      nsm_thickness: params.nsm_thickness,
      conical_pitch: params.conical_pitch,
      n_batches: params.n_batches,
      run_mode: params.run_mode,
      particle_type: params.particle_type,
      weight_windows: params.weight_windows,
      dose_time: params.dose_time,
    };

    const steps: Array<[number, string]> = [
      [0, "Simulation start requested (dummy — no RIMAG process yet)."],
      [200, `Parameters: ${JSON.stringify(payload)}`],
      [500, "Would write params JSON and call: docker compose run --rm rimag python simulation_paper.py <params.json>"],
      [900, "Waiting for stdout…"],
      [1400, "(stub) No process attached. Wire this button to the RIMAG runner next."],
      [1800, "Done."],
    ];

    for (const [delay, message] of steps) {
      const id = window.setTimeout(() => {
        append(message);
        if (message === "Done.") setRunning(false);
      }, delay);
      timersRef.current.push(id);
    }
  };

  const onClear = () => {
    if (running) return;
    setOutput("");
  };

  return (
    <Row className="g-3 simulation-tab">
      <Col lg={4}>
        <div className="border rounded p-3 bg-white h-100">
          <h2 className="h6 mb-3">RIMAG run parameters</h2>
          <p className="small text-secondary mb-3">
            Values written into the parameter file passed to <code>simulation_paper.py</code>. Geometry still comes from
            the current calculator setup once the runner is wired.
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

          <Form.Group className="mb-3">
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

          <div className="d-flex gap-2">
            <Button variant="primary" className="flex-grow-1" disabled={running} onClick={onStart}>
              {running ? "Running…" : "Start simulation"}
            </Button>
            <Button variant="outline-secondary" disabled={running || !output} onClick={onClear}>
              Clear
            </Button>
          </div>

          {running && (
            <Alert variant="info" className="py-2 px-3 small mt-3 mb-0">
              Dummy run in progress. Output below is simulated.
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
