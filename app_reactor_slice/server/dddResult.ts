export type DisplacementDamage = {
  dddMeVPerG: number;
  dddCi95Pct: number | null;
  dddYears: number | null;
};

export type IngaasPmax = {
  pmaxRemaining: number;
  pmaxCi95Pct: number | null;
  pmaxYears: number | null;
  pmaxFluenceM2: number;
  pmaxOutsideRange: boolean;
  pmaxFastRemaining: number | null;
  pmaxTruncatedRemaining: number | null;
};

const NUMBER = String.raw`[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?`;
const PMAX_LINE = new RegExp(
  String.raw`InGaAs Pmax remaining:\s*(${NUMBER})\s+of initial\s+over\s+(${NUMBER})\s+years\s+\((?:±|\+/-)\s*(${NUMBER}|nan)%\s*,\s*95%\s*CI\),\s*XPNR-equivalent fluence\s+(${NUMBER})\s+m\^-2(?:\s+\(outside measured range\))?`,
  "i",
);
const PMAX_SENSITIVITY = new RegExp(
  String.raw`InGaAs Pmax sensitivity:\s*fast-fluence\s+(${NUMBER}),\s*truncated spectrum\s+(${NUMBER})`,
  "i",
);
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

function finiteOrNull(raw: unknown): number | null {
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** The tally printer's Wang Pmax line. The CI is already a percent. */
export function parseIngaasPmaxLine(line: string): IngaasPmax | null {
  const match = line.match(PMAX_LINE);
  if (!match) return null;
  const pmaxRemaining = Number(match[1]);
  const pmaxYears = Number(match[2]);
  const pmaxFluenceM2 = Number(match[4]);
  if (![pmaxRemaining, pmaxYears, pmaxFluenceM2].every((value) => Number.isFinite(value))) {
    return null;
  }
  const ci = match[3].toLowerCase() === "nan" ? null : Number(match[3]);
  return {
    pmaxRemaining,
    pmaxYears,
    pmaxFluenceM2,
    pmaxCi95Pct: ci != null && Number.isFinite(ci) ? ci : null,
    pmaxOutsideRange: /\(outside measured range\)/i.test(line),
    pmaxFastRemaining: null,
    pmaxTruncatedRemaining: null,
  };
}

export function parseIngaasPmaxSensitivityLine(
  line: string,
): Pick<IngaasPmax, "pmaxFastRemaining" | "pmaxTruncatedRemaining"> | null {
  const match = line.match(PMAX_SENSITIVITY);
  if (!match) return null;
  const pmaxFastRemaining = Number(match[1]);
  const pmaxTruncatedRemaining = Number(match[2]);
  if (!Number.isFinite(pmaxFastRemaining) || !Number.isFinite(pmaxTruncatedRemaining)) return null;
  return { pmaxFastRemaining, pmaxTruncatedRemaining };
}

/**
 * pmax fields written next to `ddd` in resultsim.json.
 * `pmax_ci95p` is a fraction. `doseYears` is the queue item's dose time.
 */
export function pmaxFromResultsim(
  record: Record<string, unknown>,
  doseYears: number | null,
): IngaasPmax | null {
  if (record.kind === "gamma_dose") return null;
  const raw = Array.isArray(record.pmax_remaining) ? record.pmax_remaining[0] : record.pmax_remaining;
  const pmaxRemaining = Number(raw);
  const fluenceRaw = Array.isArray(record.pmax_fluence_m2)
    ? record.pmax_fluence_m2[0]
    : record.pmax_fluence_m2;
  const pmaxFluenceM2 = Number(fluenceRaw);
  if (!Number.isFinite(pmaxRemaining) || !Number.isFinite(pmaxFluenceM2)) return null;
  const fraction = record.pmax_ci95p == null ? NaN : Number(record.pmax_ci95p);
  const fastRaw = Array.isArray(record.pmax_fast) ? record.pmax_fast[0] : record.pmax_fast;
  const truncRaw = Array.isArray(record.pmax_truncated) ? record.pmax_truncated[0] : record.pmax_truncated;
  return {
    pmaxRemaining,
    pmaxFluenceM2,
    pmaxYears: doseYears != null && Number.isFinite(doseYears) ? doseYears : null,
    pmaxCi95Pct: Number.isFinite(fraction) ? fraction * 100 : null,
    pmaxOutsideRange: record.pmax_outside === true,
    pmaxFastRemaining: finiteOrNull(fastRaw),
    pmaxTruncatedRemaining: finiteOrNull(truncRaw),
  };
}