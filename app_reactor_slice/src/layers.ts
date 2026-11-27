import { EDITOR_GROUPS, LAYER_GROUPS, type LayerGroupId } from "./constants";
import { LAYER_TITLES, type Setup } from "./configurations";
import type { LayerRow } from "./geometry";
import { trisoFuelLayers } from "./geometry";

export type Groups = Record<LayerGroupId, LayerRow[]>;

export function defaultGroups(): Groups {
  const groups = {} as Groups;
  for (const [groupId, title] of EDITOR_GROUPS) {
    groups[groupId as LayerGroupId] = [{ name: title, cm: 1 }];
  }
  return groups;
}

export function sameLayers(left: LayerRow[], right: LayerRow[]): boolean {
  if (left.length !== right.length) return false;
  return left.every((one, index) => {
    const other = right[index];
    return one.name === other.name && Math.abs(one.cm - other.cm) <= 1e-4;
  });
}

export function sameMaterialNames(left: LayerRow[], right: LayerRow[]): boolean {
  const namesLeft = left.map((row) => String(row.name ?? "").trim());
  const namesRight = right.map((row) => String(row.name ?? "").trim());
  return Boolean(namesLeft.length) && namesLeft.every((name, index) => name === namesRight[index]);
}

function solidMaterialNames(rows: LayerRow[]): string[] {
  return rows
    .map((row) => String(row.name ?? "").trim())
    .filter((name) => name && name.toLowerCase() !== "void");
}

/** Graphite-like reflector and shield moderator share one fuel-to-TPV chord. */
export function sharedGraphiteChord(
  left: LayerRow[],
  right: LayerRow[],
  isGraphite: (name: string) => boolean,
): boolean {
  const leftNames = solidMaterialNames(left);
  const rightNames = solidMaterialNames(right);
  if (!leftNames.length || !rightNames.length) return false;
  return leftNames.every(isGraphite) && rightNames.every(isGraphite);
}

export function groupThicknesses(groups: Groups): Array<[string, number]> {
  const diskCm = (groups.disk ?? []).reduce((sum, layer) => sum + layer.cm, 0);
  return LAYER_GROUPS.map(([groupId, title]) => {
    const own = (groups[groupId as LayerGroupId] ?? []).reduce((sum, layer) => sum + layer.cm, 0);
    return [title, own + diskCm] as [string, number];
  });
}

/** Solid layer thickness excluding Void / He gaps. */
export function solidLayerThicknessCm(layers: LayerRow[] | undefined, fallbackCm: number): number {
  const rows = layers ?? [];
  const solid = rows.filter((row) => String(row.name ?? "").trim().toLowerCase() !== "void");
  const sum = solid.reduce((total, row) => total + row.cm, 0);
  if (sum > 0) return sum;
  const total = rows.reduce((acc, row) => acc + row.cm, 0);
  return total > 0 ? total : fallbackCm;
}

/** Solid disk thickness for Modelica (excludes Void / He gaps). */
export function solidDiskThicknessCm(diskLayers: LayerRow[] | undefined): number {
  return solidLayerThicknessCm(diskLayers, 0.8);
}

function isVoidLayer(row: LayerRow): boolean {
  return String(row.name ?? "").trim().toLowerCase() === "void";
}

/**
 * Helium gaps on the two faces of the disk [cm].
 * Leading Void sheets face the fuel; trailing Void sheets face the TPV shell.
 * A Void buried between disk solids is split equally across the two faces.
 */
export function diskHeliumGapsCm(diskLayers: LayerRow[] | undefined): { fuelGapCm: number; tpvGapCm: number } {
  const rows = diskLayers ?? [];
  let index = 0;
  let leading = 0;
  while (index < rows.length && isVoidLayer(rows[index])) {
    leading += rows[index].cm;
    index += 1;
  }
  let end = rows.length - 1;
  let trailing = 0;
  while (end >= index && isVoidLayer(rows[end])) {
    trailing += rows[end].cm;
    end -= 1;
  }
  if (leading > 0 || trailing > 0) return { fuelGapCm: leading, tpvGapCm: trailing };
  const buried = rows.reduce((sum, row) => sum + (isVoidLayer(row) ? row.cm : 0), 0);
  return { fuelGapCm: buried / 2, tpvGapCm: buried / 2 };
}

/** Solid fuel-stack thickness for Modelica FuelPlate (excludes Void). */
export function solidFuelThicknessCm(fuelLayers: LayerRow[] | undefined): number {
  return solidLayerThicknessCm(fuelLayers, 1.0);
}

export function sharedThickness(totals: Array<[string, number]>): number | null {
  const rounded = new Set(totals.map(([, cm]) => Math.round(cm * 100) / 100));
  if (rounded.size !== 1) return null;
  return totals[0][1];
}

export function thicknessWarning(totals: Array<[string, number]>): string {
  const parts = totals.map(([title, cm]) => `${title} is ${cm.toFixed(2)} cm`);
  if (parts.length <= 1) return parts[0] ?? "";
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}.`;
}

export function applyTrisoFuel(
  groups: Groups,
  diameterMm: number,
  wallMarginMm: number,
  spacingMm: number,
  packingPct: number,
  hmParticlePct: number,
): { groups: Groups; particleInCylinder: number; hmFraction: number; layers: LayerRow[] } {
  const { layers, particleInCylinder, hmFraction } = trisoFuelLayers(
    diameterMm,
    wallMarginMm,
    spacingMm,
    packingPct,
    hmParticlePct,
  );
  if (sameLayers(groups.fuel ?? [], layers)) {
    return { groups, particleInCylinder, hmFraction, layers };
  }
  return {
    groups: { ...groups, fuel: layers },
    particleInCylinder,
    hmFraction,
    layers,
  };
}

export function setupFromState(setup: Setup, groups: Groups): Setup {
  return {
    ...setup,
    layers: Object.fromEntries(
      (Object.keys(LAYER_TITLES) as LayerGroupId[]).map((id) => [
        id,
        (groups[id] ?? []).map((row) => ({ name: row.name, cm: row.cm })),
      ]),
    ) as Groups,
  };
}
