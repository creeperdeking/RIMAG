import {
  NSM_MATERIALS,
  PARTICLE_TYPES,
  RUN_MODES,
  WEIGHT_WINDOWS,
  type LayerGroupId,
  type NsmMaterial,
  type ParticleType,
  type RunMode,
  type WeightWindows,
} from "./constants";
import type { LayerRow } from "./geometry";

export type { WeightWindowsRun } from "./constants";

export const NUMERIC_FIELDS = {
  a: [1.0, 4.0, 0.1, 2.0],
  abs: [0.01, 0.5, 0.01, 0.01],
  refl: [0.1, 1.0, 0.1, 0.5],
  b_pct: [1.0, 100.0, 1.0, 100.0],
  w: [0.3, 3.0, 0.1, 1.0],
  ratio_pct: [10.0, 50.0, 1.0, 30.0],
  enrichment_pct: [0.1, 20.0, 0.1, 5.0],
  packing_pct: [1.0, 30.0, 1.0, 30.0],
  hm_particle_pct: [20.0, 60.0, 1.0, 30.0],
  cylinder_diameter_mm: [2.0, 30.0, 0.1, 10.0],
  wall_margin_mm: [0.0, 5.0, 0.1, 0.5],
  compact_spacing_mm: [0.0, 10.0, 0.1, 1.0],
  fuel_temp_c: [800.0, 1600.0, 10.0, 1150.0],
  fuel_emissivity: [0.05, 1.0, 0.01, 0.85],
  disk_emissivity: [0.05, 1.0, 0.01, 0.85],
  /**
   * Gray emissivity of the vacuum shell, both faces. The disk side uses it in the
   * helium gap. The cell side uses it in the closed-gap spectrum.
   */
  shell_emissivity: [0.05, 1.0, 0.01, 0.3],
  /** Air-bridge chart: 0 = 0.74 eV, 1 = 0.90 eV, 2 = 1.10 eV. */
  tpv_airbridge_cell: [0, 2, 1, 0],
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

export type SimulationParams = {
  run_mode: RunMode;
  n_batches: number;
  n_threads: number;
  nsm_material: NsmMaterial;
  nsm_thickness: number;
  conical_pitch: number;
  particle_type: ParticleType;
  weight_windows: WeightWindows;
  survival_biasing: boolean;
  dose_time: number;
  print_core_characteristics: boolean;
  boron_concentration_ppm: number;
  ddd_tallies_only: boolean;
  ww_mesh_cm: number;
  ww_energy_groups: number;
  /** Whole-stack thermal power [MW]. The run scales it to one periodic slice. null → thermodynamics-tab period power. */
  thermal_power_mw: number | null;
};

export const DEFAULT_SIMULATION_PARAMS: SimulationParams = {
  run_mode: "keff",
  n_batches: 200,
  n_threads: 10,
  nsm_material: "Graphite",
  nsm_thickness: 25,
  conical_pitch: 15,
  particle_type: "neutron",
  weight_windows: "no",
  survival_biasing: false,
  dose_time: 10,
  print_core_characteristics: true,
  boron_concentration_ppm: 0,
  ddd_tallies_only: true,
  ww_mesh_cm: 40,
  ww_energy_groups: 10,
  thermal_power_mw: null,
};

function pickBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    return ["1", "true", "yes"].includes(value.trim().toLowerCase());
  }
  return fallback;
}

export type Setup = {
  [K in NumericKey]: number;
} & {
  /** Electrical power density from the air-bridge chart [W/cm²]. Calculated. */
  tpv_density: number;
  /** Conversion efficiency from the air-bridge chart [%]. Calculated. */
  tpv_eff_pct: number;
  /** Heat the cell absorbs, one face [W/cm²]. Calculated. */
  tpv_absorbed_w_per_cm2: number;
  /** Vacuum-shell temperature the cells see [°C]. Calculated. */
  shell_temp_c: number;
  /** Thermodynamics-tab heat for one pitch and every column [W]. */
  period_thermal_w: number;
  /** Thermodynamics-tab electrical power for one pitch and every column [W]. */
  period_electric_w: number;
  reload_fraction: ReloadFraction;
  dims: boolean;
  layers: Record<LayerGroupId, LayerRow[]>;
  simulation: SimulationParams;
};

function pickEnum<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

