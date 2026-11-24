import type { Setup } from "./configurations";
import type { LayerRow } from "./geometry";

export type SlabRole = "reflector" | "moderator" | "absorber" | "detector";

/** One block of the 1D shield chord, fuel side first. Thickness is centimetres. */
export type SlabLayerSpec = {
  name: string;
  cm: number;
  role: SlabRole;
};

const ROLES: readonly SlabRole[] = ["reflector", "moderator", "absorber", "detector"];

function resolveMaterialName(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "Void";
  if (trimmed === "Disk" || trimmed === "disk") return "Graphite";
  return trimmed;
}

function namesOf(rows: LayerRow[] | undefined): string[] {
  return (rows ?? []).map((row) => resolveMaterialName(row.name));
}

function firstSolid(rows: LayerRow[] | undefined, fallback: string): string {
  const solid = namesOf(rows).find((name) => name !== "Void");
  return solid ?? fallback;
}

function roundCm(cm: number): number {
  return Math.round(cm * 10000) / 10000;
}

/**
 * Chord the fast slab transports, in the same order and thicknesses as the
 * full geometry. When the reflector and shield-moderator layer names match,
 * those metres are one block of the neutron-shield material. The last cell
 * is 1 cm of void, where the damage-weighted flux is scored.
 */
export function slabLayersFromSetup(setup: Setup): SlabLayerSpec[] {
  const reflectorRows = setup.layers.reflector ?? [];
  const moderatorRows = setup.layers.shield_moderator ?? [];
  const reflectorNames = namesOf(reflectorRows);
  const moderatorNames = namesOf(moderatorRows);
  const merged =
    reflectorNames.length > 0 && reflectorNames.join("\0") === moderatorNames.join("\0");
  const moderatorCm = (merged ? setup.a + setup.refl : setup.a) * 100;
  const reflectorCm = merged ? 0 : setup.refl * 100;
  const absorberCm = setup.abs * 100;
  const layers: SlabLayerSpec[] = [];
  if (reflectorCm > 1e-6) {
    layers.push({
      role: "reflector",
      name: firstSolid(reflectorRows, "Graphite"),
      cm: roundCm(reflectorCm),
    });
  }
  if (moderatorCm > 1e-6) {
    layers.push({
      role: "moderator",
      name: resolveMaterialName(setup.simulation.nsm_material || "Graphite"),
      cm: roundCm(moderatorCm),
    });
  }
  if (absorberCm > 1e-6) {
    layers.push({
      role: "absorber",
      name: firstSolid(setup.layers.shield_absorber, "Boron Carbide"),
      cm: roundCm(absorberCm),
    });
  }
  layers.push({ role: "detector", name: "void", cm: 1 });
  return layers;
}

export function parseSlabLayers(raw: unknown): SlabLayerSpec[] {
  if (!Array.isArray(raw)) return [];
  const layers: SlabLayerSpec[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const role = String(record.role ?? "");
    if (!(ROLES as readonly string[]).includes(role)) continue;
    const cm = Number(record.cm);
    if (!Number.isFinite(cm) || cm <= 0) continue;
    const name = String(record.name ?? "").trim();
    if (!name) continue;
    layers.push({ name, cm: roundCm(cm), role: role as SlabRole });
  }
  return layers;
}
