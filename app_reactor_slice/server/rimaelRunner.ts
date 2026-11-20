import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const MODEL_DIR = path.join(REPO_ROOT, "RIMAEL-Modellica");
const WORK_DIR = path.join(MODEL_DIR, "work");
const APP_MO = path.join(MODEL_DIR, "RIMAEL_App.mo");
const SOURCE_PKG = path.join(MODEL_DIR, "RIMAEL");
const MAKE_APP = path.join(MODEL_DIR, "_make_app_mo.py");
const MOS = path.join(MODEL_DIR, "run_reactor_app.mos");
const EXE = path.join(WORK_DIR, "RIMAEL.Reactor.exe");
const CSV = path.join(WORK_DIR, "RIMAEL.Reactor_res.csv");

function sourcePackageMtimeMs(): number {
  if (!fs.existsSync(SOURCE_PKG)) return 0;
  let newest = fs.statSync(SOURCE_PKG).mtimeMs;
  for (const name of fs.readdirSync(SOURCE_PKG)) {
    const st = fs.statSync(path.join(SOURCE_PKG, name));
    if (st.mtimeMs > newest) newest = st.mtimeMs;
  }
  return newest;
}

export class RimaelRunnerError extends Error {}

export type RimaelFuelTrace = {
  timeS: number[];
  fuelTempK: number[];
  fuelTempC: number[];
  stopTimeS: number;
  fuelTempStartC: number;
  fuelEmissivity: number;
  diskEmissivity: number;
  diskThicknessCm: number;
  heatCapacitySection: number;
  throughThicknessG: number;
  grFuel: number;
  grTpv: number;
  reusedBinary: boolean;
  message: string;
};

export type RimaelRunOptions = {
  /** Initial FuelPlate temperature in °C (slider). */
  fuelTempC?: number;
  /** Fuel-side emissivity ε ∈ (0, 1]. */
  fuelEmissivity?: number;
  /** Disk-side emissivity ε ∈ (0, 1]. */
  diskEmissivity?: number;
  /** Solid disk thickness from Layer designer (cm, excludes Void). */
  diskThicknessCm?: number;
};

/** Model default FuelPlate start is 1523.15 K; disk T_start is 150 K cooler. */
const DEFAULT_FUEL_START_K = 1523.15;
const DISK_OFFSET_K = 150;
/** Calibrate radiation areas so default ε keep model Gr_fuel / Gr_tpv. */
const DEFAULT_EPS = 0.85;
const GR_FUEL_REF = 1.009;
const GR_TPV_REF = 0.156;
const EPS_TPV = 0.85;
/** Model defaults match the usual 0.8 cm solid Disk layer. */
const DISK_THICKNESS_REF_CM = 0.8;
const HEAT_CAPACITY_REF = 23569;
const THROUGH_G_REF = 18149;

function clampEps(value: number | undefined): number {
  if (value == null || !Number.isFinite(value)) return DEFAULT_EPS;
  return Math.min(1, Math.max(0.05, value));
}

function resolveDiskThicknessCm(value: number | undefined): number {
  if (value == null || !Number.isFinite(value) || value <= 0) return DISK_THICKNESS_REF_CM;
  return Math.min(20, Math.max(0.01, value));
}

/** Two gray surfaces: Gr = A / (1/ε₁ + 1/ε₂ − 1). */
function radiationFactor(area: number, epsA: number, epsB: number): number {
  const denom = 1 / epsA + 1 / epsB - 1;
  return area / Math.max(denom, 1e-9);
}

function resolveFuelStartK(fuelTempC: number | undefined): number {
  if (fuelTempC == null || !Number.isFinite(fuelTempC)) return DEFAULT_FUEL_START_K;
  return fuelTempC + 273.15;
}

function overrideFlags(
  fuelStartK: number,
  fuelEmissivity: number,
  diskEmissivity: number,
  diskThicknessCm: number,
): {
  flags: string;
  grFuel: number;
  grTpv: number;
  heatCapacitySection: number;
  throughThicknessG: number;
} {
  const diskStartK = Math.max(273.15, fuelStartK - DISK_OFFSET_K);
  const denomRef = 1 / DEFAULT_EPS + 1 / DEFAULT_EPS - 1;
  const areaFuel = GR_FUEL_REF * denomRef;
  const areaTpv = GR_TPV_REF * denomRef;
  const grFuel = radiationFactor(areaFuel, fuelEmissivity, diskEmissivity);
  const grTpv = radiationFactor(areaTpv, EPS_TPV, diskEmissivity);
  const scale = diskThicknessCm / DISK_THICKNESS_REF_CM;
  const heatCapacitySection = HEAT_CAPACITY_REF * scale;
  const throughThicknessG = THROUGH_G_REF / scale;
  const gOverrides = Array.from({ length: 12 }, (_, i) => {
    const n = i + 1;
    return `disk.twoFaceDiskSection${n}.thermalConductor.G=${throughThicknessG}`;
  }).join(",");
  return {
    flags: [
      `FuelPlate.T=${fuelStartK}`,
      `disk.T_start=${diskStartK}`,
      `Gr_fuel=${grFuel}`,
      `Gr_tpv=${grTpv}`,
      `disk.heat_capacity_section=${heatCapacitySection}`,
      gOverrides,
    ].join(","),
    grFuel,
    grTpv,
    heatCapacitySection,
    throughThicknessG,
  };
}

