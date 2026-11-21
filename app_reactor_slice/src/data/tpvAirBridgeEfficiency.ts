/**
 * Air-bridge InGaAs TPV efficiency vs emitter temperature.
 *
 * Source: Roy-Layinde et al., “High-efficiency air-bridge thermophotovoltaic cells,”
 * Joule 8, 2135–2145 (2024), Fig. 4A model curves (dashed), hand-digitized.
 *
 * Peaks anchored to the paper text:
 *   0.74 eV → 36.0% @ 1480 °C
 *   0.90 eV → 43.8% @ 1435 °C
 *   1.1  eV → 36.1% @ 1630 °C
 *
 * Fig. 4A was measured at F_v ≈ 0.33–0.38. η = Pmpp/Pabs, so these curves are
 * the right shape for design use; at F_v = 1 the paper only quotes two 0.9 eV
 * model points (40% @ 1250 °C, 38% @ 1400 °C) due to series-resistance losses.
 */

export type TpvBandGapEv = 0.74 | 0.9 | 1.1;

export type TpvEffPoint = { tempC: number; effPct: number };

/** Fig. 4A dashed model curves (hand-digitized). */
export const TPV_AIR_BRIDGE_FIG4A_MODEL: Record<TpvBandGapEv, TpvEffPoint[]> = {
  0.74: [
    { tempC: 900, effPct: 27.5 },
    { tempC: 950, effPct: 29.0 },
    { tempC: 1000, effPct: 30.5 },
    { tempC: 1050, effPct: 31.5 },
    { tempC: 1100, effPct: 32.5 },
    { tempC: 1150, effPct: 33.2 },
    { tempC: 1200, effPct: 34.0 },
    { tempC: 1250, effPct: 34.6 },
    { tempC: 1300, effPct: 35.1 },
    { tempC: 1350, effPct: 35.5 },
    { tempC: 1400, effPct: 35.8 },
    { tempC: 1450, effPct: 35.95 },
    { tempC: 1480, effPct: 36.0 },
    { tempC: 1500, effPct: 35.9 },
    { tempC: 1550, effPct: 35.4 },
    { tempC: 1600, effPct: 34.7 },
  ],
  0.9: [
    { tempC: 920, effPct: 29.0 },
    { tempC: 950, effPct: 31.0 },
    { tempC: 1000, effPct: 34.0 },
    { tempC: 1050, effPct: 37.0 },
    { tempC: 1100, effPct: 39.2 },
    { tempC: 1150, effPct: 41.0 },
    { tempC: 1200, effPct: 42.3 },
    { tempC: 1250, effPct: 43.1 },
    { tempC: 1300, effPct: 43.6 },
    { tempC: 1350, effPct: 43.85 },
    { tempC: 1400, effPct: 43.9 },
    { tempC: 1435, effPct: 43.8 },
    { tempC: 1500, effPct: 43.4 },
    { tempC: 1550, effPct: 42.7 },
    { tempC: 1600, effPct: 41.8 },
  ],
  1.1: [
    { tempC: 900, effPct: 7.0 },
    { tempC: 950, effPct: 9.5 },
    { tempC: 1000, effPct: 12.5 },
    { tempC: 1050, effPct: 15.5 },
    { tempC: 1100, effPct: 18.5 },
    { tempC: 1150, effPct: 21.5 },
    { tempC: 1200, effPct: 24.2 },
    { tempC: 1250, effPct: 26.5 },
    { tempC: 1300, effPct: 28.6 },
    { tempC: 1350, effPct: 30.5 },
    { tempC: 1400, effPct: 32.1 },
    { tempC: 1450, effPct: 33.5 },
    { tempC: 1500, effPct: 34.5 },
    { tempC: 1550, effPct: 35.4 },
    { tempC: 1600, effPct: 36.0 },
  ],
};

