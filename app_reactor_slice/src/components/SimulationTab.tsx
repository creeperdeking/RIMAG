import React, { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, Col, ProgressBar, Row } from "react-bootstrap";
import { WEIGHT_WINDOWS, type WeightWindows, type WeightWindowsRun } from "../constants";
import {
  DEFAULT_SIMULATION_PARAMS,
  type Setup,
  type SimulationParams,
} from "../configurations";
import FastSlabModal from "./FastSlabModal";
import RunQueueModal, { type QueueModalMode } from "./RunQueueModal";

export type { SimulationParams };
export { DEFAULT_SIMULATION_PARAMS };

type Props = {
  params: SimulationParams;
  onChange: (next: SimulationParams) => void;
  setup: Setup;
  /** Overview thermal power [MW] for append-modal default. */
  defaultThermalPowerMw?: number | null;
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
  ingaasVoxels: number | null;
  ingaasReached: number | null;
  ingaasReachFraction: number | null;
  ingaasEnergyFraction: number | null;
};

type QueueItemStatus = "queued" | "running" | "done" | "failed" | "cancelled";

type QueueItemResult = {
  summary?: string | null;
  keff?: number | null;
  keffUncertainty?: number | null;
  ingaasReached?: number | null;
  ingaasVoxels?: number | null;
  ingaasReachFraction?: number | null;
  ingaasEnergyFraction?: number | null;
  gammaKGy?: number | null;
  gammaCi95Pct?: number | null;
  gammaYears?: number | null;
};

type QueueItem = {
  id: string;
  status: QueueItemStatus;
  label: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  exitCode: number | null;
  payload?: { setup?: unknown; simulation?: unknown } | null;
  result?: QueueItemResult | null;
};

type SimQueue = {
  items: QueueItem[];
};

