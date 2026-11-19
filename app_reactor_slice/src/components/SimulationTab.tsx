import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import { Alert, Button, Col, Collapse, Form, OverlayTrigger, ProgressBar, Row, Tooltip } from "react-bootstrap";
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

function InfoTip({ text }: { text: React.ReactNode }) {
  const tipId = useId();
  return (
    <OverlayTrigger
      placement="right"
      overlay={
        <Tooltip id={tipId} className="simulation-info-tooltip">
          {text}
        </Tooltip>
      }
    >
      <button type="button" className="simulation-info-btn" aria-label="More information" tabIndex={0}>
        <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="8" cy="5" r="1" fill="currentColor" />
          <path d="M8 7.2v4.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </OverlayTrigger>
  );
}

function FieldLabel({
  children,
  info,
  className = "small mb-0",
}: {
  children: React.ReactNode;
  info?: React.ReactNode;
  className?: string;
}) {
  return (
    <Form.Label className={`${className} simulation-field-label d-inline-flex align-items-center gap-1`}>
      <span>{children}</span>
      {info != null ? <InfoTip text={info} /> : null}
    </Form.Label>
  );
}

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
  spatialCoverage: number | null;
  energyCoverage: number | null;
  outerCoverage: number | null;
  decades: number | null;
  reachYCm: number | null;
  meshRMaxCm: number | null;
};

type KeffLive = {
  value: number | null;
  uncertainty: number | null;
  batch: number | null;
  totalBatches: number | null;
  generation: number | null;
  generationsPerBatch: number | null;
  phase: "inactive" | "active" | null;
  percent: number | null;
  eta: string | null;
  source: "progress" | "final" | null;
  finalRank: number;
};

const EMPTY_KEFF: KeffLive = {
  value: null,
  uncertainty: null,
  batch: null,
  totalBatches: null,
  generation: null,
  generationsPerBatch: null,
  phase: null,
  percent: null,
  eta: null,
  source: null,
  finalRank: -1,
};

/** Matches simlib._OpenMCProgressReporter lines. */
const OPENMC_PROGRESS_RE =
  /\[OpenMC\]\s+\|[^|]*\|\s+([\d.]+)%\s+batch\s+(\d+)\/(\d+)\s+gen\s+(\d+)\/(\d+)(?:\s+(inactive|active))?(?:\s+k=([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(?:\s+\+\/-\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))?)?(?:\s+ETA\s+(\S+))?/;

const KEFF_FINAL_RE =
  /k-effective\s+\((Combined|Collision|Track-length|Absorption)\)\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*\+\/-\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)/i;

