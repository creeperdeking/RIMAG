import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const SIDES = 64;

const SCRIPT = path.resolve("server/copy_reactor.py");

export class BlenderClipboardError extends Error {}

function versionKey(filePath: string): number[] {
  const numbers: number[] = [];
  for (const part of filePath.split(/[\\/]/)) {
    for (const match of part.match(/\d+/g) ?? []) numbers.push(Number(match));
  }
  return numbers.length ? numbers : [0];
}

function newer(left: string, right: string): string {
  const a = versionKey(left);
  const b = versionKey(right);
  const count = Math.max(a.length, b.length);
  for (let i = 0; i < count; i += 1) {
    const diff = (a[i] ?? 0) - (b[i] ?? 0);
    if (diff > 0) return left;
    if (diff < 0) return right;
  }
  return left;
}

export function findBlender(): string | null {
  const candidates: string[] = [];
  const override = process.env.BLENDER_EXECUTABLE;
  if (override) candidates.push(override);
  const pathEntries = (process.env.PATH ?? "").split(path.delimiter).filter(Boolean);
  for (const entry of pathEntries) {
    candidates.push(path.join(entry, "blender.exe"), path.join(entry, "blender"));
  }
  for (const key of ["ProgramFiles", "ProgramFiles(x86)"]) {
    const root = process.env[key];
    if (!root) continue;
    const base = path.join(root, "Blender Foundation");
    if (!fs.existsSync(base)) continue;
    for (const folder of fs.readdirSync(base, { withFileTypes: true })) {
      if (!folder.isDirectory()) continue;
      candidates.push(path.join(base, folder.name, "blender.exe"));
    }
  }
  const existing = candidates.filter((candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
  if (!existing.length) return null;
  return existing.reduce(newer);
}

function failureText(stdout: string, stderr: string): string {
  const lines = `${stdout}\n${stderr}`
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("Blender "));
  if (!lines.length) return "Blender could not build the reactor model.";
  return lines.slice(-8).join("\n");
}

type Report = {
  path: string;
  columns: Array<{
    side_faces: number;
    diameter: number;
    height: number;
    location: [number, number, number];
  }>;
};

function checkReport(payload: Report, radius: number, height: number, centers: Array<[number, number]>) {
  if (!Array.isArray(payload.columns) || payload.columns.length !== centers.length) {
    throw new BlenderClipboardError("Blender wrote the wrong number of cylinders.");
  }
  payload.columns.forEach((column, index) => {
    const center = centers[index];
    if (column.side_faces !== SIDES) {
      throw new BlenderClipboardError(`The cylinder does not have ${SIDES} side faces.`);
    }
    if (Math.abs(column.diameter - 2 * radius) > 1e-3) {
      throw new BlenderClipboardError("Cylinder diameter does not match the reactor.");
    }
    if (Math.abs(column.height - height) > 1e-3) {
      throw new BlenderClipboardError("Cylinder height does not match the stack.");
    }
    const [x, y, z] = column.location;
    if (Math.abs(x - center[0]) > 1e-3 || Math.abs(y - center[1]) > 1e-3) {
      throw new BlenderClipboardError("A cylinder is in the wrong place.");
    }
    if (Math.abs(z - height / 2) > 1e-3) {
      throw new BlenderClipboardError("A cylinder is not standing on the ground plane.");
    }
  });
}

export async function copyColumnsToBlender(
  radius: number,
  height: number,
  centers: Array<[number, number]>,
): Promise<string> {
  if (!(radius > 0) || !(height > 0) || !Number.isFinite(radius) || !Number.isFinite(height)) {
    throw new BlenderClipboardError("Cylinder size must be positive.");
  }
  if (!centers.length || centers.some(([x, y]) => !Number.isFinite(x) || !Number.isFinite(y))) {
    throw new BlenderClipboardError("Column positions must be finite.");
  }
  const blender = findBlender();
  if (!blender) {
    throw new BlenderClipboardError("Blender was not found. Install it, or add blender.exe to PATH.");
  }
  if (!fs.existsSync(SCRIPT)) {
    throw new BlenderClipboardError("The Blender copy script is missing.");
  }

  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "rimag-reactor-"));
  const specPath = path.join(folder, "reactor.json");
  const resultPath = path.join(folder, "result.json");
  fs.writeFileSync(specPath, JSON.stringify({ radius, height, sides: SIDES, centers }), "utf8");
  let payload: Report;
  try {
    try {
      await execFileAsync(blender, ["--background", "--python", SCRIPT, "--", specPath, resultPath], {
        timeout: 120_000,
        windowsHide: true,
        maxBuffer: 10 * 1024 * 1024,
      });
    } catch (error) {
      const failed = error as { stdout?: string; stderr?: string; killed?: boolean };
      if (failed.killed) throw new BlenderClipboardError("Blender took too long to build the reactor.");
      throw new BlenderClipboardError(failureText(String(failed.stdout ?? ""), String(failed.stderr ?? "")));
    }
    if (!fs.existsSync(resultPath)) {
      throw new BlenderClipboardError("Blender could not build the reactor model.");
    }
    payload = JSON.parse(fs.readFileSync(resultPath, "utf8")) as Report;
  } finally {
    fs.rmSync(folder, { recursive: true, force: true });
  }
  checkReport(payload, radius, height, centers);
  const written = Buffer.from(fs.readFileSync(payload.path).subarray(0, 7)).toString("utf8");
  if (written !== "BLENDER") {
    throw new BlenderClipboardError("Blender did not write a model file.");
  }
  return payload.path;
}
