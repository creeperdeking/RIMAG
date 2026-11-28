import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  containersToStop,
  protectedContainerNames,
  weightWindowWriteBelongsToPass,
} from "./containerPolicy";
import {
  appendQueued,
  beginRunning,
  ensureRunningPlaceholder,
  getQueueItem,
  markFinished,
  markRunning,
  peekNextQueued,
  queueSnapshot,
  readQueuePaused,
  reconcileAfterRestart,
  rememberContainer,
  removeQueued,
  showLiveContainer,
  reorderQueued,
  saveQueue,
  updateQueuedPayload,
  writeQueuePaused,
  type QueueItem,
  type QueueItemResult,
  type SimQueueState,
} from "./simQueue";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const RUN_DIR = path.resolve(REPO_ROOT, "runs", "default");
const PARAMS_FILE = "app_slice_run.json";
/** Identifies this loaded module. A Vite reload starts a new one; stale sweeps must stop. */
const RUNNER_EPOCH_FILE = path.join(RUN_DIR, "runner.epoch");
const RUNNER_EPOCH = randomUUID();
const RESULTSIM_FILE = "resultsim.json";
/** Prefix for one-off sim containers (Stop / adopt match this). */
const CONTAINER_PREFIX = "rimag-app-sim";
/** Legacy fixed name still cleaned up on launch. */
const CONTAINER_NAME = CONTAINER_PREFIX;

export class RimagRunnerError extends Error {}

type JobState = {
  child: ChildProcessWithoutNullStreams | null;
  listeners: Set<(line: string) => void>;
  queueListeners: Set<(queue: SimQueueState) => void>;
  running: boolean;
  lastLines: string[];
  currentId: string | null;
  /** Container that is actually transporting. Empty until it is visible. */
  containerName: string;
  /** Name passed to compose that is not confirmed in `docker ps` yet. */
  pendingContainerName: string;
  /** `Date.now()` immediately before this pass's container was spawned. */
  passStartedAt: number;
  /** Monotonic id so overlapping launch/end callbacks ignore stale work. */
  launchGen: number;
  /** When true, the next job end does not start the following queued run (Stop). */
  suppressQueueAdvance: boolean;
  /** When true, finished runs do not auto-start the next queued item (Pause). */
  queuePaused: boolean;
  /** Completed refine passes for the current autorefine queue item. */
  autoRefinePass: number;
};

const job: JobState = {
  child: null,
  listeners: new Set(),
  queueListeners: new Set(),
  running: false,
  lastLines: [],
  currentId: null,
  containerName: "",
  pendingContainerName: "",
  passStartedAt: 0,
  launchGen: 0,
  suppressQueueAdvance: false,
  queuePaused: readQueuePaused(),
  autoRefinePass: 0,
};

/** Serialize remove+spawn so `docker rm -f` cannot SIGKILL a just-started peer. */
let launchChain: Promise<void> = Promise.resolve();

const AUTOREFINE_TARGET = 0.8;
const AUTOREFINE_MAX_PASSES = 50;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function claimRunnerEpoch() {
  fs.mkdirSync(RUN_DIR, { recursive: true });
  fs.writeFileSync(RUNNER_EPOCH_FILE, `${RUNNER_EPOCH}\n`, "utf8");
}

/** False after a newer copy of this module has been loaded in the same process. */
function runnerEpochIsCurrent(): boolean {
  try {
    return fs.readFileSync(RUNNER_EPOCH_FILE, "utf8").trim() === RUNNER_EPOCH;
  } catch {
    return false;
  }
}

claimRunnerEpoch();

function runDocker(args: string[]): Promise<number> {
  return new Promise((resolve) => {
    const child = spawn("docker", args, {
      cwd: REPO_ROOT,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stderr = "";
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      emit(`[runner] docker ${args.join(" ")} failed: ${error.message}`);
      resolve(1);
    });
    child.on("close", (code) => {
      if (code !== 0 && stderr.trim()) {
        emit(`[runner] docker ${args.join(" ")}: ${stderr.trim()}`);
      }
      resolve(code ?? 1);
    });
  });
}

async function containerExists(): Promise<boolean> {
  const names = await listSimContainerNames();
  return names.length > 0;
}

async function listSimContainerNames(): Promise<string[]> {
  return new Promise((resolve) => {
    const child = spawn(
      "docker",
      // Running containers only. `-q` hides --format and returns ids, which then
      // fail the name check, so leftover runs were never stopped.
      ["ps", "--filter", `name=${CONTAINER_PREFIX}`, "--format", "{{.Names}}"],
      { windowsHide: true, stdio: ["ignore", "pipe", "ignore"] },
    );
    let out = "";
    child.stdout.on("data", (chunk: Buffer) => {
      out += chunk.toString("utf8");
    });
    child.on("error", () => resolve([]));
    child.on("close", () => {
      resolve(
        out
          .split(/\r?\n/)
          .map((n) => n.trim())
          .filter(
            (n) =>
              n === CONTAINER_NAME ||
              n.startsWith(`${CONTAINER_PREFIX}-`),
          ),
      );
    });
  });
}

/**
 * Remove any leftover `rimag-app-sim*` containers before a new compose run.
 * Serialized via launchChain so we never `rm -f` a container we just started.
 */
async function removeSimContainers(protect: readonly string[] = []) {
  if (!runnerEpochIsCurrent()) return;
  const keep = new Set(protect.filter((name) => name.length > 0));
  for (let attempt = 1; attempt <= 20; attempt++) {
    const names = await listSimContainerNames();
    const targets =
      names.length > 0
        ? containersToStop(names, [...keep])
        : keep.has(CONTAINER_NAME)
          ? []
          : [CONTAINER_NAME];
    for (const name of targets) {
      await runDocker(["rm", "-f", name]);
    }
    const left = containersToStop(await listSimContainerNames(), [...keep]);
    if (left.length === 0) return;
    if (attempt === 1 || attempt % 5 === 0) {
      emit(`[runner] Waiting for ${CONTAINER_PREFIX}* to release (attempt ${attempt})…`);
    }
    await sleep(500);
  }
  emit(`[runner] warning: ${CONTAINER_PREFIX}* still present after retries; next compose run may fail`);
}