type QueueModalState = {
  mode: QueueModalMode;
  title: string;
  itemId: string | null;
  simulation: SimulationParams & { weight_windows?: WeightWindowsRun | string };
  result?: QueueItemResult | null;
  exitCode?: number | null;
  statusLabel?: string | null;
  startedAt?: string | null;
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

const SimulationTab: React.FC<Props> = ({ params, onChange, setup, defaultThermalPowerMw = null }) => {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [wwStatus, setWwStatus] = useState<WwStatus | null>(null);
  const [keffLive, setKeffLive] = useState<KeffLive>(EMPTY_KEFF);
  const [queue, setQueue] = useState<SimQueue>({ items: [] });
  const [queuePaused, setQueuePaused] = useState(false);
  const [queueModal, setQueueModal] = useState<QueueModalState | null>(null);
  const [queueModalError, setQueueModalError] = useState<string | null>(null);
  const [queueModalSaving, setQueueModalSaving] = useState(false);
  const [fastOpen, setFastOpen] = useState(false);
  const [fastError, setFastError] = useState<string | null>(null);
  const [fastSaving, setFastSaving] = useState(false);
  const [dragQueuedId, setDragQueuedId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);
  const sourceRef = useRef<EventSource | null>(null);

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
          queuePaused?: boolean;
          queue?: SimQueue;
        };
        if (payload.queue) {
          setQueue(payload.queue);
          if (payload.queue.items.some((item) => item.status === "running")) {
            setRunning(true);
          }
        }
        if (typeof payload.queuePaused === "boolean") {
          setQueuePaused(payload.queuePaused);
        }
        if (payload.type === "ready") {
          if (clearOnReady) {
            setOutput("");
            setKeffLive(EMPTY_KEFF);
            clearOnReady = false;
          }
          setRunning(Boolean(payload.running));
          return;
        }
        if (payload.type === "queue") {
          return;
        }
        if (payload.type === "log" && payload.line) {
          if (payload.line.includes("[runner] Starting next queued run:")) {
            setOutput("");
            setKeffLive(EMPTY_KEFF);
            setRunning(true);
          }
          append(payload.line);
          if (payload.line.startsWith("[runner] done exit=")) {
            setRunning(false);
            void refreshWwStatus();
          }
          return;
        }
        if (payload.type === "done") {
          const stillRunning = Boolean(
            payload.queue?.items.some((item) => item.status === "running"),
          );
          setRunning(stillRunning);
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

  const appendWith = async (
    simulation: SimulationParams & { weight_windows?: WeightWindowsRun },
  ): Promise<boolean> => {
    setError(null);
    const body = { setup, simulation };
    try {
      const response = await fetch("/api/simulation/append", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as {
        ok?: boolean;
        error?: string;
        queue?: SimQueue;
        running?: boolean;
      };
      if (!response.ok) {
        setError(data.error || `Append failed (${response.status})`);
        return false;
      }
      if (data.queue) setQueue(data.queue);
      if (data.running) {
        setRunning(true);
        openStream(false);
      }
      const ww = simulation.weight_windows ?? "no";
      const persistedWw = (WEIGHT_WINDOWS as readonly string[]).includes(ww)
        ? (ww as WeightWindows)
        : params.weight_windows;
      const isWwBuild =
        ww === "seed" || ww === "refine" || ww === "autorefine" || ww === "generate";
      // Seed/refine force keff_notallies for the job only — keep the calculator default as keff.
      onChange({
        ...simulation,
        weight_windows: persistedWw,
        run_mode: isWwBuild
          ? params.run_mode === "keff_notallies"
            ? "keff"
            : params.run_mode
          : simulation.run_mode,
        survival_biasing: isWwBuild ? params.survival_biasing : simulation.survival_biasing,
      });
      append(`[runner] Queued: ${simulation.run_mode} · ww=${ww}`);
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      return false;
    }
  };

  const appendFast = async (simulation: SimulationParams) => {
    setFastSaving(true);
    setFastError(null);
    const body = { setup, simulation };
    try {
      const response = await fetch("/api/simulation/append", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as {
        ok?: boolean;
        error?: string;
        queue?: SimQueue;
        running?: boolean;
      };
      if (!response.ok) {
        setFastError(data.error || `Append failed (${response.status})`);
        return;
      }
      if (data.queue) setQueue(data.queue);
      if (data.running) {
        setRunning(true);
        openStream(false);
      }
      append(`[runner] Queued: fast slab · ${simulation.n_batches} batches`);
      setFastOpen(false);
    } catch (err: unknown) {
      setFastError(err instanceof Error ? err.message : String(err));
    } finally {
      setFastSaving(false);
    }
  };

  const openAppendModal = () => {
    setQueueModalError(null);
    setQueueModal({
      mode: "append",
      title: "Append run",
      itemId: null,
      simulation: {
        ...params,
        // Default tally runs use keff; seed/refine presets switch to keff_notallies in the modal.
        run_mode: params.run_mode === "keff_notallies" ? "keff" : params.run_mode,
        // This host has 8 cores. Don't inherit a saved 12-thread setting into Append.
        n_threads: 8,
      },
    });
  };

  const openQueueItem = async (item: QueueItem) => {
    setQueueModalError(null);
    let full = item;
    try {
      const response = await fetch(`/api/simulation/queue/${encodeURIComponent(item.id)}`);
      if (response.ok) full = (await response.json()) as QueueItem;
    } catch {
      // use list payload
    }
    const simulationRaw =
      full.payload && typeof full.payload === "object" && full.payload.simulation
        ? (full.payload.simulation as SimulationParams & { weight_windows?: string })
        : { ...params };
    const editable = full.status === "queued";
    setQueueModal({
      mode: editable ? "edit" : "view",
      title: editable ? "Edit queued run" : full.status === "running" ? "Running run" : "Past run",
      itemId: full.id,
      simulation: simulationRaw,
      result: full.result ?? null,
      exitCode: full.exitCode,
      statusLabel: full.status,
      startedAt: full.startedAt,
    });
  };

  const onQueueModalSubmit = async (
    simulation: SimulationParams & { weight_windows: WeightWindowsRun },
  ) => {
    if (!queueModal) return;
    setQueueModalSaving(true);
    setQueueModalError(null);
    const body = { setup, simulation };
    try {
      if (queueModal.mode === "append") {
        const ok = await appendWith(simulation);
        if (!ok) {
          setQueueModalError("Could not append this run.");
          return;
        }
        setQueueModal(null);
        return;
      }
      if (queueModal.mode === "edit" && queueModal.itemId) {
        const response = await fetch(
          `/api/simulation/queue/${encodeURIComponent(queueModal.itemId)}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        );
        const data = (await response.json()) as { error?: string; queue?: SimQueue };
        if (!response.ok) {
          setQueueModalError(data.error || `Save failed (${response.status})`);
          return;
        }
        if (data.queue) setQueue(data.queue);
        setQueueModal(null);
      }
    } catch (err: unknown) {
      setQueueModalError(err instanceof Error ? err.message : String(err));
    } finally {
      setQueueModalSaving(false);
    }
  };

  const onRemoveQueued = async (id: string, event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      const response = await fetch(`/api/simulation/queue/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      const data = (await response.json()) as SimQueue & { error?: string };
      if (!response.ok) {
        setError(data.error || `Remove failed (${response.status})`);
        return;
      }
      setQueue(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onReorderQueued = async (orderedIds: string[]) => {
    try {
      const response = await fetch("/api/simulation/queue/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: orderedIds }),
      });
      const data = (await response.json()) as SimQueue & { error?: string };
      if (!response.ok) {
        setError(data.error || `Reorder failed (${response.status})`);
        return;
      }
      setQueue(data);
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

  const onTogglePause = async () => {
    const nextPaused = !queuePaused;
    try {
      const response = await fetch("/api/simulation/queue/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paused: nextPaused }),
      });
      const data = (await response.json()) as {
        paused?: boolean;
        running?: boolean;
        queue?: SimQueue;
        error?: string;
      };
      if (!response.ok) {
        setError(data.error || `Pause failed (${response.status})`);
        return;
      }
      setQueuePaused(Boolean(data.paused));
      if (data.queue) setQueue(data.queue);
      if (data.running) {
        setRunning(true);
        openStream(false);
      } else if (!nextPaused) {
        openStream(false);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onClear = () => {
    if (running) return;
    setOutput("");
    setKeffLive(EMPTY_KEFF);
    setError(null);
  };

  const onCopyOutput = async () => {
    if (!output) return;
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const showKeffPanel = running || keffLive.value != null || keffLive.percent != null;
  const progressPercent =
    keffLive.percent != null && Number.isFinite(keffLive.percent)
      ? Math.max(0, Math.min(100, keffLive.percent))
      : running
        ? 0
        : null;

  const runningItems = queue.items.filter((item) => item.status === "running");
  const queuedItems = queue.items.filter((item) => item.status === "queued");
  const pastItems = queue.items
    .filter(
      (item) =>
        item.status === "done" || item.status === "failed" || item.status === "cancelled",
    )
    .slice()
    .reverse();

  const queueStatusLabel = (status: QueueItemStatus) => {
    switch (status) {
      case "running":
        return "running";
      case "queued":
        return "queued";
      case "done":
        return "done";
      case "failed":
        return "failed";
      case "cancelled":
        return "stopped";
      default:
        return status;
    }
  };

  const moveQueued = (fromId: string, toId: string) => {
    if (fromId === toId) return;
    const ids = queuedItems.map((item) => item.id);
    const from = ids.indexOf(fromId);
    const to = ids.indexOf(toId);
    if (from < 0 || to < 0) return;
    const next = [...ids];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    void onReorderQueued(next);
  };

  return (
    <Row className="g-3 simulation-tab">
      <Col lg={4}>
        <div className="border rounded p-3 bg-white h-100 d-flex flex-column simulation-queue-card">
          <div className="d-flex justify-content-between align-items-baseline mb-2">
            <h2 className="h6 mb-0">Run queue</h2>
            <span className="small text-secondary">
              {runningItems.length + queuedItems.length} active
              {queuePaused ? " · paused" : ""}
            </span>
          </div>
          <p className="small text-secondary mb-2">
            Runs <code>simulation_app_slice.py</code> in Docker with the current calculator geometry.
            Append configures each job.
          </p>
          <ol className="simulation-run-list-items list-unstyled mb-2 flex-grow-1">
            {runningItems.map((item, index) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="simulation-run-list-item is-running"
                  onClick={() => void openQueueItem(item)}
                >
                  <span className="simulation-run-list-index font-monospace">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="simulation-run-list-label">{item.label}</span>
                  <span className={`simulation-run-list-status status-${item.status}`}>
                    {queueStatusLabel(item.status)}
                  </span>
                </button>
              </li>
            ))}
            {queuedItems.map((item, index) => (
              <li
                key={item.id}
                draggable
                onDragStart={() => setDragQueuedId(item.id)}
                onDragEnd={() => setDragQueuedId(null)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  if (dragQueuedId) moveQueued(dragQueuedId, item.id);
                  setDragQueuedId(null);
                }}
              >
                <div
                  className={`simulation-run-list-item is-queued${dragQueuedId === item.id ? " is-dragging" : ""}`}
                >
                  <button
                    type="button"
                    className="simulation-run-list-main"
                    onClick={() => void openQueueItem(item)}
                  >
                    <span className="simulation-run-list-index font-monospace">
                      {String(runningItems.length + index + 1).padStart(2, "0")}
                    </span>
                    <span className="simulation-run-list-label">{item.label}</span>
                    <span className={`simulation-run-list-status status-${item.status}`}>
                      {queueStatusLabel(item.status)}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="simulation-run-list-remove"
                    aria-label={`Remove ${item.label}`}
                    onClick={(event) => void onRemoveQueued(item.id, event)}
                  >
                    ×
                  </button>
                </div>
              </li>
            ))}
            {runningItems.length === 0 && queuedItems.length === 0 && (
              <li className="small text-secondary px-1">No active runs. Append one below.</li>
            )}
          </ol>
          {pastItems.length > 0 && (
            <div className="simulation-run-list-past mb-2">
              <div className="small text-secondary mb-1">Past simulations</div>
              <ol className="simulation-run-list-items list-unstyled mb-0">
                {pastItems.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="simulation-run-list-item is-past"
                      onClick={() => void openQueueItem(item)}
                    >
                      <span className="simulation-run-list-index font-monospace">·</span>
                      <span className="simulation-run-list-label">{item.label}</span>
                      <span className={`simulation-run-list-status status-${item.status}`}>
                        {queueStatusLabel(item.status)}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div className="d-flex flex-wrap gap-2 mt-auto pt-2">
            <Button variant="primary" size="sm" onClick={openAppendModal}>
              Append
            </Button>
            <Button
              variant="outline-primary"
              size="sm"
              onClick={() => {
                setFastError(null);
                setFastOpen(true);
              }}
            >
              Fast simulation
            </Button>
            <Button
              variant="outline-danger"
              size="sm"
              disabled={!running}
              onClick={() => void onStop()}
            >
              Stop
            </Button>
            <Button
              variant={queuePaused ? "warning" : "outline-secondary"}
              size="sm"
              onClick={() => void onTogglePause()}
              title={
                queuePaused
                  ? "Resume auto-starting the next queued run"
                  : "Keep the current run, but do not start the next ones"
              }
            >
              {queuePaused ? "Resume" : "Pause"}
            </Button>
          </div>
          {error && (
            <Alert variant="danger" className="py-2 px-3 small mt-3 mb-0">
              {error}
            </Alert>
          )}
        </div>
      </Col>

      <Col lg={8}>
        <div className="border rounded p-3 bg-white h-100 d-flex flex-column simulation-output-card">
          <div className="d-flex justify-content-between align-items-baseline mb-2">
            <h2 className="h6 mb-0">Simulation output</h2>
            <div className="d-flex align-items-center gap-2">
              <span className="small text-secondary">
                {running ? "live" : output ? "idle" : "empty"}
                {queuePaused ? " · queue paused" : ""}
              </span>
              <Button
                variant="outline-secondary"
                size="sm"
                disabled={!output}
                onClick={() => void onCopyOutput()}
              >
                {copied ? "Copied" : "Copy"}
              </Button>
              <Button
                variant="outline-secondary"
                size="sm"
                disabled={running || !output}
                onClick={onClear}
              >
                Clear
              </Button>
            </div>
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
            {output || "Append a run to stream RIMAG stdout here."}
          </pre>
        </div>
      </Col>

      <FastSlabModal
        show={fastOpen}
        setup={setup}
        params={params}
        saving={fastSaving}
        error={fastError}
        onHide={() => {
          if (fastSaving) return;
          setFastOpen(false);
          setFastError(null);
        }}
        onAppend={(simulation) => void appendFast(simulation)}
      />

      {queueModal && (
        <RunQueueModal
          show
          mode={queueModal.mode}
          title={queueModal.title}
          setup={setup}
          initialSimulation={queueModal.simulation}
          defaultThermalPowerMw={defaultThermalPowerMw}
          wwPresent={Boolean(wwStatus?.present)}
          result={queueModal.result}
          exitCode={queueModal.exitCode}
          statusLabel={queueModal.statusLabel}
          startedAt={queueModal.startedAt}
          saving={queueModalSaving}
          error={queueModalError}
          onHide={() => {
            if (queueModalSaving) return;
            setQueueModal(null);
            setQueueModalError(null);
          }}
          onSubmit={(simulation) => void onQueueModalSubmit(simulation)}
        />
      )}
    </Row>
  );
};

export default SimulationTab;
