import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  GRAPHITE_CP_J_KG_K,
  GRAPHITE_DENSITY_KG_M3,
  GRAPHITE_K_W_M_K,
  RIMAEL_N_SECTIONS,
  diskCircuitArcsFromAngles,
  diskSectionThermal,
  graphiteLumpedThermal,
  type DiskCircuitArcs,
} from "../shared/diskThermal";

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
  diskAreaM2: number;
  fuelThicknessCm: number;
  fuelAreaM2: number;
  fuelPlateC: number;
  fuelMassKg: number;
  fuelHeatingPowerW: number;
  fuelArcFrac: number;
  tpvArcFrac: number;
  heatCapacitySection: number;
  throughThicknessG: number;
  massTotalKg: number;
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
  /** One-disk face area from Geometry tab (m²). */
  diskAreaM2?: number;
  /** Solid fuel-stack thickness from Layer designer (cm, excludes Void). */
  fuelThicknessCm?: number;
  /** Fuel-sector face area from Geometry tab (m²). */
  fuelAreaM2?: number;
  /** Fuel / TPV / shield circuit fractions of 2π from Geometry. */
  fuelArcFrac?: number;
  tpvArcFrac?: number;
  shield1ArcFrac?: number;
  shield2ArcFrac?: number;
  /** Stationary fuel heating power P0 [W] (one disk × one slice, from app Thermal). */
  fuelHeatingPowerW?: number;
};

/** Model default P0 when the app does not send a value. */
const DEFAULT_P0_W = 383771;

/** Model default FuelPlate start is 1523.15 K; disk T_start is 150 K cooler. */
const DEFAULT_FUEL_START_K = 1523.15;
const DISK_OFFSET_K = 150;
/** Calibrate radiation areas so default ε keep model Gr_fuel / Gr_tpv. */
const DEFAULT_EPS = 0.85;
const GR_FUEL_REF = 1.009;
const GR_TPV_REF = 0.156;
const EPS_TPV = 0.85;
const DEFAULT_DISK_THICKNESS_CM = 0.8;
const DEFAULT_FUEL_THICKNESS_CM = 1.0;

function clampEps(value: number | undefined): number {
  if (value == null || !Number.isFinite(value)) return DEFAULT_EPS;
  return Math.min(1, Math.max(0.05, value));
}

function resolveThicknessCm(value: number | undefined, fallback: number): number {
  if (value == null || !Number.isFinite(value) || value <= 0) return fallback;
  return Math.min(20, Math.max(0.01, value));
}

