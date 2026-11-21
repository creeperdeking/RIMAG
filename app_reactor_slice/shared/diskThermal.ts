/** Graphite thermal properties for RIMAEL Modelica lumped masses. */

/** Matches OpenMC Graphite density in common_lib/materials.py (1.82 g/cm³). */
export const GRAPHITE_DENSITY_KG_M3 = 1820;

/**
 * Specific heat of nuclear graphite near ~1000–1250 °C (J/(kg·K)).
 * Room-temperature graphite is ~700; high-T values are ~1600–2000.
 */
export const GRAPHITE_CP_J_KG_K = 1800;

/** Through-thickness conductivity of polycrystalline graphite at elevated T (W/(m·K)). */
export const GRAPHITE_K_W_M_K = 40;

/** Angular sectors in RIMAEL.Disk / TwoFaceDiskSection. */
export const RIMAEL_N_SECTIONS = 12;

export type GraphiteLumpedThermal = {
  heatCapacity: number;
  massKg: number;
  thicknessM: number;
  areaM2: number;
};

export type DiskSectionThermal = {
  heatCapacitySection: number;
  throughThicknessG: number;
  massTotalKg: number;
  thicknessM: number;
  areaM2: number;
  nSections: number;
};

/** C = ρ · A · t · c_p for a single lumped graphite body (e.g. FuelPlate). */
export function graphiteLumpedThermal(areaM2: number, thicknessCm: number): GraphiteLumpedThermal {
  const area = Math.max(areaM2, 0);
  const thicknessM = Math.max(thicknessCm, 0.01) / 100;
  const massKg = GRAPHITE_DENSITY_KG_M3 * area * thicknessM;
  return {
    heatCapacity: massKg * GRAPHITE_CP_J_KG_K,
    massKg,
    thicknessM,
    areaM2: area,
  };
}

/**
 * Lumped heat capacity of one Modelica disk sector:
 * C_section = (ρ · A · t · c_p) / N
 * and through-thickness conductance of that sector:
 * G = k · (A/N) / t
 */
export function diskSectionThermal(
  areaM2: number,
  thicknessCm: number,
  nSections: number = RIMAEL_N_SECTIONS,
): DiskSectionThermal {
  const lumped = graphiteLumpedThermal(areaM2, thicknessCm);
  const n = Math.max(1, Math.round(nSections));
  const throughThicknessG = (GRAPHITE_K_W_M_K * (lumped.areaM2 / n)) / lumped.thicknessM;
  return {
    heatCapacitySection: lumped.heatCapacity / n,
    throughThicknessG,
    massTotalKg: lumped.massKg,
    thicknessM: lumped.thicknessM,
    areaM2: lumped.areaM2,
    nSections: n,
  };
}

export type DiskCircuitArcs = {
  fuelArcFrac: number;
  tpvArcFrac: number;
  shield1ArcFrac: number;
  shield2ArcFrac: number;
};

/**
 * Map app zone angles to Modelica circuit fractions (full circle = 1).
 * Fuel and TPV match Geometry; remaining angle is split equally into shield1/shield2.
 */
export function diskCircuitArcsFromAngles(fuelAngleRad: number, tpvAngleRad: number): DiskCircuitArcs {
  const twoPi = 2 * Math.PI;
  let fuel = Math.max(1e-6, fuelAngleRad / twoPi);
  let tpv = Math.max(1e-6, tpvAngleRad / twoPi);
  if (fuel + tpv >= 1 - 1e-9) {
    const scale = (1 - 2e-6) / (fuel + tpv);
    fuel *= scale;
    tpv *= scale;
  }
  const shieldEach = Math.max(0, (1 - fuel - tpv) / 2);
  return {
    fuelArcFrac: fuel,
    tpvArcFrac: tpv,
    shield1ArcFrac: shieldEach,
    shield2ArcFrac: shieldEach,
  };
}

