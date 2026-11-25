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

/**
 * One graphite shield lump.
 * Each zone is a disk-facing ring area times that group's own layer-designer thickness.
 */
export function shieldGraphiteThermal(
  zones: readonly { areaM2: number; thicknessCm: number }[],
): GraphiteLumpedThermal {
  let massKg = 0;
  let areaM2 = 0;
  for (const zone of zones) {
    const area = Number.isFinite(zone.areaM2) && zone.areaM2 > 0 ? zone.areaM2 : 0;
    const thicknessM = Number.isFinite(zone.thicknessCm) && zone.thicknessCm > 0 ? zone.thicknessCm / 100 : 0;
    massKg += GRAPHITE_DENSITY_KG_M3 * area * thicknessM;
    areaM2 += area;
  }
  return {
    heatCapacity: massKg * GRAPHITE_CP_J_KG_K,
    massKg,
    thicknessM: areaM2 > 0 ? massKg / (GRAPHITE_DENSITY_KG_M3 * areaM2) : 0,
    areaM2,
  };
}

/**
 * Helium conductance of one shield conductor when its arc is fully covered.
 * One disk face uses the fuel-side gap, the other the shell-side gap,
 * each G = k A / d over the one-face shield area. `shieldAreaM2` is that area.
 */
export function shieldHeliumPerFace(
  gFuelBothFaces: number,
  gShellBothFaces: number,
  fuelAreaM2: number,
  tpvAreaM2: number,
  shieldAreaM2: number,
  shieldArcSum: number,
  nSections: number = RIMAEL_N_SECTIONS,
): number {
  const shield = Number.isFinite(shieldAreaM2) && shieldAreaM2 > 0 ? shieldAreaM2 : 0;
  const fuelFace = fuelAreaM2 > 0 ? Math.max(gFuelBothFaces, 0) * (shield / fuelAreaM2) / 2 : 0;
  const shellFace = tpvAreaM2 > 0 ? Math.max(gShellBothFaces, 0) * (shield / tpvAreaM2) / 2 : 0;
  return perFaceFullWindow(fuelFace + shellFace, shieldArcSum, nSections);
}

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

/**
 * Modelica per-face factor for one sector window fully on an arc.
 * Twelve sectors rotate together. The time average of one sector's overlap
 * fraction is the arc fraction, and each sector has two faces, so
 * 2 · N · arcFrac · value_face = value over the whole area.
 */
export function perFaceFullWindow(
  wholeArea: number,
  arcFrac: number,
  nSections: number = RIMAEL_N_SECTIONS,
): number {
  const arc = Math.min(1, Math.max(arcFrac, 1e-6));
  const n = Math.max(1, Math.round(nSections));
  if (!(wholeArea > 0)) return 0;
  return wholeArea / (2 * n * arc);
}

/** TPV cell coolant temperature in the thermodynamics tab and in RIMAEL.Reactor. */
export const TPV_CELL_TEMP_K = 298.15;

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

/**
 * Helium thermal conductivity at 1 atm [W/(m·K)].
 * Power-law fit to k(300 K) = 0.156 and k(1000 K) = 0.360.
 * Near 1 atm, k is set by temperature, not by pressure.
 */
export function heliumConductivityWPerMK(tempK: number): number {
  const t = Math.min(3000, Math.max(250, tempK));
  return 2.96e-3 * t ** 0.6945;
}

