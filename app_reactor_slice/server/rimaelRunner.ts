import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { absorbedFluxWPerCm2, airbridgeOperatingPoint } from "../src/data/tpvEmpiricalLimits";
import {
  GRAPHITE_CP_J_KG_K,
  GRAPHITE_DENSITY_KG_M3,
  GRAPHITE_K_W_M_K,
  RIMAEL_N_SECTIONS,
  TPV_CELL_TEMP_K,
  diskCircuitArcsFromAngles,
  diskSectionThermal,
  graphiteLumpedThermal,
  heatFromFuelToShell,
  perFaceFullWindow,
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
/** OpenModelica emits `RIMAEL.Reactor.exe` on Windows and `RIMAEL.Reactor` elsewhere. */
const REACTOR_BIN = path.join(
  WORK_DIR,
  process.platform === "win32" ? "RIMAEL.Reactor.exe" : "RIMAEL.Reactor",
);
const CSV = path.join(WORK_DIR, "RIMAEL.Reactor_res.csv");
const TPV_TABLE = path.join(WORK_DIR, "tpv_absorbed.txt");

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
  diskTempC: number[];
  shellTempC: number[];
  /** Disk sector whose window starts at 0°. */
  section0TempC: number[];
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
  /** Vacuum-shell emissivity used by the air-bridge absorption. */
  shellEmissivity?: number;
  /** Helium gap on the fuel side of the disk [cm]. */
  fuelGapCm?: number;
  /** Helium gap between the disk and the vacuum shell [cm]. */
  tpvGapCm?: number;
  /** TPV face area of one disk [m²]. */
  tpvAreaM2?: number;
  /** Air-bridge cell index: 0 = 0.74 eV, 1 = 0.90 eV, 2 = 1.10 eV. */
  tpvCellIndex?: number;
};

/** Model default FuelPlate start is 1523.15 K. */
const DEFAULT_FUEL_START_K = 1523.15;
const DEFAULT_EPS = 0.85;
const DEFAULT_SHELL_EPS = 0.95;
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

function resolveGapCm(value: number | undefined): number {
  if (value == null || !Number.isFinite(value) || value < 0) return 0;
  return Math.min(20, value);
}

function resolveShellEmissivity(value: number | undefined): number {
  if (value == null || !Number.isFinite(value)) return DEFAULT_SHELL_EPS;
  return Math.min(1, Math.max(0.05, value));
}

function resolveCellIndex(value: number | undefined): number {
  if (value == null || !Number.isFinite(value)) return 0;
  return Math.min(2, Math.max(0, Math.round(value)));
}

/** Shell temperature [°C] and absorbed flux [W/cm²], sampled from the air-bridge integral. */
function writeAbsorbedTable(cellIndex: number, shellEmissivity: number): void {
  fs.mkdirSync(WORK_DIR, { recursive: true });
  const temps: number[] = [];
  for (let tempC = 0; tempC <= 1600 + 1e-9; tempC += 10) temps.push(tempC);
  const lines = ["#1", `double qabs(${temps.length},2)`];
  for (const tempC of temps) {
    lines.push(`${tempC} ${absorbedFluxWPerCm2(cellIndex, shellEmissivity, tempC).toExponential(8)}`);
  }
  fs.writeFileSync(TPV_TABLE, `${lines.join("\n")}\n`, "utf8");
}

