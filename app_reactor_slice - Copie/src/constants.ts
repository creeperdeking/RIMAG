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

export const EDITOR_GROUPS = [DISK_GROUP, ...LAYER_GROUPS] as const;

export type LayerGroupId =
  | "disk"
  | "fuel"
  | "reflector"
  | "shield_moderator"
  | "shield_absorber"
  | "tpv";

export const LAYER_MATCH_NOTE =
  "The disk layer sits on top of every stack. Fuel, reflector, shield moderator, " +
  "shield absorber, and TPV, each plus the disk, must have the same thickness.";

export const LAYER_FALLBACK_COLORS: Record<string, string> = {
  Graphite: "black",
  "Uranium Dioxide": "green",
};

export const TAB_KEYS = ["overview", "fuel", "designer"] as const;
export type TabKey = (typeof TAB_KEYS)[number];
