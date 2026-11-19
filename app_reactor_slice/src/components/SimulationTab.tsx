import React, { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, Col, Collapse, Form, Row } from "react-bootstrap";
import {
  NSM_MATERIALS,
  PARTICLE_TYPES,
  RUN_MODES,
  WEIGHT_WINDOWS,
  type NsmMaterial,
  type ParticleType,
  type RunMode,
  type WeightWindows,
  type WeightWindowsRun,
} from "../constants";
import {
  DEFAULT_SIMULATION_PARAMS,
  type Setup,
  type SimulationParams,
} from "../configurations";

export type { SimulationParams };
export { DEFAULT_SIMULATION_PARAMS };

type Props = {
  params: SimulationParams;
  onChange: (next: SimulationParams) => void;
  setup: Setup;
};

type WwStatus = {
  present: boolean;
  sizeBytes: number | null;
  passes: number | null;
  lastPass: string | null;
  meshCm: number | null;
  energyGroups: number | null;
  batches: number | null;
  updatedAt: string | null;
};

function stamp(): string {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

function formatBytes(bytes: number | null): string {
  if (bytes == null || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const SimulationTab: React.FC<Props> = ({ params, onChange, setup }) => {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [wwOpen, setWwOpen] = useState(false);
  const [wwStatus, setWwStatus] = useState<WwStatus | null>(null);
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

  const refreshWwStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/simulation/weight-windows");
      if (!response.ok) return;
      const data = (await response.json()) as WwStatus;
      setWwStatus(data);
    } catch {
      // leave last known status
    }
  }, []);

  const openStream = (replaceHistory: boolean) => {
    closeStream();
    let clearOnReady = replaceHistory;
    const source = new EventSource("/api/simulation/stream");
    sourceRef.current = source;
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as {
          type: string;
          line?: string;
          code?: number;
          running?: boolean;
        };
        if (payload.type === "ready") {
          if (clearOnReady) {
            setOutput("");
            clearOnReady = false;
          }
          setRunning(Boolean(payload.running));
          return;
        }
        if (payload.type === "log" && payload.line) {
          append(payload.line);
          if (payload.line.startsWith("[runner] done exit=")) {
            setRunning(false);
            void refreshWwStatus();
          }
          return;
        }
        if (payload.type === "done") {
          setRunning(false);
          void refreshWwStatus();
        }
      } catch {
        append(event.data);
      }
    };
    source.onerror = () => {
      if (!sourceRef.current) return;
    };
  };

  useEffect(() => {
    openStream(true);
    void refreshWwStatus();
    return () => closeStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount/unmount only
  }, []);

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [output]);

  const startWith = async (overrides: Partial<SimulationParams> & { weight_windows?: WeightWindowsRun }) => {
    if (running) return;
    setError(null);
    setOutput("");
    setRunning(true);
    openStream(true);

    const simulation = { ...params, ...overrides };
    const body = { setup, simulation };

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
        append(data.error || `Start failed (${response.status})`);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setRunning(false);
      append(message);
    }
  };

  const onStart = () => void startWith({});

  const onSeedWw = () => {
    append("Weight windows: seeding MAGIC (offline after analog keff)…");
    void startWith({
      weight_windows: "seed",
      run_mode: "keff_notallies",
      survival_biasing: true,
    });
  };

  const onRefineWw = () => {
    if (!wwStatus?.present) {
      setError("No weight_windows.h5 yet. Run Seed first.");
      return;
    }
    append("Weight windows: refining with the previous windows applied…");
    void startWith({
      weight_windows: "refine",
      run_mode: "keff_notallies",
      survival_biasing: false,
    });
  };

  const onClearWw = async () => {
    if (running) return;
    try {
      const response = await fetch("/api/simulation/weight-windows", { method: "DELETE" });
      const data = (await response.json()) as WwStatus & { error?: string; removed?: boolean };
      if (!response.ok) {
        setError(data.error || `Clear failed (${response.status})`);
        return;
      }
      setWwStatus(data);
      append(data.removed ? "Cleared weight_windows.h5." : "No weight-window file to clear.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onStop = async () => {
    append("Stop requested…");
    try {
      const response = await fetch("/api/simulation/stop", { method: "POST" });
      const data = (await response.json()) as { stopped?: boolean };
      if (!data.stopped) append("No running simulation to stop.");
    } catch (err: unknown) {
      append(err instanceof Error ? err.message : String(err));
    }
  };

  const onClear = () => {
    if (running) return;
    setOutput("");
    setError(null);
  };

  const wwSummary = (() => {
    if (!wwStatus) return "Checking…";
    if (!wwStatus.present) return "No weight_windows.h5 in runs/default";
    const bits = [`present`];
    if (wwStatus.passes != null) bits.push(`${wwStatus.passes} pass${wwStatus.passes === 1 ? "" : "es"}`);
    if (wwStatus.lastPass) bits.push(`last=${wwStatus.lastPass}`);
    if (wwStatus.meshCm != null) bits.push(`mesh ${wwStatus.meshCm} cm`);
    if (wwStatus.energyGroups != null) bits.push(`${wwStatus.energyGroups} groups`);
    const size = formatBytes(wwStatus.sizeBytes);
    if (size) bits.push(size);
    return bits.join(" · ");
  })();

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
            <Form.Label className="small mb-1">OpenMP threads</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={1}
              max={256}
              step={1}
              value={params.n_threads}
              disabled={running}
              onChange={(event) => {
                const next = Math.max(1, Math.min(256, Math.round(Number(event.target.value) || 1)));
                setField("n_threads", next);
              }}
            />
            <div className="small text-secondary mt-1">
              Passed to OpenMC as <code>RIMAG_THREADS</code> / <code>simsettings.json</code>.
            </div>
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
            <Form.Label className="small mb-1">Boron concentration (ppm)</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={0}
              step={1}
              value={params.boron_concentration_ppm}
              disabled={running}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next) && next >= 0) setField("boron_concentration_ppm", next);
              }}
            />
            <div className="small text-secondary mt-1">
              Elemental boron by mass in the graphite of the fuel layer. Reflector, disk, and shield graphite stay pure carbon.
            </div>
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
              Layer bounds become cones about the disk axis (0° = flat disks). Increasing the conical pitch increases simulation time significantly.
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

          <div className="border rounded p-2 mb-3 bg-light-subtle">
            <div className="d-flex justify-content-between align-items-center gap-2">
              <Form.Label className="small mb-0 fw-semibold">Weight windows</Form.Label>
              <Button
                size="sm"
                variant="link"
                className="p-0 small"
                onClick={() => setWwOpen((open) => !open)}
                aria-expanded={wwOpen}
              >
                {wwOpen ? "Hide build steps" : "Build steps"}
              </Button>
            </div>
            <div className="small text-secondary mt-1 mb-2">{wwSummary}</div>

            <Form.Group className="mb-2">
              <Form.Label className="small mb-1">Tally mode</Form.Label>
              <Form.Select
                size="sm"
                value={params.weight_windows}
                disabled={running}
                onChange={(event) => setField("weight_windows", event.target.value as WeightWindows)}
              >
                {WEIGHT_WINDOWS.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode === "no" ? "no (analog)" : "use (apply existing windows)"}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>

            <Collapse in={wwOpen}>
              <div>
                <p className="small text-secondary mb-2">
                  For deep shields (~10 orders of magnitude to the InGaAs), seed once, then refine until the TPV
                  tallies get scores. Seed runs analog keff then writes MAGIC windows offline (on-the-fly MAGIC
                  loses particles on periodic cones). Each refine applies the previous{" "}
                  <code>weight_windows.h5</code> and regenerates it. Then set tally mode to <em>use</em> and
                  start a normal run.
                </p>
                <Form.Group className="mb-2">
                  <Form.Label className="small mb-1">Mesh cell (cm)</Form.Label>
                  <Form.Control
                    size="sm"
                    type="number"
                    min={0.5}
                    step={0.5}
                    value={params.ww_mesh_cm}
                    disabled={running}
                    onChange={(event) => {
                      const next = Number(event.target.value);
                      if (Number.isFinite(next) && next > 0) setField("ww_mesh_cm", next);
                    }}
                  />
                  <div className="small text-secondary mt-1">
                    Start coarse (40 cm). Finer cells resolve the shield better but make seed/refine much slower.
                  </div>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label className="small mb-1">Energy groups</Form.Label>
                  <Form.Control
                    size="sm"
                    type="number"
                    min={1}
                    max={200}
                    step={1}
                    value={params.ww_energy_groups}
                    disabled={running}
                    onChange={(event) => {
                      const next = Math.max(1, Math.min(200, Math.round(Number(event.target.value) || 1)));
                      setField("ww_energy_groups", next);
                    }}
                  />
                </Form.Group>
                <div className="d-flex flex-wrap gap-2">
                  <Button size="sm" variant="outline-primary" disabled={running} onClick={onSeedWw}>
                    1. Seed
                  </Button>
                  <Button
                    size="sm"
                    variant="outline-primary"
                    disabled={running || !wwStatus?.present}
                    onClick={onRefineWw}
                  >
                    2. Refine once
                  </Button>
                  <Button size="sm" variant="outline-secondary" disabled={running} onClick={() => void onClearWw()}>
                    Clear WW
                  </Button>
                </div>
              </div>
            </Collapse>
          </div>

          <Form.Check
            type="checkbox"
            id="survival-biasing"
            className="small mb-3"
            label="Survival biasing"
            checked={params.survival_biasing}
            disabled={running}
            onChange={(event) => setField("survival_biasing", event.target.checked)}
          />

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
            className="small mb-2"
            label="Print core characteristics"
            checked={params.print_core_characteristics}
            disabled={running}
            onChange={(event) => setField("print_core_characteristics", event.target.checked)}
          />

          <Form.Check
            type="checkbox"
            id="ddd-tallies-only"
            className="small mb-1"
            label="Photovoltaic DDD tallies only"
            checked={params.ddd_tallies_only}
            disabled={running}
            onChange={(event) => setField("ddd_tallies_only", event.target.checked)}
          />
          <div className="small text-secondary mb-3">
            When on, keff keeps only the SR-NIEL flux tally on the InGaAs cells (keff itself still comes from the
            eigenvalue solve). Turn off for heating, tritium, C-14, IFP, and the rest.
          </div>

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
