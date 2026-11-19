import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const RUN_DIR = path.resolve(REPO_ROOT, "runs", "default");
const PARAMS_FILE = "app_slice_run.json";
/** Fixed name so Stop can send SIGINT into the one-off container (Ctrl+C). */
const CONTAINER_NAME = "rimag-app-sim";

export class RimagRunnerError extends Error {}

type JobState = {
  child: ChildProcessWithoutNullStreams | null;
  listeners: Set<(line: string) => void>;
  running: boolean;
  lastLines: string[];
};

const job: JobState = {
  child: null,
  listeners: new Set(),
  running: false,
  lastLines: [],
};

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

/** Remove a leftover named container so the next run can reuse the name. */
async function removeSimContainer() {
  await runDocker(["rm", "-f", CONTAINER_NAME]);
}

function emit(line: string) {
  job.lastLines.push(line);
  if (job.lastLines.length > 2000) job.lastLines.splice(0, job.lastLines.length - 2000);
  for (const listener of job.listeners) listener(line);
}

function copyDir(src: string, dest: string) {
  fs.mkdirSync(dest, { recursive: true });
  fs.cpSync(src, dest, { recursive: true, force: true });
}

/** Keep the mounted run directory's Python packages in sync with the repo. */
export function syncRimagSourcesIntoRunDir() {
  fs.mkdirSync(RUN_DIR, { recursive: true });
  // entrypoint.sh copies /opt/rimag → /work only when start_sim.py is missing.
  // Seed that marker first so a fresh run dir is not clobbered by the image tree.
  const marker = path.join(RUN_DIR, "start_sim.py");
  const markerSrc = path.join(REPO_ROOT, "start_sim.py");
  if (!fs.existsSync(marker)) {
    if (!fs.existsSync(markerSrc)) {
      throw new RimagRunnerError(`Missing ${markerSrc}`);
    }
    fs.copyFileSync(markerSrc, marker);
  }
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
    else {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(src, dest);
    }
  }
}

export function writeRunParams(payload: unknown) {
  syncRimagSourcesIntoRunDir();
  const target = path.join(RUN_DIR, PARAMS_FILE);
  fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return target;
}

export function isSimulationRunning() {
  return job.running;
}

export function subscribe(listener: (line: string) => void) {
  job.listeners.add(listener);
  for (const line of job.lastLines) listener(line);
  return () => job.listeners.delete(listener);
}

/**
 * Interrupt like Ctrl+C: SIGINT to PID 1 inside the container.
 * On Windows, kill() on the compose client does not send Unix signals.
 */
export function stopSimulation(): boolean {
  if (!job.running && !job.child) return false;
  emit("[runner] Stop: sending SIGINT to container (same as Ctrl+C)…");
  void (async () => {
    const code = await runDocker(["kill", "--signal=SIGINT", CONTAINER_NAME]);
    if (code !== 0) {
      emit("[runner] SIGINT did not reach the container; forcing docker kill…");
      await runDocker(["kill", CONTAINER_NAME]);
    }
    // Also drop the local compose client if it is still attached.
    if (job.child && !job.child.killed) {
      try {
        job.child.kill();
      } catch {
        // ignore
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

export function startSimulation(payload: unknown): void {
  if (job.running) {
    throw new RimagRunnerError("A simulation is already running.");
  }

  writeRunParams(payload);
  const threads = threadsFromPayload(payload);
  // Entrypoint writes simsettings.json from RIMAG_THREADS before Python starts.
  fs.writeFileSync(
    path.join(RUN_DIR, "simsettings.json"),
    `${JSON.stringify({ threads }, null, 2)}\n`,
    "utf8",
  );
  job.lastLines = [];
  job.running = true;

  const { command, prefix } = dockerComposeCommand();
  const args = [
    ...prefix,
    "run",
    "--name",
    CONTAINER_NAME,
    "--rm",
    "-e",
    `RIMAG_THREADS=${threads}`,
    "rimag",
    "python",
    "simulation_app_slice.py",
    PARAMS_FILE,
  ];

  emit(`[runner] repo=${REPO_ROOT}`);
  emit(`[runner] run_dir=${RUN_DIR}`);
  emit(`[runner] threads=${threads}`);
  emit(`[runner] ${command} ${args.join(" ")}`);

  void removeSimContainer().then(() => {
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

    const forward = (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      for (const line of text.split(/\r\n|\n|\r/)) {
        if (line.length) emit(line);
      }
    };

    child.stdout.on("data", forward);
    child.stderr.on("data", forward);
    child.on("error", (error) => {
      emit(`[runner] failed to start: ${error.message}`);
      job.running = false;
      job.child = null;
      emit("[runner] done exit=1");
    });
    child.on("close", (code, signal) => {
      emit(`[runner] process closed code=${code ?? "null"} signal=${signal ?? "null"}`);
      job.running = false;
      job.child = null;
      emit(`[runner] done exit=${code ?? 1}`);
    });
  });
}
