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

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

function lerp(a: number, b: number, t: number): number {
  return a + t * (b - a);
}

function bracket(value: number, knots: readonly number[]): { i0: number; i1: number; t: number } {
  if (value <= knots[0]) return { i0: 0, i1: 0, t: 0 };
  const last = knots.length - 1;
  if (value >= knots[last]) return { i0: last, i1: last, t: 0 };
  let i0 = 0;
  while (i0 < last - 1 && knots[i0 + 1] < value) i0 += 1;
  const span = knots[i0 + 1] - knots[i0];
  return { i0, i1: i0 + 1, t: span === 0 ? 0 : (value - knots[i0]) / span };
}

function blendBandGap(table: Record<string, BandSeries>, which: keyof BandSeries, egEv: number): number[] {
  const { i0, i1, t } = bracket(egEv, TPV_EG_OPTIONS);
  const left = table[TPV_EG_OPTIONS[i0].toFixed(1)][which];
  const right = table[TPV_EG_OPTIONS[i1].toFixed(1)][which];
  return left.map((value, index) => lerp(value, right[index], t));
}

function blendWoc(table: Record<string, BandSeries>, egEv: number, wocMv: number): number[] {
  const at70 = blendBandGap(table, "hi_plus70mV", egEv);
  const at140 = blendBandGap(table, "lo_plus140mV", egEv);
  const t = (clamp(wocMv, 70, 140) - 70) / 70;
  return at70.map((value, index) => lerp(value, at140[index], t));
}

/**
 * Efficiency and power density at any band gap, below-gap reflectance, and Woc penalty
 * inside the Fig. 8 ranges. Band gap and Woc are blended between the computed curves.
 * Reflectance changes only the below-gap part of the absorbed heat, so efficiency follows
 * that exactly and power density does not move.
 */
export function empiricalCurves(
  egEv: number,
  reflectancePct: number,
  wocMv: number,
): { efficiency: TpvPoint[]; power: TpvPoint[] } {
  const eg = clamp(egEv, 0.4, 0.8);
  const reflectance = clamp(reflectancePct, 95, 99);
  const emissivity = (100 - reflectance) / 100;
  const temps = fig8.temps_C as number[];
  const power = blendWoc(fig8.power_w_cm2 as Record<string, BandSeries>, eg, wocMv);
  const eta95 = blendWoc(fig8.efficiency_R95 as Record<string, BandSeries>, eg, wocMv);
  const eta99 = blendWoc(fig8.efficiency_R99 as Record<string, BandSeries>, eg, wocMv);
  const efficiency = eta95.map((value95, index) => {
    const value99 = eta99[index];
    const p = power[index];
    if (!(p > 0) || !(value95 > 0) || !(value99 > 0)) {
      return lerp(value95, value99, (reflectance - 95) / 4);
    }
    const absorbed95 = (100 * p) / value95;
    const absorbed99 = (100 * p) / value99;
    const below = (absorbed95 - absorbed99) / (0.05 - 0.01);
    const above = absorbed99 - 0.01 * below;
    const absorbed = above + emissivity * below;
    return absorbed > 0 ? (100 * p) / absorbed : 0;
  });
  return {
    efficiency: temps.map((tempC, index) => ({ tempC, value: efficiency[index] })),
    power: temps.map((tempC, index) => ({ tempC, value: power[index] })),
  };
}

function hexChannel(hex: string): [number, number, number] {
  const n = Number.parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Color blended between the neighboring Fig. 8 band-gap colors. */
export function bandGapColor(egEv: number): string {
  const { i0, i1, t } = bracket(clamp(egEv, 0.4, 0.8), TPV_EG_OPTIONS);
  const left = hexChannel(TPV_EG_META[TPV_EG_OPTIONS[i0]].color);
  const right = hexChannel(TPV_EG_META[TPV_EG_OPTIONS[i1]].color);
  const mixed = left.map((channel, index) => Math.round(lerp(channel, right[index], t)));
  return `#${mixed.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
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