function overrideFlags(
  fuelStartK: number,
  fuelEmissivity: number,
  diskEmissivity: number,
  shellEmissivity: number,
  diskThicknessCm: number,
  diskAreaM2: number,
  fuelThicknessCm: number,
  fuelAreaM2: number,
  tpvAreaM2: number,
  fuelGapCm: number,
  tpvGapCm: number,
  cellIndex: number,
  arcs: DiskCircuitArcs,
): {
  flags: string;
  grFuel: number;
  grTpv: number;
  gFuelGap: number;
  gDiskShell: number;
  heatCapacitySection: number;
  throughThicknessG: number;
  massTotalKg: number;
  fuelPlateC: number;
  fuelMassKg: number;
  fuelHeatingPowerW: number;
  diskStartK: number;
  shellStartK: number;
} {
  const fuelTempC = fuelStartK - 273.15;
  const point = airbridgeOperatingPoint({
    fuelTempC,
    fuelEmissivity,
    diskEmissivity,
    shellEmissivity,
    fuelAreaM2,
    tpvAreaM2,
    fuelGapCm,
    tpvGapCm,
    cellIndex,
  });
  const flow = heatFromFuelToShell({
    fuelTempC,
    shellTempC: point.shellTempC,
    fuelEmissivity,
    diskEmissivity,
    shellEmissivity,
    fuelAreaM2,
    tpvAreaM2,
    fuelGapCm,
    tpvGapCm,
  });
  if (!(point.heatW > 0)) {
    throw new RimaelRunnerError("TPV absorbed heat is zero — cannot set Modelica fuel heating power P0.");
  }
  const fuelHeatingPowerW = Math.min(1e9, point.heatW);
  const grFuel = perFaceFullWindow(flow.grFuel, arcs.fuelArcFrac);
  const grTpv = perFaceFullWindow(flow.grDiskShell, arcs.tpvArcFrac);
  const gFuelGap = perFaceFullWindow(flow.gFuelWPerK, arcs.fuelArcFrac);
  const gDiskShell = perFaceFullWindow(flow.gDiskShellWPerK, arcs.tpvArcFrac);
  const diskStartK = Math.max(273.15, flow.diskTempK);
  const shellStartK = Math.max(273.15, flow.shellTempK);
  const bothFacesCm2 = 2 * tpvAreaM2 * 1e4;
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
      `VacuumShell.T=${shellStartK}`,
      `T_cell=${TPV_CELL_TEMP_K}`,
      `cellHeat.area_cm2=${bothFacesCm2}`,
      `Gr_fuel=${grFuel}`,
      `Gr_tpv=${grTpv}`,
      `G_fuel_gap=${gFuelGap}`,
      `G_disk_shell=${gDiskShell}`,
      `fuel_arc_frac=${arcs.fuelArcFrac}`,
      `tpv_arc_frac=${arcs.tpvArcFrac}`,
      `shield1_arc_frac=${arcs.shield1ArcFrac}`,
      `shield2_arc_frac=${arcs.shield2ArcFrac}`,
      `disk.heat_capacity_section=${heatCapacitySection}`,
      gOverrides,
    ].join(","),
    grFuel,
    grTpv,
    gFuelGap,
    gDiskShell,
    heatCapacitySection,
    throughThicknessG,
    massTotalKg,
    fuelPlateC: fuelThermal.heatCapacity,
    fuelMassKg: fuelThermal.massKg,
    fuelHeatingPowerW,
    diskStartK,
    shellStartK,
  };
}

const OMC_DOCKER_IMAGE =
  process.env.OPENMODELICA_DOCKER_IMAGE ?? "openmodelica/openmodelica:v1.27.1-minimal";
/** Writable HOME for the non-root Docker user (Modelica package index + stdlib). */
const OMC_DOCKER_HOME = path.join(MODEL_DIR, ".omc-home");

type OmcLauncher =
  | { kind: "local"; omc: string }
  | { kind: "docker"; image: string };

function resolveOnPath(command: string): string | null {
  try {
    const which = process.platform === "win32" ? "where" : "which";
    const resolved = execFileSync(which, [command], { encoding: "utf8" });
    const first = resolved
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find(Boolean);
    return first ?? null;
  } catch {
    return null;
  }
}

