import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {
  RIMAEL_CONTAINER,
  RIMAEL_WORK_DIR,
  holdRimael,
  prepareRimaelModel,
  releaseRimael,
  rimaelLaunchSpec,
  type RimaelRunOptions,
} from "./rimaelRunner";

export type LiveSample = {
  timeS: number;
  powerW: number;
  rps: number;
  fuelC: number;
  shellC: number;
  shieldC: number;
  sectionC: number[];
  /** Section-window rotation from the model [deg]. */
  angleDeg: number;
};

export type LiveEvent =
  | { type: "ready"; running: boolean; message: string }
  | { type: "status"; running: boolean; message: string }
  | { type: "sample"; sample: LiveSample }
  | { type: "control"; powerW: number; rps: number; scale: number }
  | { type: "done"; message: string }
  | { type: "error"; message: string };

const CONTROL = path.join(RIMAEL_WORK_DIR, "live_control.txt");
const STATE = path.join(RIMAEL_WORK_DIR, "live_state.txt");
const HISTORY_CAP = 4000;

type Listener = (event: LiveEvent) => void;

type Session = {
  child: ChildProcess | null;
  listeners: Set<Listener>;
  history: LiveSample[];
  powerW: number;
  rps: number;
  scale: number;
  timer: NodeJS.Timeout | null;
  offset: number;
  partial: string;
  running: boolean;
  message: string;
  token: number;
};

let session: Session | null = null;
let liveToken = 0;

function emit(event: LiveEvent): void {
  if (!session) return;
  for (const listener of session.listeners) listener(event);
}

function clampScale(scale: number): number {
  if (!Number.isFinite(scale)) return 1;
  return Math.min(60, Math.max(1, scale));
}

function clampPower(powerW: number): number {
  if (!Number.isFinite(powerW) || powerW < 0) return 0;
  return Math.min(1e9, powerW);
}

function clampRps(rps: number): number {
  if (!Number.isFinite(rps) || rps < 0) return 0;
  return Math.min(20, rps);
}

function writeControl(powerW: number, rps: number, scale: number, run: boolean): void {
  fs.mkdirSync(RIMAEL_WORK_DIR, { recursive: true });
  const text = `${powerW.toFixed(6)} ${rps.toFixed(6)} ${scale.toFixed(3)} ${run ? 1 : 0}\n`;
  const tmp = `${CONTROL}.tmp`;
  fs.writeFileSync(tmp, text, "utf8");
  fs.renameSync(tmp, CONTROL);
}

function parseLine(line: string): LiveSample | null {
  const parts = line.trim().split(/\s+/).map(Number);
  if (parts.length < 19 || parts.some((value) => !Number.isFinite(value))) return null;
  const toC = (kelvin: number) => kelvin - 273.15;
  return {
    timeS: parts[0],
    powerW: parts[1],
    rps: parts[2],
    fuelC: toC(parts[3]),
    shellC: toC(parts[4]),
    shieldC: toC(parts[5]),
    sectionC: parts.slice(6, 18).map(toC),
    angleDeg: parts[18],
  };
}

function pumpState(): void {
  if (!session) return;
  let size = 0;
  try {
    size = fs.statSync(STATE).size;
  } catch {
    return;
  }
  if (size < session.offset) session.offset = 0;
  if (size === session.offset) return;
  const fd = fs.openSync(STATE, "r");
  try {
    const length = size - session.offset;
    const buf = Buffer.alloc(length);
    fs.readSync(fd, buf, 0, length, session.offset);
    session.offset = size;
    session.partial += buf.toString("utf8");
  } finally {
    fs.closeSync(fd);
  }
  const lines = session.partial.split(/\n/);
  session.partial = lines.pop() ?? "";
  for (const line of lines) {
    const sample = parseLine(line);
    if (!sample || !session) continue;
    const prev = session.history[session.history.length - 1];
    if (prev && sample.timeS < prev.timeS - 1e-9) continue;
    if (prev && Math.abs(sample.timeS - prev.timeS) <= 1e-9) {
      session.history[session.history.length - 1] = sample;
    } else {
      session.history.push(sample);
    }
    if (session.history.length > HISTORY_CAP) {
      session.history.splice(0, session.history.length - HISTORY_CAP);
    }
    emit({ type: "sample", sample });
  }
}

function killChild(child: ChildProcess | null): void {
  if (!child || child.killed) return;
  try {
    child.kill("SIGTERM");
  } catch {
    /* already gone */
  }
}

