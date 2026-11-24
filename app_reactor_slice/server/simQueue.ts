import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const RUN_DIR = path.resolve(REPO_ROOT, "runs", "default");
const QUEUE_FILE = path.join(RUN_DIR, "sim_queue.json");
const MAX_HISTORY = 100;

export type QueueItemStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export type QueueItemResult = {
  summary?: string | null;
  keff?: number | null;
  keffUncertainty?: number | null;
  /** InGaAs MAGIC mesh coverage after seed/refine (fraction 0–1). */
  ingaasReached?: number | null;
  ingaasVoxels?: number | null;
  ingaasReachFraction?: number | null;
  ingaasEnergyFraction?: number | null;
};

export type QueueItem = {
  id: string;
  status: QueueItemStatus;
  label: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  exitCode: number | null;
  payload: unknown;
  result?: QueueItemResult | null;
};

export type SimQueueState = {
  items: QueueItem[];
};

function nowIso() {
  return new Date().toISOString();
}

export function labelFromPayload(payload: unknown): string {
  const root =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : {};
  const simulation =
    root.simulation && typeof root.simulation === "object" && !Array.isArray(root.simulation)
      ? (root.simulation as Record<string, unknown>)
      : root;
  const mode = String(simulation.run_mode ?? "keff");
  const ww = String(simulation.weight_windows ?? "no");
  const batches = simulation.n_batches;
  const pitch = simulation.conical_pitch;
  const bits = [mode];
  if (ww && ww !== "no") {
    bits.push(ww === "autorefine" ? "ww=autorefine→80%" : `ww=${ww}`);
  }
  if (typeof batches === "number" && Number.isFinite(batches)) bits.push(`${batches} batches`);
  if (typeof pitch === "number" && Number.isFinite(pitch)) bits.push(`${pitch}°`);
  const setup =
    root.setup && typeof root.setup === "object" && !Array.isArray(root.setup)
      ? (root.setup as Record<string, unknown>)
      : {};
  const overrideMw = simulation.thermal_power_mw;
  const thermalW = setup.period_thermal_w;
  if (typeof overrideMw === "number" && Number.isFinite(overrideMw) && overrideMw > 0) {
    bits.push(`${Number(overrideMw.toPrecision(4))} MWₜₕ`);
  } else if (typeof thermalW === "number" && Number.isFinite(thermalW) && thermalW > 0) {
    bits.push(`${Number((thermalW / 1e6).toPrecision(4))} MWₜₕ/period`);
  }
  return bits.join(" · ");
}

export function loadQueue(): SimQueueState {
  try {
    if (!fs.existsSync(QUEUE_FILE)) return { items: [] };
    const parsed = JSON.parse(fs.readFileSync(QUEUE_FILE, "utf8")) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return { items: [] };
    const items = (parsed as { items?: unknown }).items;
    if (!Array.isArray(items)) return { items: [] };
    return {
      items: items.filter(
        (item): item is QueueItem =>
          !!item &&
          typeof item === "object" &&
          typeof (item as QueueItem).id === "string" &&
          typeof (item as QueueItem).status === "string",
      ),
    };
  } catch {
    return { items: [] };
  }
}

function trimHistory(state: SimQueueState) {
  const finished = state.items.filter(
    (entry) =>
      entry.status === "done" || entry.status === "failed" || entry.status === "cancelled",
  );
  if (finished.length <= MAX_HISTORY) return;
  const drop = new Set(finished.slice(0, finished.length - MAX_HISTORY).map((entry) => entry.id));
  state.items = state.items.filter((entry) => !drop.has(entry.id));
}

