/** Zone geometry for a hollow disk split into fuel, reflector, shield, and TPV. */

export type ZoneLayout = {
  a: number;
  b: number;
  w: number;
  reflector: number;
  percentFuel: number;
  rInner: number;
  rOuter: number;
  totalArea: number;
  absorber: number;
  /** Angle of ONE shield moderator sector, in radians. */
  gapAngle: number;
  /** Angle of ONE reflector sector, in radians. */
  reflectorAngle: number;
  /** Angle of ONE shield absorber sector, in radians. */
  absorberAngle: number;
  fuelAngle: number;
  oppositeAngle: number;
  fuelArea: number;
  oppositeArea: number;
  /** Combined area of both shield moderator sectors. */
  gapArea: number;
  reflectorArea: number;
  absorberArea: number;
  maxPercentFuel: number;
  feasible: boolean;
};

export type CenterCuts = {
  moderatorY: number;
  reflectorY: number | null;
};

export type Point = [number, number];

export type LayerRow = { name: string; cm: number };

export type MaterialSpec = {
  density: number;
  color: string | null;
  /** Carbon moderator. Set in common_lib/materials.py and exported with the catalog. */
  graphite_like?: boolean;
  composition: Array<{
    atom: string;
    atomic_weight: number;
    proportion: number | null;
    enrichment: number | null;
    enrichment_target: string | null;
  }>;
};

export type MixedSpec = {
  materials: string[];
  proportions: number[];
  graphite_like?: boolean;
};

export function chordAngle(thickness: number, innerDiameter: number): number {
  if (thickness <= 0 || innerDiameter <= 0) return 0;
  return 2 * Math.asin(Math.min(1, thickness / innerDiameter));
}

function innerDiameter(a: number, b: number, reflector: number, absorber: number, extra: number): number {
  return a + reflector + absorber + b + extra;
}

function layerAngles(a: number, reflector: number, absorber: number, diameter: number): [number, number, number] {
  return [chordAngle(a, diameter), chordAngle(reflector, diameter), chordAngle(absorber, diameter)];
}

export function maxPercentFuel(a: number, b: number, reflector = 0, absorber = 0): number {
  const diameter = innerDiameter(a, b, reflector, absorber, 0);
  const [moderator, reflected, absorbed] = layerAngles(a, reflector, absorber, diameter);
  return 100 * (1 - (moderator + reflected + absorbed) / Math.PI);
}

export function percentFuelForRatio(
  a: number,
  b: number,
  ratio: number,
  reflector = 0,
  absorber = 0,
  extra = 0,
): number {
  if (ratio <= 0) throw new Error("ratio must be positive");
  const diameter = innerDiameter(a, b, reflector, absorber, extra);
  const [moderator, reflected, absorbed] = layerAngles(a, reflector, absorber, diameter);
  const free = Math.max(0, 2 * Math.PI - 2 * (moderator + reflected + absorbed));
  const fuelAngle = (ratio / (1 + ratio)) * free;
  return (100 * fuelAngle) / (2 * Math.PI);
}

export function computeLayout(
  a: number,
  b: number,
  w: number,
  percentFuel: number,
  reflector = 0,
  absorber = 0,
  extra = 0,
): ZoneLayout {
  if (a <= 0) throw new Error("a must be positive");
  if (b < 0) throw new Error("b must be non-negative");
  if (reflector < 0) throw new Error("reflector must be non-negative");
  if (absorber < 0) throw new Error("absorber must be non-negative");
  if (extra < 0) throw new Error("extra must be non-negative");
  if (w <= 0) throw new Error("w must be positive");
  if (!(percentFuel >= 0 && percentFuel <= 100)) throw new Error("percent_fuel must be between 0 and 100");

  const diameter = innerDiameter(a, b, reflector, absorber, extra);
  const rInner = diameter / 2;
  const rOuter = rInner + w;
  const ring = rOuter ** 2 - rInner ** 2;
  const totalArea = Math.PI * ring;

  const [gapAngle, reflectorAngle, absorberAngle] = layerAngles(a, reflector, absorber, diameter);
  const maxPct = 100 * (1 - (gapAngle + reflectorAngle + absorberAngle) / Math.PI);
  const feasible = percentFuel <= maxPct + 1e-12;

  const fuelAngle = (2 * Math.PI * percentFuel) / 100;
  const oppositeAngle = Math.max(0, 2 * Math.PI - fuelAngle - 2 * (gapAngle + reflectorAngle + absorberAngle));

  return {
    a,
    b,
    w,
    reflector,
    absorber,
    percentFuel,
    rInner,
    rOuter,
    totalArea,
    gapAngle,
    reflectorAngle,
    absorberAngle,
    fuelAngle,
    oppositeAngle,
    fuelArea: (fuelAngle / 2) * ring,
    oppositeArea: (oppositeAngle / 2) * ring,
    gapArea: gapAngle * ring,
    reflectorArea: reflectorAngle * ring,
    absorberArea: absorberAngle * ring,
    maxPercentFuel: maxPct,
    feasible,
  };
}

