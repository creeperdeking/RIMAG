export type DisplacementDamage = {
  dddMeVPerG: number;
  dddCi95Pct: number | null;
  dddYears: number | null;
};

const NUMBER = String.raw`[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?`;
const LINE = new RegExp(
  String.raw`Displacement damage:\s*(${NUMBER})\s*MeV/g\s+over\s+(${NUMBER})\s+years\s+\((?:±|\+/-)\s*(${NUMBER}|nan)%\s*,\s*95%\s*CI\)`,
  "i",
);

/** The tally printer's "Displacement damage" line. The CI is already a percent. */
export function parseDisplacementDamageLine(line: string): DisplacementDamage | null {
  const match = line.match(LINE);
  if (!match) return null;
  const dddMeVPerG = Number(match[1]);
  const dddYears = Number(match[2]);
  if (!Number.isFinite(dddMeVPerG) || !Number.isFinite(dddYears)) return null;
  const ci = match[3].toLowerCase() === "nan" ? null : Number(match[3]);
  return {
    dddMeVPerG,
    dddYears,
    dddCi95Pct: ci != null && Number.isFinite(ci) ? ci : null,
  };
}

/**
 * resultsim.json written by the neutron DDD tally.
 * `ddd_ci95p` is a fraction, matching the gamma file. `doseYears` is the
 * queue item's dose time, because the file does not store it.
 */
export function displacementDamageFromResultsim(
  record: Record<string, unknown>,
  doseYears: number | null,
): DisplacementDamage | null {
  if (record.kind === "gamma_dose") return null;
  const raw = Array.isArray(record.ddd) ? record.ddd[0] : record.ddd;
  const dddMeVPerG = Number(raw);
  if (!Number.isFinite(dddMeVPerG)) return null;
  const fraction = record.ddd_ci95p == null ? NaN : Number(record.ddd_ci95p);
  return {
    dddMeVPerG,
    dddYears: doseYears != null && Number.isFinite(doseYears) ? doseYears : null,
    dddCi95Pct: Number.isFinite(fraction) ? fraction * 100 : null,
  };
}