function resolveAreaM2(value: number | undefined): number {
  if (value == null || !Number.isFinite(value) || value <= 0) return 0;
  return value;
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

function resolveCircuitArcs(options: RimaelRunOptions): DiskCircuitArcs {
  if (
    options.fuelArcFrac != null &&
    options.tpvArcFrac != null &&
    Number.isFinite(options.fuelArcFrac) &&
    Number.isFinite(options.tpvArcFrac)
  ) {
    const shield1 =
      options.shield1ArcFrac != null && Number.isFinite(options.shield1ArcFrac)
        ? options.shield1ArcFrac
        : undefined;
    const shield2 =
      options.shield2ArcFrac != null && Number.isFinite(options.shield2ArcFrac)
        ? options.shield2ArcFrac
        : undefined;
    if (shield1 != null && shield2 != null) {
      return {
        fuelArcFrac: options.fuelArcFrac,
        tpvArcFrac: options.tpvArcFrac,
        shield1ArcFrac: shield1,
        shield2ArcFrac: shield2,
      };
    }
    return diskCircuitArcsFromAngles(options.fuelArcFrac * 2 * Math.PI, options.tpvArcFrac * 2 * Math.PI);
  }
  return diskCircuitArcsFromAngles((2 / 12) * 2 * Math.PI, (6 / 12) * 2 * Math.PI);
}

function resolveFuelHeatingPowerW(value: number | undefined): number {
  if (value == null || !Number.isFinite(value) || value <= 0) return DEFAULT_P0_W;
  return Math.min(1e9, Math.max(1, value));
}

function overrideFlags(
  fuelStartK: number,
  fuelEmissivity: number,
  diskEmissivity: number,
  diskThicknessCm: number,
  diskAreaM2: number,
  fuelThicknessCm: number,
  fuelAreaM2: number,
  arcs: DiskCircuitArcs,
  fuelHeatingPowerW: number,
): {
  flags: string;
  grFuel: number;
  grTpv: number;
  heatCapacitySection: number;
  throughThicknessG: number;
  massTotalKg: number;
  fuelPlateC: number;
  fuelMassKg: number;
} {
  const diskStartK = Math.max(273.15, fuelStartK - DISK_OFFSET_K);
  const denomRef = 1 / DEFAULT_EPS + 1 / DEFAULT_EPS - 1;
  const areaFuel = GR_FUEL_REF * denomRef;
  const areaTpv = GR_TPV_REF * denomRef;
  const grFuel = radiationFactor(areaFuel, fuelEmissivity, diskEmissivity);
  const grTpv = radiationFactor(areaTpv, EPS_TPV, diskEmissivity);
  const thermal = diskSectionThermal(diskAreaM2, diskThicknessCm, RIMAEL_N_SECTIONS);
  const fuelThermal = graphiteLumpedThermal(fuelAreaM2, fuelThicknessCm);
  const { heatCapacitySection, throughThicknessG, massTotalKg } = thermal;
  const gOverrides = Array.from({ length: RIMAEL_N_SECTIONS }, (_, i) => {
    const n = i + 1;
    return `disk.twoFaceDiskSection${n}.thermalConductor.G=${throughThicknessG}`;
  }).join(",");
  return {
    flags: [
      `FuelPlate.T=${fuelStartK}`,
      `FuelPlate.C=${fuelThermal.heatCapacity}`,
      `P0=${fuelHeatingPowerW}`,
      `disk.T_start=${diskStartK}`,
      `Gr_fuel=${grFuel}`,
      `Gr_tpv=${grTpv}`,
      `fuel_arc_frac=${arcs.fuelArcFrac}`,
      `tpv_arc_frac=${arcs.tpvArcFrac}`,
      `shield1_arc_frac=${arcs.shield1ArcFrac}`,
      `shield2_arc_frac=${arcs.shield2ArcFrac}`,
      `disk.heat_capacity_section=${heatCapacitySection}`,
      gOverrides,
    ].join(","),
    grFuel,
    grTpv,
    heatCapacitySection,
    throughThicknessG,
    massTotalKg,
    fuelPlateC: fuelThermal.heatCapacity,
    fuelMassKg: fuelThermal.massKg,
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
  const diskThicknessCm = resolveThicknessCm(options.diskThicknessCm, DEFAULT_DISK_THICKNESS_CM);
  const fuelThicknessCm = resolveThicknessCm(options.fuelThicknessCm, DEFAULT_FUEL_THICKNESS_CM);
  const diskAreaM2 = resolveAreaM2(options.diskAreaM2);
  const fuelAreaM2 = resolveAreaM2(options.fuelAreaM2);
  if (!(diskAreaM2 > 0)) {
    throw new RimaelRunnerError("disk_area_m2 must be a positive disk face area from Geometry.");
  }
  if (!(fuelAreaM2 > 0)) {
    throw new RimaelRunnerError("fuel_area_m2 must be a positive fuel-sector area from Geometry.");
  }
  const arcs = resolveCircuitArcs(options);
  const fuelHeatingPowerW = resolveFuelHeatingPowerW(options.fuelHeatingPowerW);
  const {
    flags,
    grFuel,
    grTpv,
    heatCapacitySection,
    throughThicknessG,
    massTotalKg,
    fuelPlateC,
    fuelMassKg,
  } = overrideFlags(
    fuelStartK,
    fuelEmissivity,
    diskEmissivity,
    diskThicknessCm,
    diskAreaM2,
    fuelThicknessCm,
    fuelAreaM2,
    arcs,
    fuelHeatingPowerW,
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
  const fuelPct = (100 * arcs.fuelArcFrac).toFixed(1);
  const p0Kw = (fuelHeatingPowerW / 1000).toFixed(1);
  return {
    timeS,
    fuelTempK,
    fuelTempC: fuelTempK.map((k) => k - 273.15),
    stopTimeS: timeS[timeS.length - 1] ?? 700,
    fuelTempStartC,
    fuelEmissivity,
    diskEmissivity,
    diskThicknessCm,
    diskAreaM2,
    fuelThicknessCm,
    fuelAreaM2,
    fuelPlateC,
    fuelMassKg,
    fuelHeatingPowerW,
    fuelArcFrac: arcs.fuelArcFrac,
    tpvArcFrac: arcs.tpvArcFrac,
    heatCapacitySection,
    throughThicknessG,
    massTotalKg,
    grFuel,
    grTpv,
    reusedBinary,
    message: reusedBinary
      ? `Reused binary · P0=${p0Kw} kW · fuel arc ${fuelPct}% · FuelPlate.C=${fuelPlateC.toFixed(0)} J/K`
      : `Compiled · P0=${p0Kw} kW · fuel arc ${fuelPct}% · FuelPlate.C=${fuelPlateC.toFixed(0)} J/K`,
  };
}

export {
  GRAPHITE_CP_J_KG_K,
  GRAPHITE_DENSITY_KG_M3,
  GRAPHITE_K_W_M_K,
  RIMAEL_N_SECTIONS,
};
