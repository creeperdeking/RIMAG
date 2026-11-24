/**
 * Air-bridge TPV curves from Roy-Layinde et al., Joule 8, 2135 (2024).
 * The optical integrals are the deposited ddiode_simulation scripts: measured
 * FTIR absorptance times a blackbody, stored at view factor 1. The page
 * multiplies by the selected view factor and solves that script's two-diode
 * equation. Data: doi:10.7302/7qsw-je08. Generator: scripts/tpv_airbridge_model.py.
 */
import { cellReflectanceForHeat, heatFromFuelToShell } from "../../shared/diskThermal";
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
): { efficiency: TpvPoint[]; power: TpvPoint[]; absorbed: TpvPoint[]; color: string; label: string } {
  const cell = CELLS[Math.min(CELLS.length - 1, Math.max(0, Math.round(cellIndex)))] ?? CELLS[0];
  const vf = Math.min(1, Math.max(0.1, viewFactor));
  const power = cell.jsc_A_cm2_vf1.map((jsc) => maximumPowerDensity(jsc * vf, cell));
  const absorbed = cell.qabs_W_cm2_vf1.map((value) => vf * value);
  const efficiency = power.map((value, index) => {
    const heat = absorbed[index];
    return heat > 0 ? (100 * value) / heat : 0;
  });
  return {
    color: cell.color,
    label: cell.label,
    efficiency: TEMPS_C.map((tempC, index) => ({ tempC, value: efficiency[index] })),
    power: TEMPS_C.map((tempC, index) => ({ tempC, value: power[index] })),
    absorbed: TEMPS_C.map((tempC, index) => ({ tempC, value: absorbed[index] })),
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

const CHART_MIN_C = TEMPS_C[0] ?? 600;
const CHART_MAX_C = TEMPS_C[TEMPS_C.length - 1] ?? 1600;

export type AirbridgeOperatingPoint = {
  shellTempC: number;
  diskTempC: number;
  /** Electrical power density of one cell face [W/cm²]. */
  powerWPerCm2: number;
  efficiencyPct: number;
  /** Heat the cell absorbs, one face [W/cm²]. */
  absorbedWPerCm2: number;
  /** Absorbed heat of one column over one pitch, both faces [W]. */
  heatW: number;
  /** Null when the shell cannot emit the absorbed heat at any reflectance in [0, 1). */
  cellReflectance: number | null;
  cellEmissivity: number | null;
  conductionShareFuel: number;
  conductionShareDisk: number;
  /** The helium-gap heat meets the chart absorption at the shell temperature. */
  balanced: boolean;
};

/**
 * Fuel temperature is fixed. The shell temperature is where the heat the helium
 * gaps can carry equals the heat the selected cell absorbs. Power, efficiency,
 * and the gray cell reflectance are that operating point.
 */
export function airbridgeOperatingPoint(options: {
  fuelTempC: number;
  fuelEmissivity: number;
  diskEmissivity: number;
  shellEmissivity: number;
  fuelAreaM2: number;
  tpvAreaM2: number;
  fuelGapCm: number;
  tpvGapCm: number;
  cellIndex: number;
  viewFactor: number;
}): AirbridgeOperatingPoint {
  const curves = airbridgeCurves(options.cellIndex, options.viewFactor);
  const bothFacesM2 = 2 * Math.max(0, options.tpvAreaM2);
  const at = (shellTempC: number) => ({
    power: interpolateTpvValue(curves.power, shellTempC) ?? 0,
    efficiency: interpolateTpvValue(curves.efficiency, shellTempC) ?? 0,
    absorbed: interpolateTpvValue(curves.absorbed, shellTempC) ?? 0,
  });
  const stackFlux = (shellTempC: number) => {
    if (!(bothFacesM2 > 0)) return 0;
    const flow = heatFromFuelToShell({ ...options, shellTempC });
    return flow.heatW / (bothFacesM2 * 1e4);
  };

  let lo = CHART_MIN_C;
  let hi = Math.min(CHART_MAX_C, options.fuelTempC - 0.05);
  let balanced = hi > lo && stackFlux(lo) > at(lo).absorbed && stackFlux(hi) < at(hi).absorbed;
  if (!(hi > lo)) {
    lo = Math.min(options.fuelTempC, CHART_MAX_C);
    hi = lo;
    balanced = false;
  } else if (balanced) {
    for (let i = 0; i < 50; i += 1) {
      const mid = 0.5 * (lo + hi);
      if (stackFlux(mid) > at(mid).absorbed) lo = mid;
      else hi = mid;
    }
  } else if (stackFlux(lo) <= at(lo).absorbed) {
    hi = lo;
  } else {
    lo = hi;
  }

  const shellTempC = 0.5 * (lo + hi);
  const flow = heatFromFuelToShell({ ...options, shellTempC });
  const chart = at(shellTempC);
  const heatW = chart.absorbed * bothFacesM2 * 1e4;
  const gray = cellReflectanceForHeat({
    heatW,
    shellTempK: shellTempC + 273.15,
    shellEmissivity: options.shellEmissivity,
    tpvAreaM2: options.tpvAreaM2,
  });
  return {
    shellTempC,
    diskTempC: flow.diskTempC,
    powerWPerCm2: chart.power,
    efficiencyPct: chart.efficiency,
    absorbedWPerCm2: chart.absorbed,
    heatW,
    cellReflectance: gray?.reflectance ?? null,
    cellEmissivity: gray?.emissivity ?? null,
    conductionShareFuel: flow.conductionShareFuel,
    conductionShareDisk: flow.conductionShareDisk,
    balanced,
  };
}