export type LayerHeatTransfer = {
  /** Heat of one column over one pitch, both faces [W]. The same heat crosses every gap. */
  heatW: number;
  diskTempC: number;
  diskTempK: number;
  /** Vacuum-insulation shell. This is the surface the cells see. */
  shellTempC: number;
  shellTempK: number;
  /** Fuel temperature required to deliver heatW to the disk. */
  fuelTempC: number;
  fuelTempK: number;
  tpvCellTempK: number;
  cellEmissivity: number;
  shellEmissivity: number;
  /** Both faces, fuel ↔ disk. */
  grFuel: number;
  /** Both faces, disk ↔ vacuum shell, across helium. */
  grDiskShell: number;
  /** Both faces, shell ↔ cells, across vacuum. */
  grShellCell: number;
  /** Helium conduction, fuel ↔ disk [W/K], at the solved film temperature. */
  gFuelWPerK: number;
  /** Helium conduction, disk ↔ shell [W/K], at the solved film temperature. */
  gDiskShellWPerK: number;
  /** Share of Q carried by helium conduction on that gap. */
  conductionShareFuel: number;
  conductionShareDisk: number;
  fuelGapCm: number;
  tpvGapCm: number;
};

function gapM(gapCm: number): number {
  return Number.isFinite(gapCm) && gapCm > 0 ? gapCm / 100 : 0;
}

/** Radiation plus helium conduction across one gap. Area is both faces [m²]. */
function heatAcrossGapW(
  hotK: number,
  coldK: number,
  gr: number,
  areaM2: number,
  gapMeters: number,
): { totalW: number; conductionW: number; gWPerK: number } {
  const rad = SIGMA_W_M2_K4 * Math.max(gr, 0) * (hotK ** 4 - coldK ** 4);
  if (!(gapMeters > 0) || !(areaM2 > 0) || !(hotK > coldK)) {
    return { totalW: Math.max(0, rad), conductionW: 0, gWPerK: 0 };
  }
  const k = heliumConductivityWPerMK(0.5 * (hotK + coldK));
  const gWPerK = (k * areaM2) / gapMeters;
  const conductionW = gWPerK * (hotK - coldK);
  return { totalW: rad + conductionW, conductionW, gWPerK };
}

function flowW(hotK: number, coldK: number, gr: number, areaM2: number, gapMeters: number): number {
  return heatAcrossGapW(hotK, coldK, gr, areaM2, gapMeters).totalW;
}

/** Hot-side temperature that delivers heatW to a known cold side. */
function solveHotTemperatureK(
  coldK: number,
  heatW: number,
  gr: number,
  areaM2: number,
  gapMeters: number,
): number {
  if (!(heatW > 0) || !(coldK > 0)) return coldK;
  const flow = (hotK: number) => flowW(hotK, coldK, gr, areaM2, gapMeters);
  if (!(gr > 0) && !(gapMeters > 0 && areaM2 > 0)) return coldK;
  let lo = coldK;
  let hi = coldK + 1;
  for (let i = 0; i < 40 && flow(hi) < heatW; i += 1) {
    hi = coldK + (hi - coldK) * 1.8;
    if (hi > 6000) break;
  }
  if (flow(hi) < heatW) return hi;
  for (let i = 0; i < 70; i += 1) {
    const mid = 0.5 * (lo + hi);
    if (flow(mid) < heatW) lo = mid;
    else hi = mid;
  }
  return 0.5 * (lo + hi);
}

export type FuelToShellHeat = {
  /** Heat of one column over one pitch, both faces [W]. */
  heatW: number;
  diskTempC: number;
  diskTempK: number;
  shellTempK: number;
  fuelTempK: number;
  shellEmissivity: number;
  grFuel: number;
  grDiskShell: number;
  gFuelWPerK: number;
  gDiskShellWPerK: number;
  conductionShareFuel: number;
  conductionShareDisk: number;
};

/**
 * Heat that flows from a fixed fuel temperature to a chosen shell temperature.
 * Cell reflectance does not enter: the vacuum gap is downstream of the shell.
 * fuel —(radiation + He)— disk —(radiation + He)— shell.
 */
