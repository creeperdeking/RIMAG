import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  isSimulationRunning,
  syncPlotScriptIntoRunDir,
  syncRimagSourcesIntoRunDir,
} from "./rimagRunner";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const RUN_DIR = path.resolve(REPO_ROOT, "runs", "default");
const PLOT_OUT = "plot_slice.png";
const PLOT_DEFAULTS = "plot_defaults.json";
const PAD = 1.05;

export class GeometryPlotError extends Error {
  status: number;
  constructor(message: string, status = 400) {
    super(message);
    this.status = status;
  }
}

export type Basis = "xy" | "xz" | "yz";

export type PlotRequest = {
  basis: Basis;
  origin: [number, number, number];
  width: number;
  height: number;
  pixels?: number;
};

export type PlotDefaults = {
  ll: [number, number, number];
  ur: [number, number, number];
  origin: [number, number, number];
  pad: number;
};

function fileStamp(name: string): string {
  const target = path.join(RUN_DIR, name);
  try {
    const st = fs.statSync(target);
    return `${st.mtimeMs}:${st.size}`;
  } catch {
    return "missing";
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function readPlotDefaults(): PlotDefaults | null {
  const target = path.join(RUN_DIR, PLOT_DEFAULTS);
  try {
    const parsed = JSON.parse(fs.readFileSync(target, "utf8")) as Record<string, unknown>;
    const ll = parsed.ll;
    const ur = parsed.ur;
    if (
      !Array.isArray(ll) ||
      !Array.isArray(ur) ||
      ll.length !== 3 ||
      ur.length !== 3 ||
      !ll.every(isFiniteNumber) ||
      !ur.every(isFiniteNumber)
    ) {
      return null;
    }
    const originRaw = parsed.origin;
    const origin: [number, number, number] =
      Array.isArray(originRaw) && originRaw.length === 3 && originRaw.every(isFiniteNumber)
        ? [originRaw[0], originRaw[1], originRaw[2]]
        : [
            0.5 * (ll[0] + ur[0]),
            0.5 * (ll[1] + ur[1]),
            0.5 * (ll[2] + ur[2]),
          ];
    const pad = isFiniteNumber(parsed.pad) && parsed.pad > 0 ? parsed.pad : PAD;
    return {
      ll: [ll[0], ll[1], ll[2]],
      ur: [ur[0], ur[1], ur[2]],
      origin,
      pad,
    };
  } catch {
    return null;
  }
}

/** Width/height/origin that envelope the reactor for one basis plane. */
export function viewForBasis(
  defaults: PlotDefaults,
  basis: Basis,
): { width: number; height: number; origin: [number, number, number] } {
  const spans: [number, number, number] = [
    Math.max(1e-6, (defaults.ur[0] - defaults.ll[0]) * defaults.pad),
    Math.max(1e-6, (defaults.ur[1] - defaults.ll[1]) * defaults.pad),
    Math.max(1e-6, (defaults.ur[2] - defaults.ll[2]) * defaults.pad),
  ];
  // Center on the bounding box. defaults.origin is the fuel point, which is
  // not the middle of the disk, so a full-span window centered there clips the far side.
  const origin: [number, number, number] = [
    0.5 * (defaults.ll[0] + defaults.ur[0]),
    0.5 * (defaults.ll[1] + defaults.ur[1]),
    0.5 * (defaults.ll[2] + defaults.ur[2]),
  ];
  if (basis === "xy") return { width: spans[0], height: spans[1], origin };
  if (basis === "xz") return { width: spans[0], height: spans[2], origin };
  return { width: spans[1], height: spans[2], origin };
}

export function geometryStatus() {
  const hasGeometry = fs.existsSync(path.join(RUN_DIR, "geometry.xml"));
  const hasMaterials = fs.existsSync(path.join(RUN_DIR, "materials.xml"));
  const defaults = readPlotDefaults();
  const suggested = defaults
    ? {
        xy: viewForBasis(defaults, "xy"),
        xz: viewForBasis(defaults, "xz"),
        yz: viewForBasis(defaults, "yz"),
      }
    : null;
  return {
    ready: hasGeometry && hasMaterials,
    hasGeometry,
    hasMaterials,
    hasDefaults: Boolean(defaults),
    defaults,
    suggested,
    /** Changes when exported XMLs are rewritten (invalidates client plot cache). */
    fingerprint: `${fileStamp("geometry.xml")}|${fileStamp("materials.xml")}|${fileStamp(PLOT_DEFAULTS)}`,
    runDir: RUN_DIR,
  };
}

export function parsePlotRequest(body: unknown): PlotRequest {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new GeometryPlotError("Expected a JSON object body.");
  }
  const raw = body as Record<string, unknown>;
  const basis = raw.basis;
  if (basis !== "xy" && basis !== "xz" && basis !== "yz") {
    throw new GeometryPlotError('basis must be "xy", "xz", or "yz".');
  }

  const defaults = readPlotDefaults();
  const auto = defaults ? viewForBasis(defaults, basis) : null;

  let origin: [number, number, number];
  const originRaw = raw.origin;
  if (originRaw === undefined || originRaw === null) {
    if (!auto) throw new GeometryPlotError("origin is required when plot_defaults.json is missing.");
    origin = auto.origin;
  } else if (Array.isArray(originRaw) && originRaw.length === 3 && originRaw.every(isFiniteNumber)) {
    origin = [originRaw[0], originRaw[1], originRaw[2]];
  } else {
    throw new GeometryPlotError("origin must be [x, y, z] numbers in cm.");
  }

  let width: number;
  if (raw.width === undefined || raw.width === null) {
    if (!auto) throw new GeometryPlotError("width is required when plot_defaults.json is missing.");
    width = auto.width;
  } else if (isFiniteNumber(raw.width) && raw.width > 0) {
    width = raw.width;
  } else {
    throw new GeometryPlotError("width must be a positive number (cm).");
  }

  let height: number;
  if (raw.height === undefined || raw.height === null) {
    height = auto ? auto.height : width;
  } else if (isFiniteNumber(raw.height) && raw.height > 0) {
    height = raw.height;
  } else {
    throw new GeometryPlotError("height must be a positive number (cm).");
  }

  const pixels =
    raw.pixels === undefined || raw.pixels === null
      ? 600
      : isFiniteNumber(raw.pixels) && raw.pixels >= 16
        ? Math.min(1000, Math.round(raw.pixels))
        : (() => {
            throw new GeometryPlotError("pixels must be between 16 and 1000.");
          })();

  return { basis, origin, width, height, pixels };
}

function runDockerPlot(req: PlotRequest): Promise<{ code: number; stderr: string; stdout: string }> {
  return new Promise((resolve) => {
    const args = [
      "compose",
      "run",
      "--rm",
      "rimag",
      "python",
      "plot_geometry_slice.py",
      "--basis",
      req.basis,
      "--origin",
      String(req.origin[0]),
      String(req.origin[1]),
      String(req.origin[2]),
      "--width",
      String(req.width),
      "--height",
      String(req.height),
      "--pixels",
      String(req.pixels ?? 600),
      "--out",
      PLOT_OUT,
    ];

    const child = spawn("docker", args, {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        RIMAG_RUN_DIR: RUN_DIR,
        PYTHONUNBUFFERED: "1",
      },
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      resolve({ code: 1, stdout, stderr: `${stderr}\n${error.message}`.trim() });
    });
    child.on("close", (code) => {
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

/** Run OpenMC plot mode; returns absolute path to the PNG. */
export async function plotGeometrySlice(body: unknown): Promise<string> {
  const status = geometryStatus();
  if (!status.ready) {
    throw new GeometryPlotError(
      "geometry.xml / materials.xml not found in runs/default. Run a simulation (render mode is enough) first.",
      404,
    );
  }

  const req = parsePlotRequest(body);
  // A full sync rewrites common_lib and app_slice_design in the live run folder.
  // During transport, only refresh the plot script. The plot itself reads copies
  // of the XML in .plot_stage and does not rewrite the run's geometry or summary.
  if (isSimulationRunning()) syncPlotScriptIntoRunDir();
  else syncRimagSourcesIntoRunDir();

  const outPath = path.join(RUN_DIR, PLOT_OUT);
  if (fs.existsSync(outPath)) {
    try {
      fs.unlinkSync(outPath);
    } catch {
      // ignore
    }
  }

  const { code, stderr, stdout } = await runDockerPlot(req);
  if (code !== 0 || !fs.existsSync(outPath)) {
    const detail = (stderr || stdout).trim().slice(-2000) || `docker exit ${code}`;
    throw new GeometryPlotError(`Plot failed: ${detail}`, 500);
  }
  return outPath;
}