function emit(line: string) {
  job.lastLines.push(line);
  if (job.lastLines.length > 2000) job.lastLines.splice(0, job.lastLines.length - 2000);
  for (const listener of job.listeners) listener(line);
}

function emitQueue() {
  const snapshot = queueSnapshot();
  for (const listener of job.queueListeners) listener(snapshot);
}

export function getSimulationQueue(): SimQueueState {
  const state = queueSnapshot();
  let changed = false;
  for (const item of state.items) {
    const next = backfillWwCoverage(item);
    if (next.result !== item.result) changed = true;
  }
  return changed ? queueSnapshot() : state;
}

export function subscribeQueue(listener: (queue: SimQueueState) => void) {
  job.queueListeners.add(listener);
  listener(queueSnapshot());
  return () => job.queueListeners.delete(listener);
}

function isAccessError(error: unknown): boolean {
  const code =
    typeof error === "object" && error !== null && "code" in error
      ? (error as NodeJS.ErrnoException).code
      : undefined;
  return code === "EACCES" || code === "EPERM";
}

/** Bytecode left by the root OpenMC container. It is not source and must not be copied. */
function shouldSkipCopyName(name: string): boolean {
  return name === "__pycache__" || name.endsWith(".pyc") || name.endsWith(".pyo");
}

function copyFileReplacing(src: string, dest: string) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  try {
    fs.copyFileSync(src, dest);
  } catch (error) {
    if (!isAccessError(error) || !fs.existsSync(dest)) throw error;
    // The container runs as root and leaves mode-644 files behind. Opening
    // those with O_TRUNC fails; the directory is ours, so unlink then copy.
    fs.rmSync(dest, { force: true });
    fs.copyFileSync(src, dest);
  }
}

function copyDir(src: string, dest: string) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (shouldSkipCopyName(entry.name)) continue;
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(from, to);
    else if (entry.isFile()) copyFileReplacing(from, to);
  }
}

/** Keep the mounted run directory's Python packages in sync with the repo. */
export function syncRimagSourcesIntoRunDir() {
  fs.mkdirSync(RUN_DIR, { recursive: true });
  // entrypoint.sh copies /opt/rimag → /work only when simulation_app_slice.py
  // is missing. Copying it first keeps a fresh run directory from being
  // replaced by the image tree.
  const pairs: Array<[string, string]> = [
    ["simulation_app_slice.py", "simulation_app_slice.py"],
    ["plot_geometry_slice.py", "plot_geometry_slice.py"],
    ["app_slice_design", "app_slice_design"],
    ["common_lib", "common_lib"],
    ["one_layer_disk_design", "one_layer_disk_design"],
  ];
  for (const [from, to] of pairs) {
    const src = path.join(REPO_ROOT, from);
    const dest = path.join(RUN_DIR, to);
    if (!fs.existsSync(src)) {
      throw new RimagRunnerError(`Missing source path ${src}`);
    }
    if (fs.statSync(src).isDirectory()) copyDir(src, dest);
    else copyFileReplacing(src, dest);
  }
}

/** Refresh only the plot script. Safe while a simulation is using the other copies. */
export function syncPlotScriptIntoRunDir() {
  fs.mkdirSync(RUN_DIR, { recursive: true });
  const src = path.join(REPO_ROOT, "plot_geometry_slice.py");
  const dest = path.join(RUN_DIR, "plot_geometry_slice.py");
  if (!fs.existsSync(src)) {
    throw new RimagRunnerError(`Missing ${src}`);
  }
  copyFileReplacing(src, dest);
}

export function writeRunParams(payload: unknown) {
  syncRimagSourcesIntoRunDir();
  const target = path.join(RUN_DIR, PARAMS_FILE);
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return target;
}

export function isQueuePaused() {
  return job.queuePaused;
}

export function setQueuePaused(paused: boolean): { paused: boolean; running: boolean } {
  job.queuePaused = paused;
  writeQueuePaused(paused);
  if (paused) {
    emit("[runner] Queue paused — current run continues; next items will not start automatically.");
  } else {
    emit("[runner] Queue resumed.");
    if (!job.running) maybeStartNextFromQueue();
  }
  emitQueue();
  return { paused: job.queuePaused, running: job.running };
}

export function isSimulationRunning() {
  return job.running;
}

async function resolveRunningSimContainer(): Promise<string | null> {
  const preferred = job.containerName;
  const names = await listSimContainerNames();
  const ordered = preferred && !names.includes(preferred) ? [preferred, ...names] : names;
  for (const name of ordered.length > 0 ? ordered : [preferred || CONTAINER_NAME]) {
    const running = await new Promise<boolean>((resolve) => {
      const child = spawn("docker", ["inspect", "-f", "{{.State.Running}}", name], {
        windowsHide: true,
        stdio: ["ignore", "pipe", "ignore"],
      });
      let out = "";
      child.stdout.on("data", (chunk: Buffer) => {
        out += chunk.toString("utf8");
      });
      child.on("error", () => resolve(false));
      child.on("close", (code) => resolve(code === 0 && out.trim() === "true"));
    });
    if (running) return name;
  }
  return null;
}

async function containerIsRunning(): Promise<boolean> {
  return (await resolveRunningSimContainer()) != null;
}

function forwardProcessOutput(child: ChildProcessWithoutNullStreams) {
  const forward = (chunk: Buffer) => {
    const text = chunk.toString("utf8");
    for (const line of text.split(/\r\n|\n|\r/)) {
      if (line.length) emit(line);
    }
  };
  child.stdout.on("data", forward);
  child.stderr.on("data", forward);
}