export function saveQueue(state: SimQueueState) {
  trimHistory(state);
  fs.mkdirSync(RUN_DIR, { recursive: true });
  fs.writeFileSync(QUEUE_FILE, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

export function queueSnapshot(): SimQueueState {
  return loadQueue();
}

export function createQueueItem(payload: unknown, status: QueueItemStatus = "queued"): QueueItem {
  const createdAt = nowIso();
  return {
    id: randomUUID(),
    status,
    label: labelFromPayload(payload),
    createdAt,
    startedAt: status === "running" ? createdAt : null,
    finishedAt: null,
    exitCode: null,
    payload,
    result: null,
  };
}

export function appendQueued(payload: unknown): QueueItem {
  const state = loadQueue();
  const item = createQueueItem(payload, "queued");
  state.items.push(item);
  saveQueue(state);
  return item;
}

/** Insert a new running item (Start now). Keeps existing queued items after it. */
export function beginRunning(payload: unknown): QueueItem {
  const state = loadQueue();
  const item = createQueueItem(payload, "running");
  const queued = state.items.filter((entry) => entry.status === "queued");
  const finished = state.items.filter((entry) => entry.status !== "queued" && entry.status !== "running");
  // Drop stale "running" rows from a crashed server; keep history + remaining queue.
  state.items = [...finished, item, ...queued];
  saveQueue(state);
  return item;
}

export function markRunning(id: string): QueueItem | null {
  const state = loadQueue();
  const item = state.items.find((entry) => entry.id === id);
  if (!item) return null;
  item.status = "running";
  item.startedAt = item.startedAt ?? nowIso();
  item.finishedAt = null;
  item.exitCode = null;
  saveQueue(state);
  return item;
}

export function markFinished(
  id: string | null,
  exitCode: number,
  status: Extract<QueueItemStatus, "done" | "failed" | "cancelled">,
  result?: QueueItemResult | null,
): QueueItem | null {
  const state = loadQueue();
  const item =
    (id ? state.items.find((entry) => entry.id === id) : null) ??
    state.items.find((entry) => entry.status === "running") ??
    null;
  if (!item) {
    saveQueue(state);
    return null;
  }
  item.status = status;
  item.exitCode = exitCode;
  item.finishedAt = nowIso();
  if (result !== undefined) item.result = result;
  saveQueue(state);
  return item;
}

export function removeQueued(id: string): boolean {
  const state = loadQueue();
  const index = state.items.findIndex((entry) => entry.id === id);
  if (index < 0) return false;
  if (state.items[index].status !== "queued") {
    throw new Error("Only queued runs can be removed.");
  }
  state.items.splice(index, 1);
  saveQueue(state);
  return true;
}

export function updateQueuedPayload(id: string, payload: unknown): QueueItem {
  const state = loadQueue();
  const item = state.items.find((entry) => entry.id === id);
  if (!item) throw new Error("Queue item not found.");
  if (item.status !== "queued") throw new Error("Only queued runs can be edited.");
  item.payload = payload;
  item.label = labelFromPayload(payload);
  saveQueue(state);
  return item;
}

/**
 * Reorder queued items. `orderedQueuedIds` must be a permutation of current queued ids.
 * Running and finished rows keep their relative blocks.
 */
export function reorderQueued(orderedQueuedIds: string[]): SimQueueState {
  const state = loadQueue();
  const queued = state.items.filter((entry) => entry.status === "queued");
  const queuedIds = new Set(queued.map((entry) => entry.id));
  if (orderedQueuedIds.length !== queued.length) {
    throw new Error("Reorder list must include every queued run once.");
  }
  for (const id of orderedQueuedIds) {
    if (!queuedIds.has(id)) throw new Error(`Unknown or non-queued id ${id}`);
  }
  if (new Set(orderedQueuedIds).size !== orderedQueuedIds.length) {
    throw new Error("Reorder list has duplicate ids.");
  }
  const byId = new Map(queued.map((entry) => [entry.id, entry]));
  const reordered = orderedQueuedIds.map((id) => byId.get(id)!);
  const finished = state.items.filter(
    (entry) =>
      entry.status === "done" || entry.status === "failed" || entry.status === "cancelled",
  );
  const running = state.items.filter((entry) => entry.status === "running");
  state.items = [...finished, ...running, ...reordered];
  saveQueue(state);
  return state;
}

export function getQueueItem(id: string): QueueItem | null {
  return loadQueue().items.find((entry) => entry.id === id) ?? null;
}

export function peekNextQueued(): QueueItem | null {
  const state = loadQueue();
  return state.items.find((entry) => entry.status === "queued") ?? null;
}

/** After a Vite restart: demote orphan "running" rows if the container is gone. */
export function reconcileAfterRestart(containerAlive: boolean): SimQueueState {
  const state = loadQueue();
  let changed = false;
  for (const item of state.items) {
    if (item.status !== "running") continue;
    if (containerAlive) continue;
    item.status = "queued";
    item.startedAt = null;
    changed = true;
  }
  if (changed) saveQueue(state);
  return loadQueue();
}

/** If Docker is still transporting but the queue has no running row, add one. */
export function ensureRunningPlaceholder(payload: unknown | null, containerAlive: boolean): SimQueueState {
  const state = loadQueue();
  if (!containerAlive) return state;
  if (state.items.some((item) => item.status === "running")) return state;
  const finished = state.items.filter(
    (entry) =>
      entry.status === "done" || entry.status === "failed" || entry.status === "cancelled",
  );
  const queued = state.items.filter((entry) => entry.status === "queued");
  const item = createQueueItem(payload ?? {}, "running");
  item.label = payload ? labelFromPayload(payload) : "reattached run";
  saveQueue({ items: [...finished.slice(-20), item, ...queued] });
  return loadQueue();
}
