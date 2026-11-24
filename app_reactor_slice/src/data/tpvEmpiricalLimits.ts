/**
 * Air-bridge TPV curves from Roy-Layinde et al., Joule 8, 2135 (2024).
 * The optical integrals are the deposited ddiode_simulation scripts. A black
 * shell is the measured FTIR absorptance times a blackbody. A gray shell uses
 * the closed-gap exchange: reflected light returns, so
 *   A ε / (ε + A (1 − ε))
 * replaces A. The reactor gap is closed, so the view factor is 1 and is not
 * scaled. The page solves the script's two-diode equation.
 * Data: doi:10.7302/7qsw-je08. Generator: scripts/tpv_airbridge_model.py.
 */
import { heatFromFuelToShell } from "../../shared/diskThermal";
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
  energy_eV: number[];
  absorptance: number[];
};

const TEMPS_C = table.temps_C;
const CELLS = table.cells as AirbridgeCell[];
const THERMAL_VOLTAGE_V = 8.617330350e-5 * table.cell_temperature_K;
const IQE = table.iqe;

/** Closed-gap weight. A black shell returns the FTIR absorptance. */
function cavityWeight(absorptance: number, emissivity: number): number {
  const a = Math.min(1, Math.max(0, absorptance));
  const eps = Math.min(1, Math.max(0, emissivity));
  if (eps >= 1) return a;
  const denom = eps + a * (1 - eps);
  return denom > 0 ? (a * eps) / denom : 0;
}

function photonFlux(energyEV: number, tempK: number): number {
  const x = energyEV / (table.kB_eV_K * tempK);
  if (x > 700) return 0;
  const denom = table.c_cm_s ** 2 * table.h_eV_s ** 3 * Math.expm1(x);
  return (2 * Math.PI * energyEV * energyEV) / denom;
}

const fluxByCell = new WeakMap<AirbridgeCell, Map<number, Float64Array>>();

function blackbodyFlux(cell: AirbridgeCell, tempC: number): Float64Array {
  let byTemp = fluxByCell.get(cell);
  if (!byTemp) {
    byTemp = new Map();
    fluxByCell.set(cell, byTemp);
  }
  const cached = byTemp.get(tempC);
  if (cached) return cached;
  const tempK = tempC + 273.15;
  const flux = new Float64Array(cell.energy_eV.length);
  for (let i = 0; i < flux.length; i += 1) flux[i] = photonFlux(cell.energy_eV[i], tempK);
  byTemp.set(tempC, flux);
  return flux;
}

/** Current and absorbed heat at view factor 1. */
function opticsAt(cell: AirbridgeCell, tempC: number, emissivity: number): { jsc: number; qabs: number } {
  const energy = cell.energy_eV;
  const absorptance = cell.absorptance;
  const flux = blackbodyFlux(cell, tempC);
  let photon = 0;
  let heat = 0;
  let prevE = energy[0];
  let prevFlux = flux[0];
  let prevWeight = cavityWeight(absorptance[0], emissivity);
  let prevAbove = prevE >= cell.eg_eV;
  for (let i = 1; i < energy.length; i += 1) {
    const e = energy[i];
    const nextFlux = flux[i];
    const weight = cavityWeight(absorptance[i], emissivity);
    const span = e - prevE;
    heat += 0.5 * (prevFlux * prevE * prevWeight + nextFlux * e * weight) * span;
    if (prevAbove && e >= cell.eg_eV) {
      photon += 0.5 * (prevFlux * prevWeight + nextFlux * weight) * span;
    }
    prevE = e;
    prevFlux = nextFlux;
    prevWeight = weight;
    prevAbove = e >= cell.eg_eV;
  }
  return { jsc: table.q_C * photon * IQE, qabs: table.q_C * heat };
}

export const AIRBRIDGE_CELLS = CELLS.map((cell, index) => ({
  index,
  id: cell.id,
  label: cell.label,
  color: cell.color,
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

type AirbridgeCurveSet = {
  efficiency: TpvPoint[];
  power: TpvPoint[];
  absorbed: TpvPoint[];
  color: string;
  label: string;
};

const curveCache = new Map<string, AirbridgeCurveSet>();

function cellAt(cellIndex: number): AirbridgeCell {
  return CELLS[Math.min(CELLS.length - 1, Math.max(0, Math.round(cellIndex)))] ?? CELLS[0];
}

/** Absorbed heat flux of one cell face at this shell temperature [W/cm²]. */
export function absorbedFluxWPerCm2(cellIndex: number, shellEmissivity: number, tempC: number): number {
  const eps = Math.min(1, Math.max(0, shellEmissivity));
  const temp = Number.isFinite(tempC) ? tempC : 0;
  return Math.max(0, opticsAt(cellAt(cellIndex), temp, eps).qabs);
}

export function airbridgeCurves(cellIndex: number, shellEmissivity = 1): AirbridgeCurveSet {
  const cell = cellAt(cellIndex);
  const eps = Math.min(1, Math.max(0, shellEmissivity));
  const cacheKey = `${cell.id}|${eps}`;
  const cached = curveCache.get(cacheKey);
  if (cached) return cached;
  const optics = TEMPS_C.map((tempC) => opticsAt(cell, tempC, eps));
  const power = optics.map((row) => maximumPowerDensity(row.jsc, cell));
  const absorbed = optics.map((row) => row.qabs);
  const efficiency = power.map((value, index) => {
    const heat = absorbed[index];
    return heat > 0 ? (100 * value) / heat : 0;
  });
  const curves = {
    color: cell.color,
    label: cell.label,
    efficiency: TEMPS_C.map((tempC, index) => ({ tempC, value: efficiency[index] })),
    power: TEMPS_C.map((tempC, index) => ({ tempC, value: power[index] })),
    absorbed: TEMPS_C.map((tempC, index) => ({ tempC, value: absorbed[index] })),
  };
  curveCache.set(cacheKey, curves);
  return curves;
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
  conductionShareFuel: number;
  conductionShareDisk: number;
  /** The helium-gap heat meets the chart absorption at the shell temperature. */
  balanced: boolean;
};

/**
 * Fuel temperature is fixed. The shell temperature is where the heat the helium
 * gaps can carry equals the heat the selected cell absorbs from the gray shell.
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
}): AirbridgeOperatingPoint {
  const curves = airbridgeCurves(options.cellIndex, options.shellEmissivity);
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
  return {
    shellTempC,
    diskTempC: flow.diskTempC,
    powerWPerCm2: chart.power,
    efficiencyPct: chart.efficiency,
    absorbedWPerCm2: chart.absorbed,
    heatW,
    conductionShareFuel: flow.conductionShareFuel,
    conductionShareDisk: flow.conductionShareDisk,
    balanced,
  };
}