let adopting: Promise<void> | null = null;
let reconcileChain: Promise<void> = Promise.resolve();

function logsShowFinalKeff(): boolean {
  return job.lastLines.some((line) =>
    /k-effective\s*\([^)]+\)\s*=\s*[0-9.]+\s*\+\/-\s*[0-9.]+/i.test(line),
  );
}

function inspectExitCode(name: string): Promise<number> {
  return new Promise((resolve) => {
    const child = spawn("docker", ["inspect", "-f", "{{.State.ExitCode}}", name], {
      windowsHide: true,
      stdio: ["ignore", "pipe", "ignore"],
    });
    let out = "";
    child.stdout.on("data", (chunk: Buffer) => {
      out += chunk.toString("utf8");
    });
    child.on("error", () => resolve(1));
    child.on("close", (code) => {
      if (code !== 0) {
        resolve(1);
        return;
      }
      const parsed = Number(out.trim());
      resolve(Number.isFinite(parsed) ? parsed : 1);
    });
  });
}

function followContainerLogs(name: string, launchGen = job.launchGen) {
  if (!runnerEpochIsCurrent() || !job.running) return;
  job.containerName = name;
  const current = job.child;
  if (
    current &&
    current.exitCode == null &&
    !current.killed &&
    current.spawnargs.includes(name)
  ) {
    return;
  }
  const child = spawn("docker", ["logs", "-f", "--tail", "400", name], {
    windowsHide: true,
  });
  job.child = child;
  forwardProcessOutput(child);
  child.on("error", (error) => {
    emit(`[runner] log follow failed: ${error.message}`);
  });
  child.on("close", () => {
    void (async () => {
      if (!runnerEpochIsCurrent() || job.launchGen !== launchGen || !job.running) return;
      const names = await listSimContainerNames();
      if (names.includes(name)) return;
      const code = logsShowFinalKeff() ? 0 : await inspectExitCode(name);
      onJobEnded(code, launchGen);
    })();
  });
}

/**
 * The queue is one run at a time. A container the queue does not call running is
 * stopped. A container that is still transporting is shown as the running item
 * instead of being ignored while another run starts.
 */
function keepNames(): string[] {
  const runningItem = queueSnapshot().items.find((entry) => entry.status === "running");
  return protectedContainerNames({
    live: job.containerName,
    pending: job.pendingContainerName,
    queuedRunning: runningItem?.containerName,
  });
}

function reconcileContainers(): Promise<void> {
  const run = async () => {
    if (!runnerEpochIsCurrent()) return;
    const names = await listSimContainerNames();
    if (
      job.pendingContainerName &&
      names.includes(job.pendingContainerName) &&
      job.running
    ) {
      job.containerName = job.pendingContainerName;
      job.pendingContainerName = "";
      if (job.currentId) rememberContainer(job.currentId, job.containerName);
    }
    if (job.running) {
      const protect = keepNames();
      if (protect.length === 0 && names.length > 0) {
        job.containerName = names[0];
        if (job.currentId) rememberContainer(job.currentId, names[0]);
      }
      for (const name of containersToStop(names, keepNames())) {
        await runDocker(["rm", "-f", name]);
      }
      return;
    }
    if (names.length === 0) return;
    const state = queueSnapshot();
    const cancelled = new Set(
      state.items
        .filter((item) => item.status === "cancelled" && item.containerName)
        .map((item) => item.containerName as string),
    );
    for (const name of names) {
      if (cancelled.has(name)) await runDocker(["rm", "-f", name]);
    }
    const live = (await listSimContainerNames()).filter((name) => !cancelled.has(name));
    if (live.length === 0) return;
    const runningItem = state.items.find((entry) => entry.status === "running");
    const show =
      runningItem?.containerName && live.includes(runningItem.containerName)
        ? runningItem.containerName
        : live[0];
    for (const name of live) {
      if (name !== show) await runDocker(["rm", "-f", name]);
    }
    let item = showLiveContainer(show);
    if (!item) {
      ensureRunningPlaceholder(null, true);
      item = queueSnapshot().items.find((entry) => entry.status === "running") ?? null;
      if (item) rememberContainer(item.id, show);
    }
    if (!item || job.running) return;
    job.running = true;
    job.suppressQueueAdvance = false;
    job.currentId = item.id;
    job.containerName = show;
    job.pendingContainerName = "";
    emit(
      `[runner] ${show} is still running. Showing ${item.label} instead of starting another run.`,
    );
    emitQueue();
    followContainerLogs(show);
  };
  reconcileChain = reconcileChain.catch(() => undefined).then(run);
  return reconcileChain;
}

const containerSweep = setInterval(() => {
  if (!runnerEpochIsCurrent()) {
    clearInterval(containerSweep);
    return;
  }
  void reconcileContainers();
}, 15_000);
containerSweep.unref?.();

/**
 * The Vite server keeps the run only in memory. A server restart drops that
 * state while `rimag-app-sim` keeps transporting. Follow its logs again.
 * Also resumes the disk queue when the container is gone but jobs remain.
 */
export function adoptRunningSimulation(): Promise<void> {
  if (adopting) return adopting;
  adopting = reconcileContainers()
    .then(() => {
      if (job.running) return;
      return containerIsRunning();
    })
    .then((alive) => {
      if (alive == null || job.running) return;
      reconcileAfterRestart(alive);
      if (alive) {
        const paramsPath = path.join(RUN_DIR, PARAMS_FILE);
        let payload: unknown = null;
        try {
          if (fs.existsSync(paramsPath)) {
            payload = JSON.parse(fs.readFileSync(paramsPath, "utf8"));
          }
        } catch {
          payload = null;
        }
        ensureRunningPlaceholder(payload, true);
        const runningItem = queueSnapshot().items.find((item) => item.status === "running");
        job.currentId = runningItem?.id ?? null;
        emitQueue();
        if (job.running) return;
        job.running = true;
        job.lastLines = [];
        void resolveRunningSimContainer().then((name) => {
          if (!name || !job.running) return;
          if (job.currentId) rememberContainer(job.currentId, name);
          emit(
            `[runner] Reattached to ${name}. The app server restarted and lost the log; the run is still going.`,
          );
          followContainerLogs(name);
        });
        return;
      }
      emitQueue();
      maybeStartNextFromQueue();
    })
    .catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      emit(`[runner] failed while adopting a run: ${message}`);
    })
    .finally(() => {
      adopting = null;
    });
  return adopting;
}

