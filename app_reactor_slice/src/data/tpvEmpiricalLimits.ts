/**
 * Air-bridge TPV curves from Roy-Layinde et al., Joule 8, 2135 (2024).
 * The optical integrals are the deposited ddiode_simulation scripts: measured
 * FTIR absorptance times a blackbody, stored at view factor 1. The page
 * multiplies by the selected view factor and solves that script's two-diode
 * equation. Data: doi:10.7302/7qsw-je08. Generator: scripts/tpv_airbridge_model.py.
 */
import table from "./tpvAirbridge.json";

export type TpvPoint = { tempC: number; value: number };

type AirbridgeCell = {
  id: string;
  label: string;
  color: string;
  eg_eV: number;
  j0_A_cm2: number;
  jgr_A_cm2: number;
  rs_ohm_cm2: number;
  rsh_ohm_cm2: number | null;
  script_view_factor: number;
  jsc_A_cm2_vf1: number[];
  qabs_W_cm2_vf1: number[];
};

const TEMPS_C = table.temps_C;
const CELLS = table.cells as AirbridgeCell[];
const THERMAL_VOLTAGE_V = 8.617330350e-5 * table.cell_temperature_K;

export const AIRBRIDGE_CELLS = CELLS.map((cell, index) => ({
  index,
  id: cell.id,
  label: cell.label,
  color: cell.color,
  scriptViewFactor: cell.script_view_factor,
}));

/** Positive current is the generated current, as in the deposited scripts. */
function generatedCurrent(voltage: number, jsc: number, cell: AirbridgeCell): number {
  const rs = cell.rs_ohm_cm2;
  const rsh = cell.rsh_ohm_cm2;
  let current = jsc;
  for (let iteration = 0; iteration < 60; iteration++) {
    const overdrive = voltage + current * rs;
    const exp1 = Math.exp(Math.min(overdrive / THERMAL_VOLTAGE_V, 80));
    const exp2 = Math.exp(Math.min(overdrive / (2 * THERMAL_VOLTAGE_V), 80));
    const shunt = rsh ? overdrive / rsh : 0;
    const shuntSlope = rsh ? rs / rsh : 0;
    const residual =
      current - jsc + cell.j0_A_cm2 * exp1 + cell.jgr_A_cm2 * exp2 + shunt;
    const slope =
      1 +
      cell.j0_A_cm2 * exp1 * (rs / THERMAL_VOLTAGE_V) +
      cell.jgr_A_cm2 * exp2 * (rs / (2 * THERMAL_VOLTAGE_V)) +
      shuntSlope;
    const next = current - residual / slope;
    if (Math.abs(next - current) < 1e-14) return next;
    current = next;
  }
  return current;
}

function maximumPowerDensity(jsc: number, cell: AirbridgeCell): number {
  if (!(jsc > 0)) return 0;
  let best = 0;
  const steps = 400;
  for (let i = 1; i < steps; i++) {
    const voltage = (1.05 * i) / (steps - 1);
    const power = voltage * generatedCurrent(voltage, jsc, cell);
    if (power > best) best = power;
  }
  return best;
}

export function airbridgeCurves(
  cellIndex: number,
  viewFactor: number,
): { efficiency: TpvPoint[]; power: TpvPoint[]; color: string; label: string } {
  const cell = CELLS[Math.min(CELLS.length - 1, Math.max(0, Math.round(cellIndex)))] ?? CELLS[0];
  const vf = Math.min(1, Math.max(0.1, viewFactor));
  const power = cell.jsc_A_cm2_vf1.map((jsc) => maximumPowerDensity(jsc * vf, cell));
  const efficiency = power.map((value, index) => {
    const absorbed = vf * cell.qabs_W_cm2_vf1[index];
    return absorbed > 0 ? (100 * value) / absorbed : 0;
  });
  return {
    color: cell.color,
    label: cell.label,
    efficiency: TEMPS_C.map((tempC, index) => ({ tempC, value: efficiency[index] })),
    power: TEMPS_C.map((tempC, index) => ({ tempC, value: power[index] })),
  };
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