const FINAL_KEFF_RANK: Record<string, number> = {
  Combined: 4,
  Collision: 3,
  Absorption: 2,
  "Track-length": 1,
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

function formatKeff(value: number | null, uncertainty: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const k = value.toFixed(5);
  if (uncertainty == null || !Number.isFinite(uncertainty)) return k;
  return `${k} ± ${uncertainty.toFixed(5)}`;
}

function parseKeffFromLine(line: string, prev: KeffLive): KeffLive | null {
  const progress = OPENMC_PROGRESS_RE.exec(line);
  if (progress) {
    const kRaw = progress[7] != null ? Number(progress[7]) : NaN;
    const uncRaw = progress[8] != null ? Number(progress[8]) : NaN;
    const phase =
      progress[6] === "inactive" || progress[6] === "active"
        ? progress[6]
        : prev.phase;
    return {
      value: Number.isFinite(kRaw) ? kRaw : prev.value,
      uncertainty: Number.isFinite(uncRaw) ? uncRaw : null,
      batch: Number(progress[2]),
      totalBatches: Number(progress[3]),
      generation: Number(progress[4]),
      generationsPerBatch: Number(progress[5]),
      phase,
      percent: Number(progress[1]),
      eta: progress[9] ?? prev.eta,
      source: "progress",
      finalRank: -1,
    };
  }

  const finalMatch = KEFF_FINAL_RE.exec(line);
  if (finalMatch) {
    const kind = finalMatch[1];
    const value = Number(finalMatch[2]);
    const uncertainty = Number(finalMatch[3]);
    if (!Number.isFinite(value)) return null;
    const rank = FINAL_KEFF_RANK[kind] ?? 0;
    if (prev.source === "final" && rank < prev.finalRank) return null;
    return {
      ...prev,
      value,
      uncertainty: Number.isFinite(uncertainty) ? uncertainty : null,
      percent: 100,
      eta: "0:00",
      source: "final",
      phase: "active",
      finalRank: rank,
    };
  }

  return null;
}

const SimulationTab: React.FC<Props> = ({ params, onChange, setup }) => {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [wwOpen, setWwOpen] = useState(false);
  const [wwStatus, setWwStatus] = useState<WwStatus | null>(null);
  const [keffLive, setKeffLive] = useState<KeffLive>(EMPTY_KEFF);
  const logRef = useRef<HTMLPreElement>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const setField = <K extends keyof SimulationParams>(key: K, value: SimulationParams[K]) => {
    onChange({ ...params, [key]: value });
  };

  const append = (line: string) => {
    const cleaned = line.replace(/\r/g, "");
    setOutput((prev) => `${prev}${prev ? "\n" : ""}[${stamp()}] ${cleaned}`);
    setKeffLive((prev) => parseKeffFromLine(cleaned, prev) ?? prev);
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
            setKeffLive(EMPTY_KEFF);
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
    setKeffLive(EMPTY_KEFF);
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
    setKeffLive(EMPTY_KEFF);
    setError(null);
  };

  const showKeffPanel = running || keffLive.value != null || keffLive.percent != null;
  const progressPercent =
    keffLive.percent != null && Number.isFinite(keffLive.percent)
      ? Math.max(0, Math.min(100, keffLive.percent))
      : running
        ? 0
        : null;

  const wwSummary = (() => {
    if (!wwStatus) return "Checking…";
    if (!wwStatus.present) return "No weight_windows.h5 in runs/default";
    const bits = [`present`];
    if (wwStatus.passes != null) bits.push(`${wwStatus.passes} pass${wwStatus.passes === 1 ? "" : "es"}`);
    if (wwStatus.lastPass) bits.push(`last=${wwStatus.lastPass}`);
    if (wwStatus.meshCm != null) bits.push(`mesh ${wwStatus.meshCm} cm`);
    if (wwStatus.energyGroups != null) bits.push(`${wwStatus.energyGroups} groups`);
    if (wwStatus.spatialCoverage != null) {
      bits.push(`spatial ${(100 * wwStatus.spatialCoverage).toFixed(0)}%`);
    }
    if (wwStatus.outerCoverage != null) {
      bits.push(`outer ${(100 * wwStatus.outerCoverage).toFixed(0)}%`);
    }
    if (wwStatus.decades != null) bits.push(`${wwStatus.decades.toFixed(1)} decades`);
    if (wwStatus.reachYCm != null && wwStatus.meshRMaxCm != null) {
      bits.push(`reach +y ${wwStatus.reachYCm.toFixed(0)}/${wwStatus.meshRMaxCm.toFixed(0)} cm`);
    }
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
            Starts <code>simulation_app_slice.py</code> in Docker with the current calculator setup
          </p>

          <Form.Group className="simulation-field">
            <Form.Label className="small mb-0 simulation-field-label">Run mode</Form.Label>
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

          <Form.Group className="simulation-field">
            <Form.Label className="small mb-0 simulation-field-label">Batches</Form.Label>
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

          <Form.Group className="simulation-field">
            <FieldLabel info={<>Passed to OpenMC as <code>RIMAG_THREADS</code> / <code>simsettings.json</code>.</>}>
              OpenMP threads
            </FieldLabel>
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
          </Form.Group>

          <Form.Group className="simulation-field">
            <Form.Label className="small mb-0 simulation-field-label">Neutron shield moderator</Form.Label>
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

          <Form.Group className="simulation-field">
            <FieldLabel info="Stored for the run config; app-slice CSG uses the zone layout.">
              NSM thickness (cm)
            </FieldLabel>
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

          <Form.Group className="simulation-field">
            <FieldLabel info="Elemental boron by mass in the graphite of the fuel layer. Reflector, disk, and shield graphite stay pure carbon.">
              Boron concentration (ppm)
            </FieldLabel>
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
          </Form.Group>

          <Form.Group className="simulation-field">
            <FieldLabel info="Layer bounds become cones about the disk axis (0° = flat disks). Increasing the conical pitch increases simulation time significantly.">
              Conical pitch (°)
            </FieldLabel>
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

          <Form.Group className="simulation-field">
            <Form.Label className="small mb-0 simulation-field-label">Particle type</Form.Label>
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
              <FieldLabel
                className="small mb-0 fw-semibold"
                info={
                  <>
                    For deep shields (~10 orders of magnitude to the InGaAs), seed once, then refine until the TPV
                    tallies get scores. Seed runs analog keff then writes MAGIC windows offline. Each refine applies
                    the previous <code>weight_windows.h5</code> and regenerates it. Then set tally mode to{" "}
                    <em>use</em> and start a normal run.
                  </>
                }
              >
                Weight windows
              </FieldLabel>
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

            <Form.Group className="simulation-field">
              <Form.Label className="small mb-0 simulation-field-label">Tally mode</Form.Label>
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
                <Form.Group className="simulation-field">
                  <FieldLabel info="Start coarse (40 cm). Finer cells resolve the shield better but make seed/refine much slower.">
                    Mesh cell (cm)
                  </FieldLabel>
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
                </Form.Group>
                <Form.Group className="simulation-field">
                  <Form.Label className="small mb-0 simulation-field-label">Energy groups</Form.Label>
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

          <Form.Group className="simulation-field">
            <Form.Label className="small mb-0 simulation-field-label">Dose time (years)</Form.Label>
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
            className="small mb-3"
            label={
              <span className="d-inline-flex align-items-center gap-1">
                Photovoltaic DDD tallies only
                <InfoTip text="When on, keff keeps only the SR-NIEL flux tally on the InGaAs cells (keff itself still comes from the eigenvalue solve). Turn off for heating, tritium, C-14, IFP, and the rest." />
              </span>
            }
            checked={params.ddd_tallies_only}
            disabled={running}
            onChange={(event) => setField("ddd_tallies_only", event.target.checked)}
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
          {showKeffPanel && (
            <div className="simulation-keff-panel mb-2" aria-live="polite">
              <div className="d-flex flex-wrap justify-content-between align-items-baseline gap-2 mb-1">
                <div className="simulation-keff-value">
                  <span className="simulation-keff-label">keff</span>{" "}
                  <span className="font-monospace fw-semibold">
                    {formatKeff(keffLive.value, keffLive.uncertainty)}
                  </span>
                  {keffLive.uncertainty == null && keffLive.value != null && keffLive.phase === "inactive" && (
                    <span className="small text-secondary ms-2">inactive (no σ yet)</span>
                  )}
                  {keffLive.source === "final" && (
                    <span className="small text-secondary ms-2">final</span>
                  )}
                </div>
                <div className="small text-secondary font-monospace">
                  {keffLive.batch != null && keffLive.totalBatches != null && (
                    <>
                      batch {keffLive.batch}/{keffLive.totalBatches}
                      {keffLive.generation != null && keffLive.generationsPerBatch != null && (
                        <>
                          {" "}
                          · gen {keffLive.generation}/{keffLive.generationsPerBatch}
                        </>
                      )}
                      {keffLive.phase && <> · {keffLive.phase}</>}
                    </>
                  )}
                  {keffLive.eta != null && (
                    <>
                      {(keffLive.batch != null ? " · " : "") + `ETA ${keffLive.eta}`}
                    </>
                  )}
                </div>
              </div>
              <ProgressBar
                now={progressPercent ?? 0}
                animated={running && (progressPercent == null || progressPercent < 100)}
                striped={running}
                label={
                  progressPercent != null ? `${progressPercent.toFixed(1)}%` : running ? "…" : undefined
                }
                className="simulation-keff-bar"
              />
            </div>
          )}
          <pre ref={logRef} className="simulation-output mb-0" aria-live="polite">
            {output || "Start a simulation to stream RIMAG stdout here."}
          </pre>
        </div>
      </Col>
    </Row>
  );
};

export default SimulationTab;