function findLocalOmc(): string | null {
  const candidates = [
    process.env.OPENMODELICA_OMC,
    "C:\\Program Files\\OpenModelica1.27.1-64bit\\bin\\omc.exe",
    "C:\\Program Files\\OpenModelica1.25.0-64bit\\bin\\omc.exe",
    "C:\\Program Files\\OpenModelica1.24.0-64bit\\bin\\omc.exe",
    "/usr/bin/omc",
    "omc",
  ].filter((value): value is string => Boolean(value));
  for (const candidate of candidates) {
    if (!candidate.includes("/") && !candidate.includes("\\")) {
      const resolved = resolveOnPath(candidate);
      if (resolved) return resolved;
      continue;
    }
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

function dockerAvailable(): boolean {
  try {
    execFileSync("docker", ["info"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return true;
  } catch {
    return false;
  }
}

function resolveOmcLauncher(): OmcLauncher {
  const local = findLocalOmc();
  if (local) return { kind: "local", omc: local };
  if (process.platform !== "win32" && dockerAvailable()) {
    return { kind: "docker", image: OMC_DOCKER_IMAGE };
  }
  throw new RimaelRunnerError(
    "OpenModelica omc not found. Install OpenModelica, set OPENMODELICA_OMC, or install Docker to use " +
      OMC_DOCKER_IMAGE +
      ".",
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

function columnIndex(header: string[], suffix: string): number {
  return header.findIndex((name) => name === suffix || name.endsWith(suffix));
}

function parseFuelCsv(csvPath: string): {
  timeS: number[];
  fuelTempK: number[];
  diskTempK: number[];
  shellTempK: number[];
  section0TempK: number[];
} {
  const raw = fs.readFileSync(csvPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) throw new RimaelRunnerError("Simulation CSV is empty.");
  const header = lines[0].split(",").map((cell) => cell.replace(/^"|"$/g, "").trim());
  const timeIdx = columnIndex(header, "time");
  const tempIdx = columnIndex(header, "FuelPlate.T");
  const diskIdx = columnIndex(header, "disk.T_mean");
  const shellIdx = columnIndex(header, "VacuumShell.T");
  const section0Idx = columnIndex(header, "disk.T_section0");
  if (timeIdx < 0 || tempIdx < 0) {
    throw new RimaelRunnerError(`CSV missing time/FuelPlate.T columns: ${header.join(", ")}`);
  }
  const timeS: number[] = [];
  const fuelTempK: number[] = [];
  const diskTempK: number[] = [];
  const shellTempK: number[] = [];
  const section0TempK: number[] = [];
  for (const line of lines.slice(1)) {
    const cells = line.split(",");
    const t = Number(cells[timeIdx]);
    const temp = Number(cells[tempIdx]);
    if (!Number.isFinite(t) || !Number.isFinite(temp)) continue;
    timeS.push(t);
    fuelTempK.push(temp);
    const disk = diskIdx >= 0 ? Number(cells[diskIdx]) : Number.NaN;
    const shell = shellIdx >= 0 ? Number(cells[shellIdx]) : Number.NaN;
    const section0 = section0Idx >= 0 ? Number(cells[section0Idx]) : Number.NaN;
    if (Number.isFinite(disk)) diskTempK.push(disk);
    if (Number.isFinite(shell)) shellTempK.push(shell);
    if (Number.isFinite(section0)) section0TempK.push(section0);
  }
  if (!timeS.length) throw new RimaelRunnerError("No samples parsed from CSV.");
  return { timeS, fuelTempK, diskTempK, shellTempK, section0TempK };
}

function canReuseBinary(): boolean {
  if (!fs.existsSync(REACTOR_BIN) || !fs.existsSync(APP_MO)) return false;
  try {
    fs.accessSync(REACTOR_BIN, fs.constants.X_OK);
  } catch {
    return false;
  }
  return fs.statSync(REACTOR_BIN).mtimeMs >= fs.statSync(APP_MO).mtimeMs;
}

function ensureDockerOmcHome() {
  fs.mkdirSync(OMC_DOCKER_HOME, { recursive: true });
}

function modelicaStdlibInstalled(): boolean {
  const libraries = path.join(OMC_DOCKER_HOME, ".openmodelica", "libraries");
  if (!fs.existsSync(libraries)) return false;
  return fs.readdirSync(libraries).some((name) => name.startsWith("Modelica "));
}

function dockerRunArgs(image: string, workdirInContainer: string, command: string[]): string[] {
  ensureDockerOmcHome();
  const uid = typeof process.getuid === "function" ? String(process.getuid()) : "0";
  const gid = typeof process.getgid === "function" ? String(process.getgid()) : "0";
  return [
    "run",
    "--rm",
    "-u",
    `${uid}:${gid}`,
    "-e",
    "HOME=/omc-home",
    "-v",
    `${OMC_DOCKER_HOME}:/omc-home`,
    "-v",
    `${MODEL_DIR}:/model`,
    "-w",
    workdirInContainer,
    image,
    ...command,
  ];
}

async function ensureDockerModelicaLibrary(image: string): Promise<void> {
  if (modelicaStdlibInstalled()) return;
  ensureDockerOmcHome();
  const result = await runCommand(
    "docker",
    dockerRunArgs(image, "/model", [
      "bash",
      "-lc",
      'printf "%s\\n" "installPackage(Modelica);" "getErrorString();" "loadModel(Modelica);" "getErrorString();" > /tmp/install_modelica.mos && omc /tmp/install_modelica.mos',
    ]),
    { cwd: MODEL_DIR, timeoutMs: 300_000 },
  );
  if (result.code !== 0 || !modelicaStdlibInstalled()) {
    throw new RimaelRunnerError(
      `Could not install Modelica standard library in Docker.\n${result.stdout}\n${result.stderr}`,
    );
  }
}

async function runCompiledBinary(override: string, launcher: OmcLauncher): Promise<void> {
  const overrideArg = `-override=${override}`;
  let result: { code: number; stdout: string; stderr: string };
  if (launcher.kind === "docker") {
    await ensureDockerModelicaLibrary(launcher.image);
    // Runtime libs live in the image; run the host-built Linux binary inside it.
    result = await runCommand(
      "docker",
      dockerRunArgs(launcher.image, "/model/work", [`./${path.basename(REACTOR_BIN)}`, overrideArg]),
      { cwd: WORK_DIR, timeoutMs: 180_000 },
    );
  } else {
    result = await runCommand(REACTOR_BIN, [overrideArg], {
      cwd: WORK_DIR,
      env: {
        ...process.env,
        PATH: `${path.dirname(launcher.omc)}${path.delimiter}${process.env.PATH ?? ""}`,
      },
      timeoutMs: 180_000,
    });
  }
  if (result.code !== 0) {
    throw new RimaelRunnerError(
      `RIMAEL.Reactor failed (exit ${result.code}).\n${result.stdout}\n${result.stderr}`,
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
  variableFilter = "time|FuelPlate\\\\.T|VacuumShell\\\\.T|disk\\\\.T_mean|disk\\\\.T_section0",
  simflags = "-override=${escaped}"
);
getErrorString();
`;
  fs.writeFileSync(mosPath, content, "utf8");
  return mosPath;
}

async function compileAndSimulateWithOmc(override: string, launcher: OmcLauncher): Promise<void> {
  fs.mkdirSync(WORK_DIR, { recursive: true });
  // Drop stale Windows/previous results so a failed omc exit 0 cannot look successful.
  for (const stale of [CSV, REACTOR_BIN]) {
    try {
      fs.unlinkSync(stale);
    } catch {
      /* missing is fine */
    }
  }
  const mosPath = writeMosWithOverride(override);
  const mosName = path.basename(mosPath);
  let result: { code: number; stdout: string; stderr: string };
  if (launcher.kind === "docker") {
    await ensureDockerModelicaLibrary(launcher.image);
    result = await runCommand("docker", dockerRunArgs(launcher.image, "/model", ["omc", mosName]), {
      cwd: MODEL_DIR,
      timeoutMs: 600_000,
    });
  } else {
    result = await runCommand(launcher.omc, [mosPath], {
      cwd: MODEL_DIR,
      env: {
        ...process.env,
        PATH: `${path.dirname(launcher.omc)}${path.delimiter}${process.env.PATH ?? ""}`,
      },
      timeoutMs: 600_000,
    });
  }
  const logPath = path.join(WORK_DIR, "omc_run.log");
  const combined = `${result.stdout}\n${result.stderr}\n`;
  fs.writeFileSync(logPath, combined, "utf8");
  const ok =
    result.code === 0 &&
    fs.existsSync(CSV) &&
    /simulation finished successfully/i.test(combined);
  if (!ok) {
    throw new RimaelRunnerError(
      `OpenModelica failed (exit ${result.code}). See ${logPath}\n${result.stdout.slice(-2000)}\n${result.stderr.slice(-2000)}`,
    );
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
  const tpvAreaM2 = resolveAreaM2(options.tpvAreaM2);
  if (!(tpvAreaM2 > 0)) {
    throw new RimaelRunnerError("tpv_area_m2 must be a positive TPV face area from Geometry.");
  }
  const shellEmissivity = resolveShellEmissivity(options.shellEmissivity);
  const fuelGapCm = resolveGapCm(options.fuelGapCm);
  const tpvGapCm = resolveGapCm(options.tpvGapCm);
  const cellIndex = resolveCellIndex(options.tpvCellIndex);
  const arcs = resolveCircuitArcs(options);
  const {
    flags,
    grFuel,
    grTpv,
    gFuelGap,
    gDiskShell,
    heatCapacitySection,
    throughThicknessG,
    massTotalKg,
    fuelPlateC,
    fuelMassKg,
    fuelHeatingPowerW,
    shellStartK,
  } = overrideFlags(
    fuelStartK,
    fuelEmissivity,
    diskEmissivity,
    shellEmissivity,
    diskThicknessCm,
    diskAreaM2,
    fuelThicknessCm,
    fuelAreaM2,
    tpvAreaM2,
    fuelGapCm,
    tpvGapCm,
    cellIndex,
    arcs,
  );
  await regenerateAppMoIfNeeded();
  fs.mkdirSync(WORK_DIR, { recursive: true });
  writeAbsorbedTable(cellIndex, shellEmissivity);
  const launcher = resolveOmcLauncher();

  let reusedBinary = false;
  if (canReuseBinary()) {
    reusedBinary = true;
    await runCompiledBinary(flags, launcher);
  } else {
    await compileAndSimulateWithOmc(flags, launcher);
  }

  const { timeS, fuelTempK, diskTempK, shellTempK, section0TempK } = parseFuelCsv(CSV);
  const fuelPct = (100 * arcs.fuelArcFrac).toFixed(1);
  const p0Kw = (fuelHeatingPowerW / 1000).toFixed(1);
  const shellC = (shellStartK - 273.15).toFixed(0);
  return {
    timeS,
    fuelTempK,
    fuelTempC: fuelTempK.map((k) => k - 273.15),
    diskTempC: diskTempK.map((k) => k - 273.15),
    shellTempC: shellTempK.map((k) => k - 273.15),
    section0TempC: section0TempK.map((k) => k - 273.15),
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
    message: `${reusedBinary ? "Reused binary" : "Compiled"} · P0=${p0Kw} kW · shell ${shellC} °C · fuel arc ${fuelPct}% · G_fuel=${gFuelGap.toFixed(2)} W/K · G_shell=${gDiskShell.toFixed(2)} W/K`,
  };
}

export {
  GRAPHITE_CP_J_KG_K,
  GRAPHITE_DENSITY_KG_M3,
  GRAPHITE_K_W_M_K,
  RIMAEL_N_SECTIONS,
};