function findOmc(): string {
  const candidates = [
    process.env.OPENMODELICA_OMC,
    "C:\\Program Files\\OpenModelica1.27.1-64bit\\bin\\omc.exe",
    "C:\\Program Files\\OpenModelica1.25.0-64bit\\bin\\omc.exe",
    "C:\\Program Files\\OpenModelica1.24.0-64bit\\bin\\omc.exe",
    "omc",
  ].filter((value): value is string => Boolean(value));
  for (const candidate of candidates) {
    if (candidate === "omc") return candidate;
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new RimaelRunnerError(
    "OpenModelica omc.exe not found. Install OpenModelica or set OPENMODELICA_OMC.",
  );
}

function runCommand(
  command: string,
  args: string[],
  options: { cwd: string; env?: NodeJS.ProcessEnv; timeoutMs?: number },
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env ?? process.env,
      windowsHide: true,
      shell: false,
    });
    let stdout = "";
    let stderr = "";
    const timer =
      options.timeoutMs != null
        ? setTimeout(() => {
            child.kill();
            reject(new RimaelRunnerError(`Command timed out after ${options.timeoutMs} ms`));
          }, options.timeoutMs)
        : null;
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      if (timer) clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      if (timer) clearTimeout(timer);
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

async function regenerateAppMoIfNeeded() {
  if (!fs.existsSync(path.join(SOURCE_PKG, "package.mo"))) {
    throw new RimaelRunnerError(`Missing directory package ${SOURCE_PKG}`);
  }
  if (
    fs.existsSync(APP_MO) &&
    fs.existsSync(MAKE_APP) &&
    fs.statSync(APP_MO).mtimeMs >= sourcePackageMtimeMs()
  ) {
    return;
  }
  if (!fs.existsSync(MAKE_APP)) {
    throw new RimaelRunnerError(`Missing ${MAKE_APP}`);
  }
  const result = await runCommand("python", [MAKE_APP], {
    cwd: MODEL_DIR,
    timeoutMs: 60_000,
  });
  if (result.code !== 0 || !fs.existsSync(APP_MO)) {
    throw new RimaelRunnerError(
      `Could not generate RIMAEL_App.mo.\n${result.stdout}\n${result.stderr}`,
    );
  }
}

function parseFuelCsv(csvPath: string): { timeS: number[]; fuelTempK: number[] } {
  const raw = fs.readFileSync(csvPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) throw new RimaelRunnerError("Simulation CSV is empty.");
  const header = lines[0].split(",").map((cell) => cell.replace(/^"|"$/g, "").trim());
  const timeIdx = header.findIndex((name) => name === "time" || name.endsWith(".time"));
  const tempIdx = header.findIndex(
    (name) => name === "FuelPlate.T" || name.endsWith("FuelPlate.T"),
  );
  if (timeIdx < 0 || tempIdx < 0) {
    throw new RimaelRunnerError(`CSV missing time/FuelPlate.T columns: ${header.join(", ")}`);
  }
  const timeS: number[] = [];
  const fuelTempK: number[] = [];
  for (const line of lines.slice(1)) {
    const cells = line.split(",");
    const t = Number(cells[timeIdx]);
    const temp = Number(cells[tempIdx]);
    if (!Number.isFinite(t) || !Number.isFinite(temp)) continue;
    timeS.push(t);
    fuelTempK.push(temp);
  }
  if (!timeS.length) throw new RimaelRunnerError("No samples parsed from CSV.");
  return { timeS, fuelTempK };
}

function canReuseBinary(): boolean {
  if (!fs.existsSync(EXE) || !fs.existsSync(APP_MO)) return false;
  return fs.statSync(EXE).mtimeMs >= fs.statSync(APP_MO).mtimeMs;
}