function dockerCmd(args: string[]): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const child = spawn("docker", args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => resolve({ code: 1, stdout, stderr: stderr || error.message }));
    child.on("close", (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

function nameStillTaken(stdout: string): boolean {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .some((name) => name === RIMAEL_CONTAINER);
}

/** One removal at a time, and do not return while the name is still reserved. */
let removalChain: Promise<void> = Promise.resolve();

function removeLiveContainer(): Promise<void> {
  const run = removalChain.then(async () => {
    await dockerCmd(["rm", "-f", RIMAEL_CONTAINER]);
    for (let attempt = 0; attempt < 25; attempt += 1) {
      const listed = await dockerCmd([
        "ps",
        "-a",
        "--filter",
        `name=${RIMAEL_CONTAINER}`,
        "--format",
        "{{.Names}}",
      ]);
      if (!nameStillTaken(listed.stdout)) return;
      await dockerCmd(["rm", "-f", RIMAEL_CONTAINER]);
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
  });
  removalChain = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

function nameConflict(text: string): boolean {
  return text.includes("already in use") || text.includes("Conflict");
}

function ensureSession(): Session {
  if (!session) {
    session = {
      child: null,
      listeners: new Set(),
      history: [],
      powerW: 0,
      rps: 0,
      scale: 1,
      timer: null,
      offset: 0,
      partial: "",
      running: false,
      message: "Idle",
      token: 0,
    };
  }
  return session;
}

export function liveSnapshot(): {
  running: boolean;
  message: string;
  history: LiveSample[];
  powerW: number;
  rps: number;
  scale: number;
} {
  const current = session;
  return {
    running: Boolean(current?.running),
    message: current?.message ?? "Idle",
    history: current?.history.slice(-600) ?? [],
    powerW: current?.powerW ?? 0,
    rps: current?.rps ?? 0,
    scale: current?.scale ?? 1,
  };
}

export function subscribeLive(listener: Listener): () => void {
  const current = ensureSession();
  current.listeners.add(listener);
  listener({ type: "ready", running: current.running, message: current.message });
  return () => {
    current.listeners.delete(listener);
  };
}

export function updateLiveControl(input: { powerW?: number; rps?: number; scale?: number }): void {
  if (!session?.running) return;
  if (input.powerW != null) session.powerW = clampPower(input.powerW);
  if (input.rps != null) session.rps = clampRps(input.rps);
  if (input.scale != null) session.scale = clampScale(input.scale);
  writeControl(session.powerW, session.rps, session.scale, true);
  emit({ type: "control", powerW: session.powerW, rps: session.rps, scale: session.scale });
}

export function stopLive(silent = false): void {
  liveToken += 1;
  if (!session) return;
  writeControl(session.powerW, session.rps, session.scale, false);
  const child = session.child;
  session.child = null;
  session.token = liveToken;
  session.running = false;
  session.message = "Stopped";
  if (session.timer) clearInterval(session.timer);
  session.timer = null;
  killChild(child);
  void removeLiveContainer();
  if (!silent) emit({ type: "done", message: "Stopped" });
  releaseRimael("live");
}

export async function startLive(
  options: RimaelRunOptions,
  control: { powerW: number; rps: number; scale: number },
): Promise<boolean> {
  stopLive(true);
  const token = liveToken;
  const current = ensureSession();
  holdRimael("live");
  current.token = token;
  current.running = false;
  current.message = "Compiling the Modelica model if it is out of date…";
  current.history = [];
  current.powerW = clampPower(control.powerW);
  current.rps = clampRps(control.rps);
  current.scale = clampScale(control.scale);
  emit({ type: "status", running: false, message: current.message });
  try {
    const prepared = await prepareRimaelModel(options);
    if (token !== liveToken) return false;
    const stepS = Math.min(2, Math.max(0.25, 0.25 * current.scale));
    const flags = /P0=/.test(prepared.flags)
      ? prepared.flags.replace(/P0=[^,]+/, `P0=${current.powerW}`)
      : `${prepared.flags},P0=${current.powerW}`;
    const override = `${flags},rpsDisk=${current.rps},liveControl=true,liveStepS=${stepS}`;
    writeControl(current.powerW, current.rps, current.scale, true);
    fs.writeFileSync(STATE, "", "utf8");
    current.offset = 0;
    current.partial = "";
    const spec = rimaelLaunchSpec(
      prepared.launcher,
      [`-override=${override}`, "-stopTime=86400", `-stepSize=${stepS}`, "-variableFilter=time"],
      prepared.launcher.kind === "docker" ? RIMAEL_CONTAINER : undefined,
    );
    const log = { text: "" };
    let child: ChildProcess | null = null;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await removeLiveContainer();
      if (token !== liveToken) return false;
      log.text = "";
      const next = spawn(spec.command, spec.args, {
        cwd: spec.cwd,
        env: spec.env,
        windowsHide: true,
        shell: false,
      });
      next.stderr.on("data", (chunk: Buffer) => {
        log.text = (log.text + chunk.toString("utf8")).slice(-4000);
      });
      const conflict = await new Promise<boolean>((resolve) => {
        const timer = setTimeout(() => resolve(nameConflict(log.text)), 700);
        const consider = () => {
          if (!nameConflict(log.text)) return;
          clearTimeout(timer);
          resolve(true);
        };
        next.stderr.on("data", consider);
        next.on("close", () => {
          clearTimeout(timer);
          resolve(nameConflict(log.text));
        });
        next.on("error", () => {
          clearTimeout(timer);
          resolve(false);
        });
      });
      if (!conflict) {
        if (next.exitCode != null || next.signalCode != null) {
          throw new Error(log.text.trim() || `Simulation exited (${next.exitCode ?? 1})`);
        }
        child = next;
        break;
      }
      killChild(next);
    }
    if (!child || token !== liveToken) {
      if (child) killChild(child);
      if (token !== liveToken) return false;
      throw new Error(log.text.trim() || "The previous live container was still named rimael-live.");
    }
    current.child = child;
    current.running = true;
    current.message = "OpenModelica is integrating in real time";
    emit({ type: "status", running: true, message: current.message });
    child.on("error", (error) => {
      if (token !== liveToken) return;
      emit({ type: "error", message: error.message });
    });
    child.on("close", (code) => {
      if (token !== liveToken || !session || session.child !== child) return;
      pumpState();
      session.running = false;
      session.child = null;
      if (session.timer) clearInterval(session.timer);
      session.timer = null;
      const message = code === 0 ? "Simulation finished" : `Simulation exited (${code ?? 1})`;
      session.message = message;
      if (code !== 0 && log.text.trim()) {
        emit({ type: "error", message: `${message}. ${log.text.trim().slice(-600)}` });
      }
      emit({ type: "done", message });
      releaseRimael("live");
    });
    current.timer = setInterval(pumpState, 100);
    return true;
  } catch (error) {
    if (token === liveToken) {
      current.running = false;
      current.message = "Failed";
      releaseRimael("live");
    }
    throw error;
  }
}