/**
 * Modelica FuelPlate heating P0 [W] for one disk × one slice pitch
 * (matches FuelPlate.C / disk areas passed into the runner).
 * Same formula as Overview Thermal, without columns × nSlices, in watts:
 * P0 = 1000 × (2 × density × 10 × A_tpv) / (η/100).
 */
export function modelicaFuelHeatingPowerW(
  tpvDensityWPerCm2: number,
  tpvEffPct: number,
  oppositeAreaM2: number,
): number {
  if (!(tpvEffPct > 0) || !(oppositeAreaM2 > 0) || !(tpvDensityWPerCm2 > 0)) return 0;
  const electricalKw = 2 * tpvDensityWPerCm2 * 10 * oppositeAreaM2;
  return (1000 * electricalKw) / (tpvEffPct / 100);
}

/** Matches Modelica coolWaterTemp / TPV cell sink in RIMAEL.Reactor. */
export const TPV_CELL_TEMP_K = 333.15;

/** TPV-side emissivity used when building Gr_tpv in the Modelica runner. */
export const EPS_TPV = 0.85;

/** Two gray surfaces: Gr = A / (1/ε₁ + 1/ε₂ − 1). */
export function radiationFactorM2(areaM2: number, epsA: number, epsB: number): number {
  const area = Math.max(areaM2, 0);
  const ea = Math.min(1, Math.max(0.05, epsA));
  const eb = Math.min(1, Math.max(0.05, epsB));
  const denom = 1 / ea + 1 / eb - 1;
  return area / Math.max(denom, 1e-9);
}

export type AverageDiskTemperature = {
  /** Steady lumped disk temperature (°C) — TPV emitter. */
  diskTempC: number;
  diskTempK: number;
  fuelTempK: number;
  tpvCellTempK: number;
  grFuel: number;
  grTpv: number;
};

/**
 * Steady-state average disk temperature for Fuel → Disk → TPV radiation.
 *
 * Lumped disk energy balance (σ cancels):
 *   Gr_fuel · (T_fuel⁴ − T_disk⁴) = Gr_tpv · (T_disk⁴ − T_tpv⁴)
 * ⇒ T_disk⁴ = (Gr_fuel · T_fuel⁴ + Gr_tpv · T_tpv⁴) / (Gr_fuel + Gr_tpv)
 *
 * Gr_fuel / Gr_tpv use the facing fuel and TPV areas with gray two-surface factors.
 * Thin-disk limit: through-thickness ΔT ≪ radiation drop, so one T_disk.
 */
export function averageDiskTemperatureFromRadiation(options: {
  fuelTempC: number;
  fuelEmissivity: number;
  diskEmissivity: number;
  fuelAreaM2: number;
  tpvAreaM2: number;
  tpvEmissivity?: number;
  tpvCellTempK?: number;
}): AverageDiskTemperature {
  const fuelTempK = options.fuelTempC + 273.15;
  const tpvCellTempK = options.tpvCellTempK ?? TPV_CELL_TEMP_K;
  const tpvEps = options.tpvEmissivity ?? EPS_TPV;
  const grFuel = radiationFactorM2(options.fuelAreaM2, options.fuelEmissivity, options.diskEmissivity);
  const grTpv = radiationFactorM2(options.tpvAreaM2, tpvEps, options.diskEmissivity);
  const sum = grFuel + grTpv;
  let diskTempK: number;
  if (!(sum > 0) || !Number.isFinite(fuelTempK) || fuelTempK <= 0) {
    diskTempK = Math.max(tpvCellTempK, fuelTempK);
  } else {
    const t4 = (grFuel * fuelTempK ** 4 + grTpv * tpvCellTempK ** 4) / sum;
    diskTempK = Math.pow(Math.max(t4, 0), 0.25);
  }
  return {
    diskTempC: diskTempK - 273.15,
    diskTempK,
    fuelTempK,
    tpvCellTempK,
    grFuel,
    grTpv,
  };
}