export function heatFromFuelToShell(options: {
  fuelTempC: number;
  shellTempC: number;
  fuelEmissivity: number;
  diskEmissivity: number;
  shellEmissivity: number;
  fuelAreaM2: number;
  tpvAreaM2: number;
  fuelGapCm: number;
  tpvGapCm: number;
}): FuelToShellHeat {
  const fuelTempK = options.fuelTempC + 273.15;
  const shellTempK = options.shellTempC + 273.15;
  const shellEmissivity = Math.min(1, Math.max(0.01, options.shellEmissivity));
  const fuelArea = Math.max(0, 2 * options.fuelAreaM2);
  const tpvArea = Math.max(0, 2 * options.tpvAreaM2);
  const grFuel = 2 * radiationFactorM2(options.fuelAreaM2, options.fuelEmissivity, options.diskEmissivity);
  const grDiskShell = 2 * radiationFactorM2(options.tpvAreaM2, options.diskEmissivity, shellEmissivity);
  const fuelGap = gapM(options.fuelGapCm);
  const tpvGap = gapM(options.tpvGapCm);
  const empty = {
    heatW: 0,
    diskTempC: options.fuelTempC,
    diskTempK: fuelTempK,
    shellTempK,
    fuelTempK,
    shellEmissivity,
    grFuel,
    grDiskShell,
    gFuelWPerK: 0,
    gDiskShellWPerK: 0,
    conductionShareFuel: 0,
    conductionShareDisk: 0,
  };
  if (!(shellTempK < fuelTempK) || !(fuelArea > 0) || !(tpvArea > 0)) return empty;

  let lo = shellTempK;
  let hi = fuelTempK;
  for (let i = 0; i < 60; i += 1) {
    const mid = 0.5 * (lo + hi);
    const fromFuel = flowW(fuelTempK, mid, grFuel, fuelArea, fuelGap);
    const toShell = flowW(mid, shellTempK, grDiskShell, tpvArea, tpvGap);
    if (fromFuel > toShell) lo = mid;
    else hi = mid;
  }
  const diskTempK = 0.5 * (lo + hi);
  const fuelGapFlow = heatAcrossGapW(fuelTempK, diskTempK, grFuel, fuelArea, fuelGap);
  const diskGap = heatAcrossGapW(diskTempK, shellTempK, grDiskShell, tpvArea, tpvGap);
  const heatW = fuelGapFlow.totalW;
  const share = (conductionW: number) => (heatW > 0 ? Math.min(1, Math.max(0, conductionW / heatW)) : 0);
  return {
    heatW,
    diskTempC: diskTempK - 273.15,
    diskTempK,
    shellTempK,
    fuelTempK,
    shellEmissivity,
    grFuel,
    grDiskShell,
    gFuelWPerK: fuelGapFlow.gWPerK,
    gDiskShellWPerK: diskGap.gWPerK,
    conductionShareFuel: share(fuelGapFlow.conductionW),
    conductionShareDisk: share(diskGap.conductionW),
  };
}

/**
 * Gray cell reflectance that makes the vacuum gap carry heatW at this shell temperature.
 * Null when no reflectance in [0, 1) can do it: the shell cannot emit that much heat.
 */
export function cellReflectanceForHeat(options: {
  heatW: number;
  shellTempK: number;
  shellEmissivity: number;
  tpvAreaM2: number;
  tpvCellTempK?: number;
}): { reflectance: number; emissivity: number } | null {
  const heatW = options.heatW;
  const shellTempK = options.shellTempK;
  const cellTempK = options.tpvCellTempK ?? TPV_CELL_TEMP_K;
  const shellEmissivity = Math.min(1, Math.max(0.01, options.shellEmissivity));
  const oneFaceM2 = options.tpvAreaM2;
  if (!(heatW > 0) || !(oneFaceM2 > 0) || !(shellTempK > cellTempK)) return null;
  const delta = shellTempK ** 4 - cellTempK ** 4;
  const exchange = (SIGMA_W_M2_K4 * 2 * oneFaceM2 * delta) / heatW;
  const invEmissivity = exchange - 1 / shellEmissivity + 1;
  if (!(invEmissivity >= 1)) return null;
  const emissivity = 1 / invEmissivity;
  if (!(emissivity > 0) || emissivity > 1) return null;
  return { reflectance: 1 - emissivity, emissivity };
}