export function subscribe(listener: (line: string) => void) {
  job.listeners.add(listener);
  for (const line of job.lastLines) listener(line);
  return () => job.listeners.delete(listener);
}

/**
 * Interrupt like Ctrl+C: SIGINT to PID 1 inside the container.
 * On Windows, kill() on the compose client does not send Unix signals.
 * Queued runs stay on disk; they do not start until Append/Start kicks the queue again.
 */
function simulationRecordFromPayload(payload: unknown): Record<string, unknown> {
  const root =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : {};
  if (root.simulation && typeof root.simulation === "object" && !Array.isArray(root.simulation)) {
    return root.simulation as Record<string, unknown>;
  }
  return root;
}

function wwModeFromPayload(payload: unknown): string {
  return String(simulationRecordFromPayload(payload).weight_windows ?? "no");
}

function isAutoRefinePayload(payload: unknown): boolean {
  return wwModeFromPayload(payload) === "autorefine";
}

/** Map queue-only modes (autorefine) to what simulation_app_slice.py accepts. */
function payloadForRunner(payload: unknown): unknown {
  if (!isAutoRefinePayload(payload)) return payload;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return payload;
  const root = payload as Record<string, unknown>;
  if (root.simulation && typeof root.simulation === "object" && !Array.isArray(root.simulation)) {
    return {
      ...root,
      simulation: {
        ...(root.simulation as Record<string, unknown>),
        weight_windows: "refine",
      },
    };
  }
  return { ...root, weight_windows: "refine" };
}

function gammaFromLogs(): Pick<QueueItemResult, "gammaKGy" | "gammaCi95Pct" | "gammaYears"> | null {
  const lineRe =
    /InGaAs gamma dose:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*kGy\s+over\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s+years\s+\((?:±|\+\/-)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|nan)%\s*,\s*95%\s*CI\)/i;
  for (let i = job.lastLines.length - 1; i >= 0; i -= 1) {
    const match = job.lastLines[i].match(lineRe);
    if (!match) continue;
    const gammaKGy = Number(match[1]);
    const gammaYears = Number(match[2]);
    const gammaCi95Pct = match[3].toLowerCase() === "nan" ? null : Number(match[3]);
    if (!Number.isFinite(gammaKGy) || !Number.isFinite(gammaYears)) continue;
    return {
      gammaKGy,
      gammaYears,
      gammaCi95Pct: gammaCi95Pct != null && Number.isFinite(gammaCi95Pct) ? gammaCi95Pct : null,
    };
  }
  return null;
}

function runModeFromPayload(payload: unknown): string {
  return String(simulationRecordFromPayload(payload).run_mode ?? "");
}

function gammaFromResultsim(
  item: QueueItem,
): Pick<QueueItemResult, "gammaKGy" | "gammaCi95Pct" | "gammaYears"> | null {
  const file = path.join(RUN_DIR, RESULTSIM_FILE);
  if (!fs.existsSync(file)) return null;
  const stat = fs.statSync(file);
  const started = item.startedAt ? Date.parse(item.startedAt) : NaN;
  const finished = item.finishedAt ? Date.parse(item.finishedAt) : Date.now();
  if (Number.isFinite(started) && stat.mtimeMs < started - 5000) return null;
  if (Number.isFinite(finished) && stat.mtimeMs > finished + 120_000) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
  const record = parsed as Record<string, unknown>;
  if (record.kind !== "gamma_dose") return null;
  const batches = simulationRecordFromPayload(item.payload).n_batches;
  if (typeof batches === "number" && record.n_batches !== batches) return null;
  const raw = Array.isArray(record.gamma_kgy) ? record.gamma_kgy[0] : record.gamma_kgy;
  const gammaKGy = Number(raw);
  const years = Number(record.gamma_years);
  const fraction = record.gamma_ci95p == null ? NaN : Number(record.gamma_ci95p);
  if (!Number.isFinite(gammaKGy)) return null;
  return {
    gammaKGy,
    gammaYears: Number.isFinite(years) ? years : null,
    gammaCi95Pct: Number.isFinite(fraction) ? fraction * 100 : null,
  };
}

function attachStoredGamma(result: QueueItemResult, item: QueueItem | null | undefined): QueueItemResult {
  const fromLogs = gammaFromLogs();
  if (fromLogs) return { ...result, ...fromLogs };
  if (!item || runModeFromPayload(item.payload) !== "keff_gamma_dose") return result;
  if (result.gammaKGy != null) return result;
  const fromFile = gammaFromResultsim(item);
  return fromFile ? { ...result, ...fromFile } : result;
}

function resultFromLogs(): QueueItemResult {
  // Prefer OpenMC's final combined keff line; fall back to the last progress k=.
  let keff: number | null = null;
  let keffUncertainty: number | null = null;
  let summary: string | null = null;
  for (let i = job.lastLines.length - 1; i >= 0; i -= 1) {
    const line = job.lastLines[i];
    const final = line.match(
      /k-effective\s*\([^)]+\)\s*=\s*([0-9.]+)\s*\+\/-\s*([0-9.]+)/i,
    );
    if (final) {
      keff = Number(final[1]);
      keffUncertainty = Number(final[2]);
      summary = line.replace(/^\[[^\]]+\]\s*/, "").trim();
      break;
    }
  }
  if (keff == null) {
    for (let i = job.lastLines.length - 1; i >= 0; i -= 1) {
      const line = job.lastLines[i];
      const progress = line.match(
        /\bk=([0-9.]+)(?:\s*\+\/-\s*([0-9.]+))?/i,
      );
      if (progress) {
        keff = Number(progress[1]);
        keffUncertainty = progress[2] != null ? Number(progress[2]) : null;
        summary = line.replace(/^\[[^\]]+\]\s*/, "").trim();
        break;
      }
    }
  }
  return { summary, keff, keffUncertainty };
}

