/**
 * Empirical TPV η(T) and power density from Dada et al. Fig. 8.
 *
 * Values are regenerated from the paper’s model (not hand-traced):
 *   VF=1, ε_abv=1, IQE=1, Tcell=25°C, Rseries=0.01 Ω·cm²,
 *   Woc = radiative-limit(15 mA/cm²) + 70 mV (solid) or + 140 mV (dashed),
 *   ε_bel = 0.05 (95% R) or 0.01 (99% R).
 *
 * Generator: app_reactor_slice/scripts/tpv_dada_model.py → tpvDadaFig8.json
 * Source: Dada et al., Sol. Energy Mater. Sol. Cells 289 (2025) 113666.
 */

import fig8 from "./tpvDadaFig8.json";

export type TpvEgEv = 0.4 | 0.5 | 0.6 | 0.7 | 0.8;
export type TpvBelowGapReflectancePct = 95 | 99;
/** Fig. 8 voltage penalty above the radiative-limit Woc at 15 mA/cm². */
export type TpvWocMv = 70 | 140;
export type TpvPoint = { tempC: number; value: number };

export const TPV_WOC_OPTIONS: ReadonlyArray<{ mv: TpvWocMv; label: string }> = [
  { mv: 70, label: "Woc +70 mV (solid)" },
  { mv: 140, label: "Woc +140 mV (dashed)" },
];

export const TPV_EG_OPTIONS: TpvEgEv[] = [0.4, 0.5, 0.6, 0.7, 0.8];

export const TPV_EG_META: Record<TpvEgEv, { label: string; color: string }> = {
  0.4: { label: "0.4 eV", color: "#2563eb" },
  0.5: { label: "0.5 eV", color: "#ea580c" },
  0.6: { label: "0.6 eV", color: "#16a34a" },
  0.7: { label: "0.7 eV", color: "#dc2626" },
  0.8: { label: "0.8 eV", color: "#7c3aed" },
};

type BandSeries = {
  hi_plus70mV: number[];
  lo_plus140mV: number[];
  mid: number[];
};

const WOC_SERIES: Record<TpvWocMv, keyof BandSeries> = {
  70: "hi_plus70mV",
  140: "lo_plus140mV",
};

function seriesToPoints(temps: number[], values: number[]): TpvPoint[] {
  return temps.map((tempC, i) => ({ tempC, value: values[i] }));
}

function mapEg(record: Record<string, BandSeries>, which: keyof BandSeries): Record<TpvEgEv, TpvPoint[]> {
  const temps = fig8.temps_C as number[];
  const out = {} as Record<TpvEgEv, TpvPoint[]>;
  for (const eg of TPV_EG_OPTIONS) {
    const key = eg.toFixed(1);
    out[eg] = seriesToPoints(temps, record[key][which]);
  }
  return out;
}

/** Fig. 8a/b — η (%) for one below-gap reflectance and one Woc penalty. */
export function efficiencyTable(
  reflectancePct: TpvBelowGapReflectancePct,
  wocMv: TpvWocMv = 70,
): Record<TpvEgEv, TpvPoint[]> {
  const table = reflectancePct === 99 ? fig8.efficiency_R99 : fig8.efficiency_R95;
  return mapEg(table as Record<string, BandSeries>, WOC_SERIES[wocMv]);
}

/** Fig. 8c — electrical power density (W/cm²) for one Woc penalty. Reflectance does not enter. */
export function powerTable(wocMv: TpvWocMv = 70): Record<TpvEgEv, TpvPoint[]> {
  return mapEg(fig8.power_w_cm2 as Record<string, BandSeries>, WOC_SERIES[wocMv]);
}

/** Linear interpolation on a sorted table. Clamps outside the domain. */
export function interpolateTpvValue(points: TpvPoint[], tempC: number): number | null {
  if (!points.length) return null;
  if (tempC <= points[0].tempC) return points[0].value;
  const last = points[points.length - 1];
  if (tempC >= last.tempC) return last.value;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (tempC >= a.tempC && tempC <= b.tempC) {
      const t = (tempC - a.tempC) / (b.tempC - a.tempC);
      return a.value + t * (b.value - a.value);
    }
  }
  return null;
}