/** Approximate experimental markers from Fig. 4A (for visual match). */
export const TPV_AIR_BRIDGE_FIG4A_DATA: Record<TpvBandGapEv, TpvEffPoint[]> = {
  0.74: [
    { tempC: 900, effPct: 27.2 },
    { tempC: 1000, effPct: 30.0 },
    { tempC: 1100, effPct: 32.2 },
    { tempC: 1200, effPct: 34.0 },
    { tempC: 1300, effPct: 35.0 },
    { tempC: 1400, effPct: 35.7 },
    { tempC: 1480, effPct: 36.0 },
    { tempC: 1550, effPct: 35.5 },
    { tempC: 1600, effPct: 34.8 },
  ],
  0.9: [
    { tempC: 950, effPct: 30.5 },
    { tempC: 1050, effPct: 36.5 },
    { tempC: 1150, effPct: 40.5 },
    { tempC: 1250, effPct: 42.8 },
    { tempC: 1350, effPct: 43.7 },
    { tempC: 1435, effPct: 43.8 },
    { tempC: 1500, effPct: 43.5 },
    { tempC: 1550, effPct: 42.8 },
  ],
  1.1: [
    { tempC: 900, effPct: 7.0 },
    { tempC: 1000, effPct: 12.0 },
    { tempC: 1100, effPct: 18.0 },
    { tempC: 1200, effPct: 24.0 },
    { tempC: 1300, effPct: 28.5 },
    { tempC: 1400, effPct: 32.0 },
    { tempC: 1500, effPct: 34.5 },
    { tempC: 1550, effPct: 35.5 },
    { tempC: 1600, effPct: 35.8 },
  ],
};

/** SOA gray band from Fig. 4A (lower / upper edge). */
export const TPV_SOA_BAND: { tempC: number; lo: number; hi: number }[] = [
  { tempC: 900, lo: 30.5, hi: 33.5 },
  { tempC: 1000, lo: 31.0, hi: 34.0 },
  { tempC: 1100, lo: 31.5, hi: 34.5 },
  { tempC: 1200, lo: 32.0, hi: 35.0 },
  { tempC: 1300, lo: 32.5, hi: 35.5 },
  { tempC: 1400, lo: 33.0, hi: 36.0 },
  { tempC: 1500, lo: 33.5, hi: 36.5 },
  { tempC: 1600, lo: 34.0, hi: 37.0 },
];

/** @deprecated alias — same as FIG4A_MODEL */
export const TPV_AIR_BRIDGE_MODEL_FV035 = TPV_AIR_BRIDGE_FIG4A_MODEL;

/**
 * Sparse F_v = 1 anchors from the paper main text (0.9 eV only).
 * Not a full curve — do not use these to reshape Fig. 4A.
 */
export const TPV_FV1_ANCHORS_09EV: TpvEffPoint[] = [
  { tempC: 1250, effPct: 40.0 },
  { tempC: 1400, effPct: 38.0 },
];

export const TPV_BANDGAP_META: Record<
  TpvBandGapEv,
  { label: string; color: string; marker: "circle" | "square" | "diamond" }
> = {
  0.74: { label: "0.74 eV", color: "#7c3aed", marker: "square" },
  0.9: { label: "0.90 eV", color: "#ea580c", marker: "circle" },
  1.1: { label: "1.1 eV", color: "#16a34a", marker: "diamond" },
};

/** Linear interpolation on a sorted η(T) table. */
export function interpolateTpvEfficiencyPct(points: TpvEffPoint[], tempC: number): number | null {
  if (!points.length) return null;
  if (tempC <= points[0].tempC) return points[0].effPct;
  const last = points[points.length - 1];
  if (tempC >= last.tempC) return last.effPct;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (tempC >= a.tempC && tempC <= b.tempC) {
      const t = (tempC - a.tempC) / (b.tempC - a.tempC);
      return a.effPct + t * (b.effPct - a.effPct);
    }
  }
  return null;
}