export function computeLayoutForRatio(
  a: number,
  b: number,
  w: number,
  ratio: number,
  reflector = 0,
  absorber = 0,
): ZoneLayout {
  const percent = percentFuelForRatio(a, b, ratio, reflector, absorber, 0);
  return computeLayout(a, b, w, percent, reflector, absorber, 0);
}

export function centerCuts(layout: ZoneLayout): CenterCuts {
  const ri = layout.rInner;
  const yFuel = ri * Math.cos(layout.fuelAngle / 2);
  const junction = Math.min(Math.PI, layout.oppositeAngle / 2 + layout.absorberAngle);
  const moderatorY = Math.min(yFuel - (layout.a + layout.reflector), -ri * Math.cos(junction));
  let reflectorY: number | null = null;
  if (layout.reflector > 1e-9) {
    reflectorY = ri * Math.cos(layout.fuelAngle / 2 + layout.reflectorAngle);
  }
  return { moderatorY, reflectorY };
}

function arcPoints(cx: number, cy: number, radius: number, a0: number, a1: number, n: number): Point[] {
  const count = Math.max(n, 2);
  const points: Point[] = [];
  for (let i = 0; i < count; i += 1) {
    const angle = a0 + ((a1 - a0) * i) / (count - 1);
    points.push([cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]);
  }
  return points;
}

function appendArc(points: Point[], arc: Point[]): void {
  if (points.length && arc.length) {
    const last = points[points.length - 1];
    const first = arc[0];
    if (Math.hypot(last[0] - first[0], last[1] - first[1]) < 1e-9) {
      points.push(...arc.slice(1));
      return;
    }
  }
  points.push(...arc);
}

function capSweep(center: Point, radius: number, start: Point, end: Point): [number, number] {
  const a0 = Math.atan2(start[1] - center[1], start[0] - center[0]);
  const a1 = Math.atan2(end[1] - center[1], end[0] - center[0]);
  const ccw = (a1 - a0) % (2 * Math.PI);
  const sweeps = [ccw, ccw - 2 * Math.PI];
  const midpoint = (sweep: number): Point => {
    const mid = a0 + sweep / 2;
    return [center[0] + radius * Math.cos(mid), center[1] + radius * Math.sin(mid)];
  };
  const inside = sweeps.filter((sweep) => Math.hypot(...midpoint(sweep)) <= Math.hypot(...center) + 1e-8);
  const sweep = (inside.length ? inside : sweeps).reduce((best, candidate) =>
    Math.hypot(...midpoint(candidate)) < Math.hypot(...midpoint(best)) ? candidate : best,
  );
  return [a0, a0 + sweep];
}

function capMeeting(right: Point, left: Point, thickness: number): Point {
  const midX = (right[0] + left[0]) / 2;
  const midY = (right[1] + left[1]) / 2;
  const span = Math.hypot(right[0] - left[0], right[1] - left[1]);
  const reach = Math.sqrt(Math.max(thickness * thickness - (span / 2) ** 2, 0));
  return [midX - (reach * (right[1] - left[1])) / span, midY + (reach * (right[0] - left[0])) / span];
}

export function absorberFront(layout: ZoneLayout): Point[] | null {
  const thickness = layout.absorber;
  const radius = layout.rInner;
  if (thickness <= 1e-12 || radius <= 1e-12 || thickness >= 2 * radius - 1e-9) return null;
  const alpha = layout.oppositeAngle / 2;
  const phi = layout.absorberAngle;
  const right = -Math.PI / 2 + alpha;
  const left = -Math.PI / 2 - alpha;
  const samples = 96;
  const at = (angle: number, rad: number): Point => [rad * Math.cos(angle), rad * Math.sin(angle)];
  const outer = arcPoints(0, 0, radius, left - phi, right + phi, samples);
  const points: Point[] = [];
  appendArc(points, outer);

  if (thickness < radius - 1e-9) {
    const innerR = radius - thickness;
    const rightEnd = at(right, radius);
    const innerRight = at(right, innerR);
    let [a0, a1] = capSweep(rightEnd, thickness, at(right + phi, radius), innerRight);
    appendArc(points, arcPoints(rightEnd[0], rightEnd[1], thickness, a0, a1, samples / 2));
    appendArc(points, arcPoints(0, 0, innerR, right, left, samples));
    const leftEnd = at(left, radius);
    const innerLeft = at(left, innerR);
    [a0, a1] = capSweep(leftEnd, thickness, innerLeft, at(left - phi, radius));
    appendArc(points, arcPoints(leftEnd[0], leftEnd[1], thickness, a0, a1, samples / 2));
  } else {
    const rightEnd = at(right, radius);
    const leftEnd = at(left, radius);
    if (Math.hypot(rightEnd[0] - leftEnd[0], rightEnd[1] - leftEnd[1]) < 1e-8) {
      const [a0, a1] = capSweep(rightEnd, thickness, at(right + phi, radius), at(left - phi, radius));
      appendArc(points, arcPoints(rightEnd[0], rightEnd[1], thickness, a0, a1, samples));
      return points;
    }
    const meet = capMeeting(rightEnd, leftEnd, thickness);
    let [a0, a1] = capSweep(rightEnd, thickness, at(right + phi, radius), meet);
    appendArc(points, arcPoints(rightEnd[0], rightEnd[1], thickness, a0, a1, samples / 2));
    [a0, a1] = capSweep(leftEnd, thickness, meet, at(left - phi, radius));
    appendArc(points, arcPoints(leftEnd[0], leftEnd[1], thickness, a0, a1, samples / 2));
  }
  return points;
}