function isWwBuildMode(mode: string): boolean {
  return mode === "seed" || mode === "refine" || mode === "autorefine" || mode === "generate";
}

function wwCoverageFields(): Pick<
  QueueItemResult,
  "ingaasReached" | "ingaasVoxels" | "ingaasReachFraction" | "ingaasEnergyFraction"
> {
  const ww = weightWindowsStatus();
  return {
    ingaasReached: ww.ingaasReached,
    ingaasVoxels: ww.ingaasVoxels,
    ingaasReachFraction: ww.ingaasReachFraction,
    ingaasEnergyFraction: ww.ingaasEnergyFraction,
  };
}

function attachWwCoverage(result: QueueItemResult, payload: unknown | null | undefined): QueueItemResult {
  if (!payload || !isWwBuildMode(wwModeFromPayload(payload))) return result;
  const coverage = wwCoverageFields();
  const frac = coverage.ingaasReachFraction;
  const reached =
    coverage.ingaasReached != null && coverage.ingaasVoxels != null
      ? `${coverage.ingaasReached}/${coverage.ingaasVoxels}`
      : null;
  const pct = frac != null ? `${(100 * frac).toFixed(0)}%` : null;
  let summary = result.summary ?? null;
  if (pct && !(summary && /ingaas/i.test(summary))) {
    const bit = `InGaAs ${pct}${reached ? ` (${reached})` : ""}`;
    summary = summary ? `${summary} · ${bit}` : bit;
  }
  return { ...result, ...coverage, summary };
}

function finishQueueItem(
  itemId: string | null,
  code: number,
  status: "done" | "failed" | "cancelled",
  result: QueueItemResult | null,
  advance: boolean,
) {
  const finishedContainer = job.containerName;
  markFinished(itemId, code, status, result);
  job.currentId = null;
  job.containerName = "";
  job.autoRefinePass = 0;
  emitQueue();
  emit(`[runner] done exit=${code}`);
  if (
    finishedContainer &&
    finishedContainer !== job.pendingContainerName &&
    runnerEpochIsCurrent()
  ) {
    void runDocker(["rm", "-f", finishedContainer]);
  }
  if (advance) maybeStartNextFromQueue();
}

function weightWindowsWrittenDuringPass(): boolean {
  if (!job.passStartedAt) return false;
  try {
    const metaPath = path.join(RUN_DIR, WW_META_FILE);
    if (!fs.existsSync(metaPath)) return false;
    return weightWindowWriteBelongsToPass(fs.statSync(metaPath).mtimeMs, job.passStartedAt);
  } catch {
    return false;
  }
}

function onJobEnded(code: number, endedGen?: number) {
  if (!runnerEpochIsCurrent()) return;
  if (endedGen != null && endedGen !== job.launchGen) {
    emit(`[runner] Ignoring stale job end (gen ${endedGen}, current ${job.launchGen}).`);
    return;
  }
  if (job.child && !job.child.killed) {
    try {
      job.child.kill();
    } catch {
      // ignore
    }
  }
  job.child = null;
  if (!job.running) return;
  job.running = false;
  const stopped = job.suppressQueueAdvance;
  job.suppressQueueAdvance = false;
  const itemId = job.currentId;
  const item = itemId ? getQueueItem(itemId) : null;

  // Exit 137 = SIGKILL. A refine that already wrote weight windows during THIS pass
  // can be torn down by container cleanup; a file left by the seed does not count.
  let effectiveCode = code;
  if (
    !stopped &&
    code === 137 &&
    item &&
    isAutoRefinePayload(item.payload) &&
    weightWindowsWrittenDuringPass()
  ) {
    emit(
      "[runner] Exit 137 after a fresh weight_windows write — treating refine pass as completed (SIGKILL during container teardown/relaunch).",
    );
    effectiveCode = 0;
  }

  if (!stopped && effectiveCode === 0 && item && isAutoRefinePayload(item.payload)) {
    job.autoRefinePass += 1;
    const ww = weightWindowsStatus();
    const frac = ww.ingaasReachFraction;
    const pctLabel = frac != null ? `${(100 * frac).toFixed(0)}%` : "unknown";
    const reached =
      ww.ingaasReached != null && ww.ingaasVoxels != null
        ? `${ww.ingaasReached}/${ww.ingaasVoxels}`
        : null;
    emit(
      `[runner] Autorefine pass ${job.autoRefinePass}: InGaAs ${reached ?? "—"} · ${pctLabel} (target ${(100 * AUTOREFINE_TARGET).toFixed(0)}%)`,
    );

    if (frac != null && frac >= AUTOREFINE_TARGET) {
      const base = attachWwCoverage(attachStoredGamma(resultFromLogs(), item), item.payload);
      finishQueueItem(
        itemId,
        0,
        "done",
        {
          ...base,
          summary: `Autorefine reached InGaAs ${pctLabel}${reached ? ` (${reached})` : ""} after ${job.autoRefinePass} pass${job.autoRefinePass === 1 ? "" : "es"}`,
        },
        true,
      );
      return;
    }

    if (job.autoRefinePass >= AUTOREFINE_MAX_PASSES) {
      const base = attachWwCoverage(attachStoredGamma(resultFromLogs(), item), item.payload);
      finishQueueItem(
        itemId,
        0,
        "done",
        {
          ...base,
          summary: `Autorefine stopped after ${AUTOREFINE_MAX_PASSES} passes (InGaAs ${pctLabel}; target ${(100 * AUTOREFINE_TARGET).toFixed(0)}%)`,
        },
        true,
      );
      return;
    }

    // Autorefine is one queue item: keep looping even if Pause is on (Pause only blocks the next item).
    emit("[runner] Autorefine: below target, starting another refine pass…");
    job.running = true;
    job.currentId = itemId;
    void sleep(2000).then(() => {
      if (job.currentId !== itemId) return;
      launchDockerJob(item.payload, item, { continueAutoRefine: true });
    });
    return;
  }

  const status = stopped ? "cancelled" : effectiveCode === 0 ? "done" : "failed";
  let result: QueueItemResult | null = stopped
    ? { summary: "Stopped by user" }
    : attachWwCoverage(attachStoredGamma(resultFromLogs(), item), item?.payload);

  // Autorefine must reach InGaAs coverage (or hit max passes as "done") before the
  // next queue item. A crashed/killed refine (e.g. exit 137) used to mark failed
  // and still advance — hold the queue instead.
  const autoRefineFailed =
    !stopped && status === "failed" && item != null && isAutoRefinePayload(item.payload);
  if (autoRefineFailed) {
    const frac = result?.ingaasReachFraction;
    const pct =
      frac != null ? `${(100 * frac).toFixed(0)}%` : "unknown";
    const reached =
      result?.ingaasReached != null && result?.ingaasVoxels != null
        ? `${result.ingaasReached}/${result.ingaasVoxels}`
        : null;
    const killHint =
      code === 137
        ? " · SIGKILL (often docker rm -f name clash or host OOM / IDE restart)"
        : "";
    result = {
      ...result,
      summary: `Autorefine failed (exit ${code}${killHint}) · InGaAs ${pct}${reached ? ` (${reached})` : ""} · target ${(100 * AUTOREFINE_TARGET).toFixed(0)}%`,
    };
    job.queuePaused = true;
    writeQueuePaused(true);
    emit(
      `[runner] Autorefine failed before InGaAs ≥ ${(100 * AUTOREFINE_TARGET).toFixed(0)}% (exit ${code}, coverage ${pct}${reached ? ` ${reached}` : ""}) — queue paused; next items will not start. Resume after fixing or re-queue autorefine.`,
    );
  }

  finishQueueItem(itemId, effectiveCode, status, result, !stopped && !autoRefineFailed);
}

