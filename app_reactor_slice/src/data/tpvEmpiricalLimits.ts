/**
 * Empirical TPV η(T) and power density from Dada et al. Fig. 8.
 *
 * The published curves use VF=1, ε_abv=1, IQE=1, Tcell=25°C, Rseries=0.01 Ω·cm²,
 * Woc = radiative-limit(15 mA/cm²) + 70 mV (solid) or + 140 mV (dashed),
 * ε_bel = 0.05 (95% R) or 0.01 (99% R).
 *
 * The chart solver uses a two-diode equation. The n = 1 diode follows the selected Woc
 * penalty, and the n = 2 diode is an extra recombination current. Series resistance and
 * view factor are selected too. Blackbody current and heat in tpvDadaSpectrum.json are
 * for a view factor of 1; the solver scales both by the selected view factor.
 * tpvDadaFig8.json keeps the published single-diode curves (J02 = 0, Rs = 0.01, VF = 1).
 *
 * Roy-Layinde et al., Joule 8, 2135 (2024), Table S4.1, for the 0.74 eV air-bridge cell
 * at 25°C: J01 = 1.47e-9 A/cm² (about Woc +76 mV), J02 = 1.97e-6 A/cm², Rs = 0.030 Ω·cm².
 * With n = 1 and n = 2 that pair reproduces their measured power to about 5%.
 *
 * Generator: app_reactor_slice/scripts/tpv_dada_model.py
 * Source: Dada et al., Sol. Energy Mater. Sol. Cells 289 (2025) 113666.
 */

import fig8 from "./tpvDadaFig8.json";
import spectrum from "./tpvDadaSpectrum.json";

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

const TCELL_C = 25;
const THERMAL_VOLTAGE_V = (1.380649e-23 * (TCELL_C + 273.15)) / 1.602176634e-19;
/** Current at which the Woc penalty is defined, matching Fig. 8. */
const WOC_REFERENCE_A_CM2 = 0.015;

function j0FromWoc(egEv: number, wocV: number): number {
  const voc = egEv - wocV;
  const denom = Math.exp(voc / THERMAL_VOLTAGE_V) - 1;
  if (!(denom > 0)) return Number.POSITIVE_INFINITY;
  return WOC_REFERENCE_A_CM2 / denom;
}

/**
 * Maximum power density of the two-diode cell
 * J = −Jsc + J01 (exp(q(V − J Rs)/kT) − 1) + J02 (exp(q(V − J Rs)/(2kT)) − 1).
 * Currents are in A/cm², Rs in Ω·cm², and the result is in W/cm².
 * J02 = 0 is the Fig. 8 single diode. The n = 1 open-circuit voltage is above the
 * real one once J02 is present, so the voltage scan still covers the maximum.
 */
function maximumPowerDensity(jsc: number, j01: number, rseriesOhmCm2: number, j02 = 0): number {
  if (!(jsc > 0) || !(j01 > 0) || !Number.isFinite(j01)) return 0;
  const rs = Math.max(0, rseriesOhmCm2);
  const recombination = Math.max(0, j02);
  const vt = THERMAL_VOLTAGE_V;
  const voc = vt * Math.log(jsc / j01 + 1);
  const steps = 200;
  let best = 0;
  for (let i = 1; i < steps; i++) {
    const voltage = (voc * 1.05 * i) / (steps - 1);
    let current = -jsc;
    for (let iteration = 0; iteration < 40; iteration++) {
      const overdrive = voltage - current * rs;
      const arg1 = Math.min(overdrive / vt, 80);
      const arg2 = Math.min(overdrive / (2 * vt), 80);
      const exp1 = Math.exp(arg1);
      const exp2 = recombination > 0 ? Math.exp(arg2) : 0;
      const residual = current + jsc - j01 * (exp1 - 1) - recombination * (exp2 - 1);
      const slope = 1 + j01 * exp1 * (rs / vt) + recombination * exp2 * (rs / (2 * vt));
      const next = current - residual / slope;
      if (Math.abs(next - current) < 1e-12) {
        current = next;
        break;
      }
      current = next;
    }
    const power = -current * voltage;
    if (power > best) best = power;
  }
  return best;
}

function spectrumRow(egEv: number): { wocRadV: number; jsc: number[]; qAbove: number[]; qBelow: number[] } {
  const gaps = spectrum.eg_eV;
  const { i0, i1, t } = bracket(egEv, gaps);
  const mix = (rows: number[][]) => rows[i0].map((value, index) => lerp(value, rows[i1][index], t));
  return {
    wocRadV: lerp(spectrum.woc_rad_V[i0], spectrum.woc_rad_V[i1], t),
    jsc: mix(spectrum.jsc_A_cm2),
    qAbove: mix(spectrum.q_above_W_cm2),
    qBelow: mix(spectrum.q_below_W_cm2),
  };
}

/**
 * Efficiency and power density from the two-diode model.
 * Band gap, Woc penalty, series resistance, view factor, and the n = 2 saturation
 * current are solved directly. View factor scales the incident photon flux, so both
 * current and absorbed heat scale with it. Reflectance changes only the below-gap
 * part of the absorbed heat, so at a fixed view factor it moves efficiency and not power.
 */
export function empiricalCurves(
  egEv: number,
  reflectancePct: number,
  wocMv: number,
  rseriesOhmCm2 = 0.01,
  viewFactor = 1,
  j02APerCm2 = 0,
): { efficiency: TpvPoint[]; power: TpvPoint[] } {
  const eg = clamp(egEv, 0.4, 0.8);
  const reflectance = clamp(reflectancePct, 95, 99);
  const emissivity = (100 - reflectance) / 100;
  const wocExtraV = clamp(wocMv, 70, 140) / 1000;
  const vf = clamp(viewFactor, 0.1, 1);
  const j02 = Math.max(0, j02APerCm2);
  const row = spectrumRow(eg);
  const j0 = j0FromWoc(eg, row.wocRadV + wocExtraV);
  const temps = spectrum.temps_C;
  const power = row.jsc.map((jsc) => maximumPowerDensity(jsc * vf, j0, rseriesOhmCm2, j02));
  const efficiency = power.map((value, index) => {
    const absorbed = vf * (row.qAbove[index] + emissivity * row.qBelow[index]);
    return absorbed > 0 ? (100 * value) / absorbed : 0;
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
