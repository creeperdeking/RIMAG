export const ZONE_COLORS = {
  fuel: "#f59e0b",
  opposite: "#3b82f6",
  reflector: "#0f766e",
  gap: "#94a3b8",
  absorber: "#475569",
} as const;

export const LAYER_GROUPS = [
  ["fuel", "Fuel layer", ["#f59e0b", "#d97706", "#b45309", "#fbbf24"]],
  ["reflector", "Reflector layer", ["#0f766e", "#115e59", "#134e4a", "#14b8a6"]],
  ["shield_moderator", "Shield moderator", ["#94a3b8", "#64748b", "#cbd5e1", "#475569"]],
  ["shield_absorber", "Shield absorber", ["#475569", "#334155", "#1e293b", "#64748b"]],
  ["tpv", "TPV layer", ["#3b82f6", "#2563eb", "#1d4ed8", "#60a5fa"]],
] as const;

export const DISK_GROUP = ["disk", "Disk layer", ["#000000", "#171717", "#404040", "#737373"]] as const;

/** One material for the hole on the fuel-to-TPV chord. Not part of the disc stack. */
export const INNER_SHIELD_GROUP = [
  "inner_shield_moderator",
  "Inner neutron shield moderator",
] as const;

export const EDITOR_GROUPS = [DISK_GROUP, ...LAYER_GROUPS] as const;

export type LayerGroupId =
  | "disk"
  | "fuel"
  | "reflector"
  | "shield_moderator"
  | "inner_shield_moderator"
  | "shield_absorber"
  | "tpv";

export const LAYER_MATCH_NOTE =
  "The disk layer sits on top of every stack. Fuel, reflector, shield moderator, " +
  "shield absorber, and TPV, each plus the disk, must have the same thickness.";

export const TAB_KEYS = [
  "overview",
  "fuel",
  "designer",
  "thermophotovoltaics",
  "thermodynamic",
  "simulation",
  "visualisation",
] as const;
export type TabKey = (typeof TAB_KEYS)[number];

/** Materials accepted as the neutron shield moderator. */
export const NSM_MATERIALS = [
  "Graphite",
  "Natural Graphite",
  "Low Density Graphite",
  "Graphite NO Scattering",
  "Beryllium Oxide",
  "High Density PolyEthylene",
  "Titanium Hydride",
  "Light Water",
  "Lithium Oxide",
] as const;
export type NsmMaterial = (typeof NSM_MATERIALS)[number];

export const RUN_MODES = [
  "keff",
  "keff_notallies",
  "render",
  "depletion",
  "keff_emitter_gamma_source",
  "keff_gamma_dose",
  "norun",
  "slab",
] as const;
export type RunMode = (typeof RUN_MODES)[number];

export const PARTICLE_TYPES = ["neutron", "photon"] as const;
export type ParticleType = (typeof PARTICLE_TYPES)[number];

/** Off / use for tallies. Seed+refine are triggered from the WW submenu, not this list. */
export const WEIGHT_WINDOWS = ["no", "use"] as const;
export type WeightWindows = (typeof WEIGHT_WINDOWS)[number];

/** Full set for queue items (includes build passes). Autorefine is expanded to refine by the runner. */
export const WEIGHT_WINDOWS_RUN = ["no", "use", "generate", "seed", "refine", "autorefine"] as const;
export type WeightWindowsRun = (typeof WEIGHT_WINDOWS_RUN)[number];