export function stopSimulation(): boolean {
  if (!job.running && !job.child) return false;
  job.suppressQueueAdvance = true;
  emit("[runner] Stop: sending SIGINT to container (same as Ctrl+C)…");
  emit("[runner] Remaining queued runs stay waiting (use Resume if the queue is paused).");
  void (async () => {
    const name = (await resolveRunningSimContainer()) ?? job.containerName;
    const alive = name != null && (await containerIsRunning());
    if (!alive || !name) {
      emit(`[runner] Container ${CONTAINER_PREFIX}* is already gone.`);
      onJobEnded(0);
      return;
    }
    job.containerName = name;
    const code = await runDocker(["kill", "--signal=SIGINT", name]);
    if (code !== 0) {
      emit("[runner] SIGINT did not reach the container; forcing docker kill…");
      const killed = await runDocker(["kill", name]);
      if (killed !== 0) {
        emit(`[runner] Container ${name} is already gone.`);
        onJobEnded(0);
      }
    }
  })();
  return true;
}

function dockerComposeCommand(): { command: string; prefix: string[] } {
  // Prefer `docker compose` (v2). Fall back to docker-compose if needed at spawn time.
  return { command: "docker", prefix: ["compose"] };
}

function threadsFromPayload(payload: unknown): number {
  const root = payload && typeof payload === "object" && !Array.isArray(payload)
    ? (payload as Record<string, unknown>)
    : {};
  const simulation =
    root.simulation && typeof root.simulation === "object" && !Array.isArray(root.simulation)
      ? (root.simulation as Record<string, unknown>)
      : root;
  const raw = Number(simulation.n_threads);
  if (!Number.isFinite(raw)) return 10;
  return Math.max(1, Math.min(256, Math.round(raw)));
}

const WW_FILE = "weight_windows.h5";
const WW_META_FILE = "weight_windows_meta.json";