export function normalizeSimulation(raw: unknown): SimulationParams {
  const source = raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  const batches = Number(source.n_batches);
  const threads = Number(source.n_threads);
  const nsmThickness = Number(source.nsm_thickness);
  const conicalPitch = Number(source.conical_pitch);
  const doseTime = Number(source.dose_time);
  const boronPpm = Number(source.boron_concentration_ppm);
  const wwMesh = Number(source.ww_mesh_cm);
  const wwGroups = Number(source.ww_energy_groups);
  const thermalMw = Number(source.thermal_power_mw);
  // Legacy "generate" in saved setups maps to "use" for the tally dropdown;
  // seed/refine are started from the WW submenu, not stored as the tally mode.
  const rawWw = typeof source.weight_windows === "string" ? source.weight_windows : "";
  const weightWindows: WeightWindows =
    rawWw === "use" || rawWw === "generate"
      ? "use"
      : pickEnum(source.weight_windows, WEIGHT_WINDOWS, DEFAULT_SIMULATION_PARAMS.weight_windows);
  return {
    run_mode: pickEnum(source.run_mode, RUN_MODES, DEFAULT_SIMULATION_PARAMS.run_mode),
    n_batches: Number.isFinite(batches) ? Math.max(1, Math.round(batches)) : DEFAULT_SIMULATION_PARAMS.n_batches,
    n_threads: Number.isFinite(threads)
      ? Math.max(1, Math.min(256, Math.round(threads)))
      : DEFAULT_SIMULATION_PARAMS.n_threads,
    nsm_material: pickEnum(source.nsm_material, NSM_MATERIALS, DEFAULT_SIMULATION_PARAMS.nsm_material),
    nsm_thickness: Number.isFinite(nsmThickness) && nsmThickness >= 0 ? nsmThickness : DEFAULT_SIMULATION_PARAMS.nsm_thickness,
    conical_pitch: Number.isFinite(conicalPitch) && conicalPitch >= 0 ? conicalPitch : DEFAULT_SIMULATION_PARAMS.conical_pitch,
    particle_type: pickEnum(source.particle_type, PARTICLE_TYPES, DEFAULT_SIMULATION_PARAMS.particle_type),
    weight_windows: weightWindows,
    survival_biasing: pickBoolean(source.survival_biasing, DEFAULT_SIMULATION_PARAMS.survival_biasing),
    dose_time: Number.isFinite(doseTime) && doseTime >= 0 ? doseTime : DEFAULT_SIMULATION_PARAMS.dose_time,
    print_core_characteristics: pickBoolean(
      source.print_core_characteristics,
      DEFAULT_SIMULATION_PARAMS.print_core_characteristics,
    ),
    boron_concentration_ppm:
      Number.isFinite(boronPpm) && boronPpm >= 0
        ? boronPpm
        : DEFAULT_SIMULATION_PARAMS.boron_concentration_ppm,
    ddd_tallies_only: pickBoolean(source.ddd_tallies_only, DEFAULT_SIMULATION_PARAMS.ddd_tallies_only),
    ww_mesh_cm:
      Number.isFinite(wwMesh) && wwMesh > 0 ? wwMesh : DEFAULT_SIMULATION_PARAMS.ww_mesh_cm,
    ww_energy_groups: Number.isFinite(wwGroups)
      ? Math.max(1, Math.min(200, Math.round(wwGroups)))
      : DEFAULT_SIMULATION_PARAMS.ww_energy_groups,
    thermal_power_mw:
      source.thermal_power_mw == null || source.thermal_power_mw === ""
        ? null
        : Number.isFinite(thermalMw) && thermalMw > 0
          ? thermalMw
          : null,
  };
}

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
  values.tpv_density = 0;
  values.tpv_eff_pct = 0;
  values.tpv_absorbed_w_per_cm2 = 0;
  values.shell_temp_c = 0;
  values.period_thermal_w = 0;
  values.period_electric_w = 0;
  values.reload_fraction = "1/4";
  values.dims = true;
  values.layers = normalizeLayers(null);
  values.simulation = { ...DEFAULT_SIMULATION_PARAMS };
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
    values[key] = snap(number, low, high, step);
  }
  const output = (
    key:
      | "tpv_density"
      | "tpv_eff_pct"
      | "tpv_absorbed_w_per_cm2"
      | "shell_temp_c"
      | "period_thermal_w"
      | "period_electric_w",
  ) => {
    const number = Number(raw[key]);
    values[key] = Number.isFinite(number) ? number : 0;
  };
  output("tpv_density");
  output("tpv_eff_pct");
  output("tpv_absorbed_w_per_cm2");
  output("shell_temp_c");
  output("period_thermal_w");
  output("period_electric_w");
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
  values.simulation = normalizeSimulation(raw.simulation);
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
