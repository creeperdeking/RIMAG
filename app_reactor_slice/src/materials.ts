import catalog from "./data/materials.json";
import type { MaterialSpec, MixedSpec } from "./geometry";

export type MaterialFact = {
  color: string;
  composition: string;
  density: number | null;
};

type Catalog = {
  specs: Record<string, MaterialSpec>;
  mixed: Record<string, MixedSpec>;
};

const BASE = catalog as Catalog;

/** Enrichment baked into `materials.json` when it was exported from common_lib. */
const DUMP_ENRICHMENT_PCT = 5;

function cloneSpecs(specs: Record<string, MaterialSpec>): Record<string, MaterialSpec> {
  return JSON.parse(JSON.stringify(specs)) as Record<string, MaterialSpec>;
}

/** Patch slider-driven enrichment; leave fixed values such as depleted U alone. */
export function materialLibrary(enrichmentPct: number): {
  specs: Record<string, MaterialSpec>;
  mixed: Record<string, MixedSpec>;
} {
  const specs = cloneSpecs(BASE.specs);
  for (const spec of Object.values(specs)) {
    for (const part of spec.composition) {
      if (part.atom === "U" && part.enrichment != null && Math.abs(part.enrichment - DUMP_ENRICHMENT_PCT) < 1e-9) {
        part.enrichment = enrichmentPct;
      }
    }
  }
  return { specs, mixed: BASE.mixed };
}

function libraryEntry(
  name: string,
  specs: Record<string, MaterialSpec>,
  mixed: Record<string, MixedSpec>,
): [MaterialSpec | null, MixedSpec | null] {
  if (name in specs) return [specs[name], null];
  const idx = name.lastIndexOf(" ");
  if (idx > 0) {
    const base = name.slice(0, idx);
    const suffix = name.slice(idx + 1);
    if (/^\d+$/.test(suffix) && base in specs) return [specs[base], null];
  }
  let mix = mixed[name] ?? null;
  if (!mix && idx > 0) {
    const base = name.slice(0, idx);
    const suffix = name.slice(idx + 1);
    if (/^\d+$/.test(suffix)) mix = mixed[base] ?? null;
  }
  return [null, mix];
}

function compositionText(spec: MaterialSpec): string {
  return spec.composition
    .map((part) => {
      const proportion = part.proportion;
      const amount = proportion == null || proportion === 1 ? "" : ` ${Number(proportion.toPrecision(4))}`;
      const enrichment = part.enrichment != null ? ` (${Number(part.enrichment.toPrecision(4))}% enriched)` : "";
      return `${part.atom}${amount}${enrichment}`;
    })
    .join(", ");
}

/**
 * Editor titles and the disk alias, in the same sense as app_slice_design.materials_map.
 * The color then comes from that catalog entry in materials.py (via materials.json).
 */
const ROLE_CATALOG_NAMES: Record<string, string> = {
  Disk: "Graphite",
  disk: "Graphite",
  "Disk layer": "Graphite",
  "Fuel layer": "Uranium Dioxide",
  "Reflector layer": "Graphite",
  "Shield absorber": "Boron Carbide",
  "TPV layer": "InGaAs",
};

export function isGraphiteLike(name: string, shieldModerator = "Graphite"): boolean {
  const catalog = catalogNameForLayer(name, shieldModerator);
  const [spec, mix] = libraryEntry(catalog, BASE.specs, BASE.mixed);
  return Boolean(spec?.graphite_like || mix?.graphite_like);
}

export function catalogNameForLayer(name: string, shieldModerator = "Graphite"): string {
  const trimmed = String(name ?? "").trim();
  const shield = typeof shieldModerator === "string" ? shieldModerator.trim() : "";
  if (trimmed === "Shield moderator") return shield || "Graphite";
  return ROLE_CATALOG_NAMES[trimmed] ?? trimmed;
}

function factFromEntry(spec: MaterialSpec | null, mix: MixedSpec | null, specs: Record<string, MaterialSpec>): MaterialFact | null {
  if (spec) {
    return {
      color: spec.color || "orange",
      composition: compositionText(spec),
      density: spec.density,
    };
  }
  if (!mix) return null;
  const weights = mix.proportions.filter((w) => w > 0);
  if (!weights.length) return null;
  let volume = 0;
  const described: string[] = [];
  let color = "orange";
  for (let i = 0; i < mix.materials.length; i += 1) {
    const component = mix.materials[i];
    const proportion = mix.proportions[i];
    const componentSpec = specs[component];
    if (!componentSpec || proportion <= 0) return null;
    if (component === mix.materials[0] && componentSpec.color) color = componentSpec.color;
    volume += proportion / componentSpec.density;
    described.push(`${Number(proportion.toPrecision(4))} ${component}`);
  }
  const total = mix.proportions.reduce((sum, value) => sum + value, 0);
  return {
    color,
    composition: described.join(" + "),
    density: volume ? total / volume : null,
  };
}

export function materialFact(
  name: string,
  specs: Record<string, MaterialSpec>,
  mixed: Record<string, MixedSpec>,
  shieldModerator = "Graphite",
): MaterialFact | null {
  const trimmed = name.trim();
  const direct = factFromEntry(...libraryEntry(trimmed, specs, mixed), specs);
  if (direct) return direct;
  const aliased = catalogNameForLayer(trimmed, shieldModerator);
  if (aliased === trimmed) return null;
  return factFromEntry(...libraryEntry(aliased, specs, mixed), specs);
}

export function materialLines(
  rows: Array<{ name: string }>,
  specs: Record<string, MaterialSpec>,
  mixed: Record<string, MixedSpec>,
  shieldModerator = "Graphite",
): string[] {
  const lines: string[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const name = String(row.name ?? "").trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const fact = materialFact(name, specs, mixed, shieldModerator);
    if (!fact || !fact.composition) continue;
    const densityText = fact.density != null ? ` · ${Number(fact.density.toPrecision(4))} g/cm³` : "";
    lines.push(`${name}: ${fact.composition}${densityText}`);
  }
  return lines;
}

export function materialNames(specs: Record<string, MaterialSpec>, mixed: Record<string, MixedSpec>): string[] {
  return [...Object.keys(specs), ...Object.keys(mixed), "Disk", "Void"].sort((a, b) =>
    a.localeCompare(b, undefined, { sensitivity: "base" }),
  );
}
