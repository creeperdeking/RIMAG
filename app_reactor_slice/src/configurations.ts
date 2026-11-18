import type { LayerGroupId } from "./constants";
import type { LayerRow } from "./geometry";

export const NUMERIC_FIELDS = {
  a: [1.0, 4.0, 0.1, 2.0],
  abs: [0.01, 0.5, 0.01, 0.01],
  refl: [0.1, 1.0, 0.1, 0.5],
  b_pct: [1.0, 100.0, 1.0, 100.0],
  w: [0.3, 3.0, 0.1, 1.0],
  ratio_pct: [10.0, 50.0, 1.0, 30.0],
  tpv_density: [0.01, 3.0, 0.01, 0.89],
  enrichment_pct: [0.1, 20.0, 0.1, 5.0],
  packing_pct: [1.0, 30.0, 1.0, 30.0],
  hm_particle_pct: [20.0, 60.0, 1.0, 30.0],
  cylinder_diameter_mm: [2.0, 30.0, 0.1, 10.0],
  wall_margin_mm: [0.0, 5.0, 0.1, 0.5],
  compact_spacing_mm: [0.0, 10.0, 0.1, 1.0],
  tpv_eff_pct: [10.0, 50.0, 1.0, 33.0],
  fuel_temp_c: [800.0, 1600.0, 10.0, 1150.0],
  stack_m: [0.1, 20.0, 0.1, 1.0],
  columns: [1.0, 3.0, 1.0, 1.0],
} as const;

export type NumericKey = keyof typeof NUMERIC_FIELDS;

export const RELOAD_FRACTIONS = ["1/2", "1/3", "1/4", "1/5"] as const;
export type ReloadFraction = (typeof RELOAD_FRACTIONS)[number];

export const LAYER_IDS: LayerGroupId[] = [
  "disk",
  "fuel",
  "reflector",
  "shield_moderator",
  "shield_absorber",
  "tpv",
];

export const LAYER_TITLES: Record<LayerGroupId, string> = {
  disk: "Disk layer",
  fuel: "Fuel layer",
  reflector: "Reflector layer",
  shield_moderator: "Shield moderator",
  shield_absorber: "Shield absorber",
  tpv: "TPV layer",
};

export type Setup = {
  [K in NumericKey]: number;
} & {
  reload_fraction: ReloadFraction;
  dims: boolean;
  layers: Record<LayerGroupId, LayerRow[]>;
};

export function snap(value: number, low: number, high: number, step: number): number {
  let next = Math.min(high, Math.max(low, value));
  if (step <= 0) return next;
  const snapped = low + Math.round((next - low) / step) * step;
  return Math.min(high, Math.max(low, Math.round(snapped * 1e10) / 1e10));
}

function normalizeLayers(raw: unknown): Record<LayerGroupId, LayerRow[]> {
  const source = raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  const layers = {} as Record<LayerGroupId, LayerRow[]>;
  for (const groupId of LAYER_IDS) {
    const rows = source[groupId];
    const parsed: LayerRow[] = [];
    if (Array.isArray(rows)) {
      for (const item of rows) {
        if (!item || typeof item !== "object") continue;
        const record = item as Record<string, unknown>;
        const cm = Number(record.cm);
        if (!Number.isFinite(cm)) continue;
        const name = String(record.name ?? record.n ?? "").trim() || LAYER_TITLES[groupId];
        parsed.push({ name, cm: Math.round(Math.min(20, Math.max(0.01, cm)) * 10000) / 10000 });
      }
    }
    layers[groupId] = parsed.length ? parsed : [{ name: LAYER_TITLES[groupId], cm: 1 }];
  }
  return layers;
}

export function defaultSetup(): Setup {
  const values = {} as Setup;
  for (const [key, [, , , def]] of Object.entries(NUMERIC_FIELDS) as Array<[NumericKey, readonly [number, number, number, number]]>) {
    values[key] = def;
  }
  values.reload_fraction = "1/4";
  values.dims = true;
  values.layers = normalizeLayers(null);
  return values;
}

export function normalizeSetup(data: unknown): Setup {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("That file is not a configuration.");
  }
  const raw = data as Record<string, unknown>;
  const values = defaultSetup();
  for (const [key, [low, high, step, def]] of Object.entries(NUMERIC_FIELDS) as Array<
    [NumericKey, readonly [number, number, number, number]]
  >) {
    let number = Number(raw[key] ?? def);
    if (!Number.isFinite(number)) number = def;
    if (key === "tpv_density" && number > high) number /= 10;
    values[key] = snap(number, low, high, step);
  }
  const reload = raw.reload_fraction;
  values.reload_fraction =
    typeof reload === "string" && (RELOAD_FRACTIONS as readonly string[]).includes(reload)
      ? (reload as ReloadFraction)
      : "1/4";
  const dims = raw.dims;
  if (typeof dims === "string") {
    values.dims = ["1", "true", "yes"].includes(dims.trim().toLowerCase());
  } else if (dims === undefined) {
    values.dims = true;
  } else {
    values.dims = Boolean(dims);
  }
  values.layers = normalizeLayers(raw.layers);
  return values;
}

export function formatPower(kw: number): string {
  if (kw >= 1000) return `${Number((kw / 1000).toPrecision(4))} MW`;
  return `${Number(kw.toPrecision(4))} kW`;
}

export function reloadShare(label: string): number {
  const [numerator, denominator] = label.split("/");
  return Number(numerator) / Number(denominator);
}