async function runCompiledBinary(override: string): Promise<void> {
  const result = await runCommand(EXE, [`-override=${override}`], {
    cwd: WORK_DIR,
    env: {
      ...process.env,
      PATH: `${path.dirname(findOmc())}${path.delimiter}${process.env.PATH ?? ""}`,
    },
    timeoutMs: 180_000,
  });
  if (result.code !== 0) {
    throw new RimaelRunnerError(
      `RIMAEL.Reactor.exe failed (exit ${result.code}).\n${result.stdout}\n${result.stderr}`,
    );
  }
  if (!fs.existsSync(CSV)) {
    throw new RimaelRunnerError("Simulation finished but CSV result is missing.");
  }
}

function writeMosWithOverride(override: string): string {
  const mosPath = path.join(MODEL_DIR, "run_reactor_override.mos");
  const escaped = override.replace(/"/g, '\\"');
  const content = `// Auto-generated — do not edit
cd("work");
loadModel(Modelica);
getErrorString();
loadFile("../RIMAEL_App.mo");
getErrorString();
simulate(
  RIMAEL.Reactor,
  startTime = 0,
  stopTime = 700,
  numberOfIntervals = 700,
  method = "dassl",
  tolerance = 1e-6,
  outputFormat = "csv",
  variableFilter = "time|FuelPlate\\\\.T",
  simflags = "-override=${escaped}"
);
getErrorString();
`;
  fs.writeFileSync(mosPath, content, "utf8");
  return mosPath;
}

async function compileAndSimulateWithOmc(override: string): Promise<void> {
  fs.mkdirSync(WORK_DIR, { recursive: true });
  const mosPath = writeMosWithOverride(override);
  const omc = findOmc();
  const result = await runCommand(omc, [mosPath], {
    cwd: MODEL_DIR,
    env: {
      ...process.env,
      PATH: `${path.dirname(omc)}${path.delimiter}${process.env.PATH ?? ""}`,
    },
    timeoutMs: 600_000,
  });
  const logPath = path.join(WORK_DIR, "omc_run.log");
  fs.writeFileSync(logPath, `${result.stdout}\n${result.stderr}\n`, "utf8");
  if (result.code !== 0 || !fs.existsSync(CSV)) {
    throw new RimaelRunnerError(
      `OpenModelica failed (exit ${result.code}). See ${logPath}\n${result.stdout.slice(-2000)}\n${result.stderr.slice(-2000)}`,
    );
  }
  if (!/simulation finished successfully/i.test(result.stdout + result.stderr) && !fs.existsSync(CSV)) {
    throw new RimaelRunnerError(`OpenModelica did not report success. See ${logPath}`);
  }
}

/** Run RIMAEL.Reactor and return FuelPlate temperature vs time. */
export async function runRimaelFuelTemperature(
  options: RimaelRunOptions = {},
): Promise<RimaelFuelTrace> {
  const fuelStartK = resolveFuelStartK(options.fuelTempC);
  const fuelTempStartC = fuelStartK - 273.15;
  const fuelEmissivity = clampEps(options.fuelEmissivity);
  const diskEmissivity = clampEps(options.diskEmissivity);
  const diskThicknessCm = resolveDiskThicknessCm(options.diskThicknessCm);
  const { flags, grFuel, grTpv, heatCapacitySection, throughThicknessG } = overrideFlags(
    fuelStartK,
    fuelEmissivity,
    diskEmissivity,
    diskThicknessCm,
  );
  await regenerateAppMoIfNeeded();
  fs.mkdirSync(WORK_DIR, { recursive: true });

  let reusedBinary = false;
  if (canReuseBinary()) {
    reusedBinary = true;
    await runCompiledBinary(flags);
  } else {
    await compileAndSimulateWithOmc(flags);
  }

  const { timeS, fuelTempK } = parseFuelCsv(CSV);
  return {
    timeS,
    fuelTempK,
    fuelTempC: fuelTempK.map((k) => k - 273.15),
    stopTimeS: timeS[timeS.length - 1] ?? 700,
    fuelTempStartC,
    fuelEmissivity,
    diskEmissivity,
    diskThicknessCm,
    heatCapacitySection,
    throughThicknessG,
    grFuel,
    grTpv,
    reusedBinary,
    message: reusedBinary
      ? `Reused binary · T₀=${fuelTempStartC.toFixed(0)} °C · disk=${diskThicknessCm.toFixed(2)} cm · ε_fuel=${fuelEmissivity.toFixed(2)} · ε_disk=${diskEmissivity.toFixed(2)}`
      : `Compiled · T₀=${fuelTempStartC.toFixed(0)} °C · disk=${diskThicknessCm.toFixed(2)} cm · ε_fuel=${fuelEmissivity.toFixed(2)} · ε_disk=${diskEmissivity.toFixed(2)}`,
  };
}