function isUraniumAtom(name: string): boolean {
  return name === "U" || (name.length > 1 && name[0] === "U" && /\d/.test(name[1]));
}

function containsUranium(spec: MaterialSpec): boolean {
  return spec.composition.some((part) => isUraniumAtom(part.atom));
}

function libraryParts(
  name: string,
  specs: Record<string, MaterialSpec>,
  mixed: Record<string, MixedSpec>,
): [MaterialSpec | null, MixedSpec | null] {
  if (name in specs) return [specs[name], null];
  const idx = name.lastIndexOf(" ");
  if (idx > 0) {
    const base = name.slice(0, idx);
    const suffix = name.slice(idx + 1);
    if (/^\d+$/.test(suffix) && base in specs) return [specs[base], null];
  }
  let mix = mixed[name] ?? null;
  if (!mix && idx > 0) {
    const base = name.slice(0, idx);
    const suffix = name.slice(idx + 1);
    if (/^\d+$/.test(suffix)) mix = mixed[base] ?? null;
  }
  return [null, mix];
}

export function uraniumBearingDensity(
  name: string,
  specs: Record<string, MaterialSpec>,
  mixed: Record<string, MixedSpec>,
): number | null {
  const [spec, mix] = libraryParts(name.trim(), specs, mixed);
  if (spec) {
    if (!containsUranium(spec) || spec.density <= 0) return null;
    return spec.density;
  }
  if (!mix) return null;
  let uraniumWeight = 0;
  let volume = 0;
  for (let i = 0; i < mix.materials.length; i += 1) {
    const componentSpec = specs[mix.materials[i]];
    const proportion = mix.proportions[i];
    if (!componentSpec || componentSpec.density <= 0 || proportion <= 0) return null;
    volume += proportion / componentSpec.density;
    if (containsUranium(componentSpec)) uraniumWeight += proportion;
  }
  if (uraniumWeight <= 0 || volume <= 0) return null;
  return uraniumWeight / volume;
}

export function uraniumInventoryKg(
  rows: LayerRow[],
  fuelAreaM2: number,
  columns: number,
  stackM: number,
  layerCm: number,
  specs: Record<string, MaterialSpec>,
  mixed: Record<string, MixedSpec>,
): { massKg: number; counted: Array<[string, number, number]>; skipped: string[] } {
  if (layerCm <= 0) return { massKg: 0, counted: [], skipped: [] };
  let massKg = 0;
  const counted: Array<[string, number, number]> = [];
  const skipped: string[] = [];
  for (const row of rows) {
    const name = String(row.name ?? "").trim();
    const density = uraniumBearingDensity(name, specs, mixed);
    if (density == null) {
      if (name.toLowerCase().includes("uranium")) skipped.push(name || "uranium");
      continue;
    }
    const cm = Number(row.cm) || 0;
    const volumeM3 = fuelAreaM2 * columns * stackM * (cm / layerCm);
    const rowKg = volumeM3 * density * 1000;
    massKg += rowKg;
    counted.push([name, rowKg, density]);
  }
  return { massKg, counted, skipped };
}