/**
 * Steady temperatures for one layer in helium at 1 atm.
 *
 * Heat of one column over one pitch is fixed by the TPV loading,
 *   Q = 1000 × (2 × ρ × 10 × A_tpv) / (η/100).
 * Disk, shell, and fuel temperatures are the ones that carry that same Q:
 *   fuel —(radiation + He conduction)— disk
 *        —(radiation + He conduction)— vacuum-insulation shell
 *        —(radiation only)— cells in vacuum.
 * The fuel temperature is an output. The shell is thin and isothermal, with
 * one emissivity on both faces. ε_cell = 1 − reflectance. Helium gaps are the
 * disk stack's Void sheets. The cells see the shell.
 */
export function diskTemperatureFromLayerHeat(options: {
  heatW: number;
  fuelEmissivity: number;
  diskEmissivity: number;
  shellEmissivity: number;
  cellReflectance: number;
  fuelAreaM2: number;
  tpvAreaM2: number;
  /** Helium gap on the fuel side of the disk [cm]. */
  fuelGapCm: number;
  /** Helium gap between the disk and the vacuum shell [cm]. */
  tpvGapCm: number;
  tpvCellTempK?: number;
}): LayerHeatTransfer {
  const tpvCellTempK = options.tpvCellTempK ?? TPV_CELL_TEMP_K;
  const cellEmissivity = emissivityFromReflectance(options.cellReflectance);
  const shellEmissivity = Math.min(1, Math.max(0.01, options.shellEmissivity));
  const fuelArea = Math.max(0, 2 * options.fuelAreaM2);
  const tpvArea = Math.max(0, 2 * options.tpvAreaM2);
  const grFuel = 2 * radiationFactorM2(options.fuelAreaM2, options.fuelEmissivity, options.diskEmissivity);
  const grDiskShell = 2 * radiationFactorM2(options.tpvAreaM2, options.diskEmissivity, shellEmissivity);
  const grShellCell = 2 * radiationFactorM2(options.tpvAreaM2, shellEmissivity, cellEmissivity);
  const fuelGap = gapM(options.fuelGapCm);
  const tpvGap = gapM(options.tpvGapCm);
  const heatW = Number.isFinite(options.heatW) && options.heatW > 0 ? options.heatW : 0;

  let shellTempK = tpvCellTempK;
  if (heatW > 0 && grShellCell > 0) {
    shellTempK = Math.pow(tpvCellTempK ** 4 + heatW / (SIGMA_W_M2_K4 * grShellCell), 0.25);
  }
  const diskTempK = solveHotTemperatureK(shellTempK, heatW, grDiskShell, tpvArea, tpvGap);
  const fuelTempK = solveHotTemperatureK(diskTempK, heatW, grFuel, fuelArea, fuelGap);
  const diskGap = heatAcrossGapW(diskTempK, shellTempK, grDiskShell, tpvArea, tpvGap);
  const fuelGapFlow = heatAcrossGapW(fuelTempK, diskTempK, grFuel, fuelArea, fuelGap);
  const share = (conductionW: number) => (heatW > 0 ? Math.min(1, Math.max(0, conductionW / heatW)) : 0);

  return {
    heatW,
    diskTempC: diskTempK - 273.15,
    diskTempK,
    shellTempC: shellTempK - 273.15,
    shellTempK,
    fuelTempC: fuelTempK - 273.15,
    fuelTempK,
    tpvCellTempK,
    cellEmissivity,
    shellEmissivity,
    grFuel,
    grDiskShell,
    grShellCell,
    gFuelWPerK: fuelGapFlow.gWPerK,
    gDiskShellWPerK: diskGap.gWPerK,
    conductionShareFuel: share(fuelGapFlow.conductionW),
    conductionShareDisk: share(diskGap.conductionW),
    fuelGapCm: fuelGap * 100,
    tpvGapCm: tpvGap * 100,
  };
}
