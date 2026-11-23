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

/** Stefan–Boltzmann constant [W/(m²·K⁴)]. */
export const SIGMA_W_M2_K4 = 5.670374419e-8;

/** Broadband reflectance of the opaque TPV cells. Default 88% → ε = 0.12. */
export const DEFAULT_CELL_REFLECTANCE = 0.88;

/**
 * Opaque gray surface: absorptivity = emissivity = 1 − reflectance.
 * Reflectance is clamped so emissivity stays in (0.01, 1].
 */
export function emissivityFromReflectance(reflectance: number): number {
  if (!Number.isFinite(reflectance)) return 1 - DEFAULT_CELL_REFLECTANCE;
  const r = Math.min(0.99, Math.max(0, reflectance));
  return 1 - r;
}

/** Two gray surfaces: Gr = A / (1/ε₁ + 1/ε₂ − 1) [m²]. */
export function radiationFactorM2(
  areaM2: number,
  epsA: number,
  epsB: number,
  minEps = 0.01,
): number {
  const area = Math.max(areaM2, 0);
  const floor = Math.min(0.5, Math.max(0.01, minEps));
  const ea = Math.min(1, Math.max(floor, epsA));
  const eb = Math.min(1, Math.max(floor, epsB));
  const denom = 1 / ea + 1 / eb - 1;
  return area / Math.max(denom, 1e-9);
}

export type LayerDiskRadiation = {
  /** Heat generated in one column over one axial pitch, both faces [W]. */
  heatW: number;
  /** Steady lumped disk temperature — the TPV emitter. */
  diskTempC: number;
  diskTempK: number;
  /** Fuel temperature required to radiate heatW onto the disk. */
  fuelTempC: number;
  fuelTempK: number;
  tpvCellTempK: number;
  cellEmissivity: number;
  /** Both faces: 2 × A / (1/ε_fuel + 1/ε_disk − 1). */
  grFuel: number;
  /** Both faces: 2 × A_tpv / (1/ε_disk + 1/ε_cell − 1). */
  grTpv: number;
};

/**
 * Disk temperature from the heat of one layer, moved by radiation only.
 *
 * Heat of one column over one pitch (both faces) is
 *   Q = P_electrical / η = 1000 × (2 × ρ × 10 × A_tpv) / (η/100)  [W].
 * At steady state that heat leaves the fuel by radiation to the disk and
 * the disk radiates the same heat onto the cells:
 *   Q = σ Gr_fuel (T_fuel⁴ − T_disk⁴) = σ Gr_tpv (T_disk⁴ − T_cell⁴).
 * Each Gr covers both faces of the layer. The cells are opaque, so
 * ε_cell = 1 − reflectance. T_disk follows from the cell side; T_fuel is
 * the temperature that delivers the same Q across the fuel gap.
 */
export function diskTemperatureFromLayerHeat(options: {
  heatW: number;
  fuelEmissivity: number;
  diskEmissivity: number;
  cellReflectance: number;
  fuelAreaM2: number;
  tpvAreaM2: number;
  tpvCellTempK?: number;
}): LayerDiskRadiation {
  const tpvCellTempK = options.tpvCellTempK ?? TPV_CELL_TEMP_K;
  const cellEmissivity = emissivityFromReflectance(options.cellReflectance);
  const grFuel = 2 * radiationFactorM2(options.fuelAreaM2, options.fuelEmissivity, options.diskEmissivity);
  const grTpv = 2 * radiationFactorM2(options.tpvAreaM2, options.diskEmissivity, cellEmissivity);
  const heatW = Number.isFinite(options.heatW) && options.heatW > 0 ? options.heatW : 0;
  let diskTempK = tpvCellTempK;
  let fuelTempK = tpvCellTempK;
  if (heatW > 0 && grTpv > 0) {
    const diskT4 = tpvCellTempK ** 4 + heatW / (SIGMA_W_M2_K4 * grTpv);
    diskTempK = Math.pow(diskT4, 0.25);
    if (grFuel > 0) {
      const fuelT4 = diskT4 + heatW / (SIGMA_W_M2_K4 * grFuel);
      fuelTempK = Math.pow(fuelT4, 0.25);
    } else {
      fuelTempK = diskTempK;
    }
  }
  return {
    heatW,
    diskTempC: diskTempK - 273.15,
    diskTempK,
    fuelTempC: fuelTempK - 273.15,
    fuelTempK,
    tpvCellTempK,
    cellEmissivity,
    grFuel,
    grTpv,
  };
}