export type WeightWindowsStatus = {
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

function metaNumber(meta: Record<string, unknown>, key: string): number | null {
  const value = meta[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function weightWindowsStatus(): WeightWindowsStatus {
  const filePath = path.join(RUN_DIR, WW_FILE);
  const metaPath = path.join(RUN_DIR, WW_META_FILE);
  const present = fs.existsSync(filePath);
  let sizeBytes: number | null = null;
  if (present) {
    try {
      sizeBytes = fs.statSync(filePath).size;
    } catch {
      sizeBytes = null;
    }
  }
  let passes: number | null = null;
  let lastPass: string | null = null;
  let meshCm: number | null = null;
  let energyGroups: number | null = null;
  let batches: number | null = null;
  let updatedAt: string | null = null;
  let spatialCoverage: number | null = null;
  let energyCoverage: number | null = null;
  let outerCoverage: number | null = null;
  let decades: number | null = null;
  let reachYCm: number | null = null;
  let meshRMaxCm: number | null = null;
  let ingaasVoxels: number | null = null;
  let ingaasReached: number | null = null;
  let ingaasReachFraction: number | null = null;
  let ingaasEnergyFraction: number | null = null;
  if (fs.existsSync(metaPath)) {
    try {
      const meta = JSON.parse(fs.readFileSync(metaPath, "utf8")) as Record<string, unknown>;
      passes = typeof meta.passes === "number" ? meta.passes : null;
      lastPass = typeof meta.last_pass === "string" ? meta.last_pass : null;
      meshCm = typeof meta.mesh_cm === "number" ? meta.mesh_cm : null;
      energyGroups = typeof meta.energy_groups === "number" ? meta.energy_groups : null;
      batches = typeof meta.batches === "number" ? meta.batches : null;
      updatedAt = typeof meta.updated_at === "string" ? meta.updated_at : null;
      spatialCoverage = metaNumber(meta, "spatial_coverage");
      energyCoverage = metaNumber(meta, "energy_coverage");
      outerCoverage = metaNumber(meta, "outer_coverage");
      decades = metaNumber(meta, "decades");
      reachYCm = metaNumber(meta, "reach_y_cm");
      meshRMaxCm = metaNumber(meta, "mesh_r_max_cm");
      ingaasVoxels = metaNumber(meta, "ingaas_voxels");
      ingaasReached = metaNumber(meta, "ingaas_reached");
      ingaasReachFraction = metaNumber(meta, "ingaas_reach_fraction");
      ingaasEnergyFraction = metaNumber(meta, "ingaas_energy_fraction");
    } catch {
      // ignore corrupt meta
    }
  }
  return {
    present,
    sizeBytes,
    passes,
    lastPass,
    meshCm,
    energyGroups,
    batches,
    updatedAt,
    spatialCoverage,
    energyCoverage,
    outerCoverage,
    decades,
    reachYCm,
    meshRMaxCm,
    ingaasVoxels,
    ingaasReached,
    ingaasReachFraction,
    ingaasEnergyFraction,
  };
}

export function clearWeightWindows(): boolean {
  if (job.running) {
    throw new RimagRunnerError("Stop the simulation before clearing weight windows.");
  }
  let removed = false;
  for (const name of [WW_FILE, WW_META_FILE]) {
    const target = path.join(RUN_DIR, name);
    if (fs.existsSync(target)) {
      fs.unlinkSync(target);
      removed = true;
    }
  }
  return removed;
}

function failPreparedRun(item: QueueItem, error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  emit(`[runner] failed to prepare run: ${message}`);
  job.running = false;
  job.child = null;
  // Advance on a later turn so a run dir that still rejects the copy fails
  // each queued item without recursing on the stack or killing this process.
  finishQueueItem(item.id, 1, "failed", { summary: message }, false);
  queueMicrotask(() => {
    try {
      maybeStartNextFromQueue();
    } catch (nextError) {
      const nextMessage = nextError instanceof Error ? nextError.message : String(nextError);
      emit(`[runner] queue advance failed: ${nextMessage}`);
    }
  });
}

function launchDockerJob(
  payload: unknown,
  item: QueueItem,
  options: { continueAutoRefine?: boolean } = {},
) {
  if (!runnerEpochIsCurrent()) return;
  let runnerPayload: unknown;
  let threads: number;
  try {
    runnerPayload = payloadForRunner(payload);
    writeRunParams(runnerPayload);
    threads = threadsFromPayload(runnerPayload);
    fs.writeFileSync(
      path.join(RUN_DIR, "simsettings.json"),
      `${JSON.stringify({ threads }, null, 2)}\n`,
      "utf8",
    );
  } catch (error) {
    failPreparedRun(item, error);
    return;
  }
  job.lastLines = [];
  job.running = true;
  job.currentId = item.id;
  job.suppressQueueAdvance = false;
  if (!options.continueAutoRefine) {
    job.autoRefinePass = 0;
  }
  const launchGen = ++job.launchGen;
  const containerName = `${CONTAINER_PREFIX}-${Date.now().toString(36)}-${launchGen}`;
  job.pendingContainerName = containerName;
  emitQueue();

  const { command, prefix } = dockerComposeCommand();
  const args = [
    ...prefix,
    "run",
    "--name",
    containerName,
    "--rm",
    "-e",
    `RIMAG_THREADS=${threads}`,
    "rimag",
    "python",
    "simulation_app_slice.py",
    PARAMS_FILE,
  ];

  const autoNote =
    isAutoRefinePayload(payload) && !options.continueAutoRefine
      ? " · autorefine until InGaAs ≥ 80%"
      : isAutoRefinePayload(payload)
        ? ` · autorefine pass ${job.autoRefinePass + 1}`
        : "";
  emit(`[runner] queue item ${item.id.slice(0, 8)} · ${item.label}${autoNote}`);
  emit(`[runner] repo=${REPO_ROOT}`);
  emit(`[runner] run_dir=${RUN_DIR}`);
  emit(`[runner] threads=${threads}`);
  emit(`[runner] container=${containerName}`);
  emit(`[runner] ${command} ${args.join(" ")}`);

  launchChain = launchChain
    .catch(() => undefined)
    .then(async () => {
      if (!runnerEpochIsCurrent()) return;
      if (!job.running || job.currentId !== item.id || job.launchGen !== launchGen) return;
      await removeSimContainers([containerName]);
      if (!runnerEpochIsCurrent()) return;
      if (!job.running || job.currentId !== item.id || job.launchGen !== launchGen) return;
      job.passStartedAt = Date.now();
      const child = spawn(command, args, {
        cwd: REPO_ROOT,
        env: {
          ...process.env,
          RIMAG_RUN_DIR: RUN_DIR,
          RIMAG_THREADS: String(threads),
          PYTHONUNBUFFERED: "1",
        },
        windowsHide: true,
      });
      job.child = child;

      forwardProcessOutput(child);
      child.on("error", (error) => {
        emit(`[runner] failed to start: ${error.message}`);
        onJobEnded(1, launchGen);
      });
      child.on("close", (code, signal) => {
        void listSimContainerNames().then((names) => {
          if (
            names.includes(containerName) &&
            job.launchGen === launchGen &&
            job.currentId === item.id
          ) {
            emit(
              `[runner] ${containerName} is still running after the client exited. Showing that run.`,
            );
            followContainerLogs(containerName);
            return;
          }
          emit(`[runner] process closed code=${code ?? "null"} signal=${signal ?? "null"}`);
          onJobEnded(code ?? 1, launchGen);
        });
      });
    });
}

let startingNext = false;

function maybeStartNextFromQueue() {
  if (!runnerEpochIsCurrent()) return;
  if (job.running || startingNext) return;
  if (job.queuePaused) {
    emitQueue();
    return;
  }
  startingNext = true;
  void (async () => {
    try {
      if (job.running || job.queuePaused) return;
      const names = await listSimContainerNames();
      if (job.running || job.queuePaused) return;
      if (names.length > 0) {
        await reconcileContainers();
        return;
      }
      const next = peekNextQueued();
      if (!next) {
        emitQueue();
        return;
      }
      const marked = markRunning(next.id);
      if (!marked) return;
      emit(`[runner] Starting next queued run: ${marked.label}`);
      launchDockerJob(marked.payload, marked);
    } finally {
      startingNext = false;
    }
  })();
}

/** Start immediately with this payload (becomes the running queue item). */
export function startSimulation(payload: unknown): void {
  if (job.running) {
    throw new RimagRunnerError("A simulation is already running. Use Append to queue another.");
  }
  const item = beginRunning(payload);
  launchDockerJob(payload, item);
}

/**
 * Queue a run with the current calculator payload. Runs after the active job,
 * or starts now if nothing is running. Persisted in runs/default/sim_queue.json.
 */
export function appendSimulation(payload: unknown): QueueItem {
  // If a transport is already live but the disk queue has no "running" row
  // (e.g. started before the queue existed), register it so Append is #2.
  if (job.running) {
    const snap = queueSnapshot();
    if (!snap.items.some((entry) => entry.status === "running")) {
      const paramsPath = path.join(RUN_DIR, PARAMS_FILE);
      let currentPayload: unknown = null;
      try {
        if (fs.existsSync(paramsPath)) {
          currentPayload = JSON.parse(fs.readFileSync(paramsPath, "utf8"));
        }
      } catch {
        currentPayload = null;
      }
      ensureRunningPlaceholder(currentPayload, true);
      const runningItem = queueSnapshot().items.find((entry) => entry.status === "running");
      job.currentId = runningItem?.id ?? job.currentId;
    }
  }
  const item = appendQueued(payload);
  emit(`[runner] Appended to queue: ${item.label} (${item.id.slice(0, 8)})`);
  emitQueue();
  if (!job.running) maybeStartNextFromQueue();
  return item;
}

export function removeQueuedSimulation(id: string): SimQueueState {
  try {
    removeQueued(id);
  } catch (error: unknown) {
    throw new RimagRunnerError(error instanceof Error ? error.message : String(error));
  }
  emit(`[runner] Removed queued run ${id.slice(0, 8)}`);
  emitQueue();
  return queueSnapshot();
}

export function updateQueuedSimulation(id: string, payload: unknown): QueueItem {
  try {
    const item = updateQueuedPayload(id, payload);
    emit(`[runner] Updated queued run ${id.slice(0, 8)} · ${item.label}`);
    emitQueue();
    return item;
  } catch (error: unknown) {
    throw new RimagRunnerError(error instanceof Error ? error.message : String(error));
  }
}

export function reorderQueuedSimulations(orderedQueuedIds: string[]): SimQueueState {
  try {
    const state = reorderQueued(orderedQueuedIds);
    emit(`[runner] Reordered queued runs`);
    emitQueue();
    return state;
  } catch (error: unknown) {
    throw new RimagRunnerError(error instanceof Error ? error.message : String(error));
  }
}

function metaMatchesFinishedItem(item: QueueItem, ww: WeightWindowsStatus): boolean {
  if (!ww.updatedAt || !item.finishedAt) return false;
  const metaMs = Date.parse(ww.updatedAt);
  const finishedMs = Date.parse(item.finishedAt);
  if (!Number.isFinite(metaMs) || !Number.isFinite(finishedMs)) return false;
  // Meta is written near the end of the OpenMC job; allow a few minutes of skew.
  return Math.abs(metaMs - finishedMs) <= 15 * 60 * 1000;
}

/** Fill InGaAs coverage on older WW build results from weight_windows_meta.json when it matches. */
function backfillWwCoverage(item: QueueItem): QueueItem {
  if (item.status !== "done" && item.status !== "failed") return item;
  if (!isWwBuildMode(wwModeFromPayload(item.payload))) return item;
  if (item.result?.ingaasReachFraction != null) return item;
  const ww = weightWindowsStatus();
  if (ww.ingaasReachFraction == null) return item;
  const mode = wwModeFromPayload(item.payload);
  if (mode === "seed" && ww.lastPass && ww.lastPass !== "seed") return item;
  if ((mode === "refine" || mode === "autorefine") && ww.lastPass && ww.lastPass !== "refine") return item;
  if (!metaMatchesFinishedItem(item, ww)) return item;
  const enriched = attachWwCoverage(item.result ?? {}, item.payload);
  const state = queueSnapshot();
  const index = state.items.findIndex((entry) => entry.id === item.id);
  if (index >= 0) {
    state.items[index] = { ...state.items[index], result: enriched };
    saveQueue(state);
  }
  return { ...item, result: enriched };
}

function backfillGamma(item: QueueItem): QueueItem {
  if (item.status !== "done") return item;
  if (runModeFromPayload(item.payload) !== "keff_gamma_dose") return item;
  if (item.result?.gammaKGy != null) return item;
  const gamma = gammaFromResultsim(item);
  if (!gamma) return item;
  const state = queueSnapshot();
  const index = state.items.findIndex((entry) => entry.id === item.id);
  if (index < 0) return { ...item, result: { ...(item.result ?? {}), ...gamma } };
  const current = state.items[index];
  if (current.result?.gammaKGy != null) return current;
  const result = { ...(current.result ?? {}), ...gamma };
  state.items[index] = { ...current, result };
  saveQueue(state);
  return state.items[index];
}

export function readQueueItem(id: string): QueueItem | null {
  const item = getQueueItem(id);
  return item ? backfillGamma(backfillWwCoverage(item)) : null;
}
