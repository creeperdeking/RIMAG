import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const RUN_DIR = path.resolve(REPO_ROOT, "runs", "default");
const PARAMS_FILE = "app_slice_run.json";

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

export function stopSimulation() {
  if (!job.child) return false;
  job.child.kill("SIGTERM");
  return true;
}

function dockerComposeCommand(): { command: string; prefix: string[] } {
  // Prefer `docker compose` (v2). Fall back to docker-compose if needed at spawn time.
  return { command: "docker", prefix: ["compose"] };
}

export function startSimulation(payload: unknown): void {
  if (job.running) {
    throw new RimagRunnerError("A simulation is already running.");
  }

  writeRunParams(payload);
  job.lastLines = [];
  job.running = true;

  const { command, prefix } = dockerComposeCommand();
  const args = [
    ...prefix,
    "run",
    "--rm",
    "rimag",
    "python",
    "simulation_app_slice.py",
    PARAMS_FILE,
  ];

  emit(`[runner] repo=${REPO_ROOT}`);
  emit(`[runner] run_dir=${RUN_DIR}`);
  emit(`[runner] ${command} ${args.join(" ")}`);

  const child = spawn(command, args, {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      RIMAG_RUN_DIR: RUN_DIR,
      PYTHONUNBUFFERED: "1",
    },
    windowsHide: true,
  });
  job.child = child;

  const forward = (chunk: Buffer) => {
    const text = chunk.toString("utf8");
    for (const line of text.split(/\r?\n/)) {
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
}