export function trisoCylinderFractions(
  diameterMm: number,
  wallMarginMm: number,
  spacingMm: number,
  packingPct: number,
  hmParticlePct: number,
): [number, number] {
  const diameter = Number(diameterMm);
  const radius = diameter / 2;
  const pitch = diameter + Number(spacingMm);
  if (diameter <= 0 || radius <= 0 || pitch <= 0) return [0, 0];
  const usable = Math.max(radius - Number(wallMarginMm), 0);
  const packing = Math.min(Math.max(packingPct / 100, 0), 1);
  const hm = Math.min(Math.max(hmParticlePct / 100, 0), 1);
  const particleInCylinder = packing * (usable / radius) ** 2;
  const cellArea = diameter * pitch;
  const hmFraction = (packing * hm * Math.PI * usable * usable) / cellArea;
  return [particleInCylinder, Math.min(Math.max(hmFraction, 0), 1)];
}

function hexLattice(step: number, limit: number): Point[] {
  if (step <= 0) return [[0, 0]];
  const points: Point[] = [[0, 0]];
  let ring = 1;
  while (ring * step <= limit + 1e-9 && ring <= 40) {
    for (let side = 0; side < 6; side += 1) {
      const angle = (Math.PI / 3) * side;
      const cornerX = Math.cos(angle) * ring * step;
      const cornerY = Math.sin(angle) * ring * step;
      const nextAngle = angle + Math.PI / 3;
      const nextX = Math.cos(nextAngle) * ring * step;
      const nextY = Math.sin(nextAngle) * ring * step;
      for (let index = 0; index < ring; index += 1) {
        const share = index / ring;
        points.push([cornerX + (nextX - cornerX) * share, cornerY + (nextY - cornerY) * share]);
      }
    }
    ring += 1;
  }
  return points;
}

export function trisoParticleLayout(
  diameterMm: number,
  wallMarginMm: number,
  packingPct: number,
  hmParticlePct: number,
): Array<[number, number, number, number]> {
  const diameter = Number(diameterMm);
  const radius = diameter / 2;
  const usable = Math.max(radius - Number(wallMarginMm), 0);
  const packing = Math.min(Math.max(packingPct / 100, 0), 1);
  const hm = Math.min(Math.max(hmParticlePct / 100, 0), 1);
  if (diameter <= 0 || usable <= 0 || packing <= 0) return [];
  const target = packing * Math.PI * usable * usable;
  const nominalR = Math.min(0.45, usable * 0.28);
  let chosen: [number, number, number] | null = null;
  for (let rings = 0; rings < 6; rings += 1) {
    const count = 1 + 3 * rings * (rings + 1);
    const particleR = Math.sqrt(target / (count * Math.PI));
    if (particleR > usable) continue;
    const step = rings === 0 ? 0 : (usable - particleR) / rings;
    if (rings && step < 2 * particleR - 1e-9) continue;
    if (!chosen || Math.abs(particleR - nominalR) < Math.abs(chosen[1] - nominalR)) {
      chosen = [rings, particleR, step];
    }
  }
  if (!chosen) return [];
  const [rings, particleR, step] = chosen;
  const limit = Math.max(usable - particleR, 0);
  const points = hexLattice(step, limit).filter((point) => Math.hypot(point[0], point[1]) <= limit + 1e-6);
  const kernelR = particleR * Math.sqrt(hm);
  return points.map((point) => [point[0], point[1], particleR, kernelR]);
}

export function trisoFuelLayers(
  diameterMm: number,
  wallMarginMm: number,
  spacingMm: number,
  packingPct: number,
  hmParticlePct: number,
): { layers: LayerRow[]; particleInCylinder: number; hmFraction: number } {
  const [particleInCylinder, hmFraction] = trisoCylinderFractions(
    diameterMm,
    wallMarginMm,
    spacingMm,
    packingPct,
    hmParticlePct,
  );
  const totalCm = diameterMm / 10;
  const uo2Cm = Math.round(totalCm * hmFraction * 10000) / 10000;
  const graphiteCm = Math.round(((totalCm - uo2Cm) / 2) * 10000) / 10000;
  const coverCm = Math.round((totalCm - uo2Cm - graphiteCm) * 10000) / 10000;
  return {
    layers: [
      { name: "Graphite", cm: graphiteCm },
      { name: "Uranium Dioxide", cm: uo2Cm },
      { name: "Graphite", cm: coverCm },
    ],
    particleInCylinder,
    hmFraction,
  };
}

export function burnupDays(uraniumKg: number, burnupMwdPerKg: number, thermalKw: number): number {
  return (uraniumKg * burnupMwdPerKg) / (thermalKw / 1000);
}

export function formatBurnupTime(days: number): string {
  const monthsTotal = Math.round(days / (365.25 / 12));
  if (monthsTotal <= 0) return "less than a month";
  const years = Math.floor(monthsTotal / 12);
  const months = monthsTotal % 12;
  const parts: string[] = [];
  if (years === 1) parts.push("1 year");
  else if (years) parts.push(`${years} years`);
  if (months === 1) parts.push("1 month");
  else if (months) parts.push(`${months} months`);
  return parts.join(" ");
}
