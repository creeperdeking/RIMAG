import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Form } from "react-bootstrap";

const POWER_KEY = "rimael-live-power-kw";
const SCALE_KEY = "rimael-live-scale";
const SCALES = [1, 10, 60] as const;

export type LiveSample = {
  timeS: number;
  powerW: number;
  rps: number;
  fuelC: number;
  shellC: number;
  shieldC: number;
  /** Temperature of the section whose window starts at 0° [°C]. */
  section0C: number;
};

/** One degree of lab angle. Section 0 writes its temperature here as it sweeps past. */
const HEAT_BINS = 360;
const SECTION_DEG = 30;

function emptySlots(): (number | null)[] {
  return Array.from({ length: HEAT_BINS }, () => null);
}

function mod360(deg: number): number {
  const wrapped = deg % 360;
  return wrapped < 0 ? wrapped + 360 : wrapped;
}

function slotIndex(deg: number): number {
  return Math.floor(mod360(deg)) % HEAT_BINS;
}

/**
 * Blend section 0's temperature across the arc it just traveled, one degree at a time.
 * One call never wraps the memory more than once.
 */
function paintTravelLerp(
  slots: (number | null)[],
  fromDeg: number,
  toDeg: number,
  fromC: number,
  toC: number,
): void {
  let span = toDeg - fromDeg;
  if (span < -1e-6) span = mod360(span);
  if (span < 1e-4) {
    slots[slotIndex(toDeg)] = toC;
    touchHeat();
    return;
  }
  span = Math.min(359, span);
  const steps = Math.ceil(span);
  for (let i = 0; i <= steps; i += 1) {
    const u = i / steps;
    slots[slotIndex(fromDeg + (span * i) / steps)] = fromC + (toC - fromC) * u;
  }
  touchHeat();
}

let heatGen = 0;
let paintedGen = -1;
let paintedGeom = "";
let heatUrl = "";
let heatCanvas: HTMLCanvasElement | null = null;
let lastRenderAt = 0;

function touchHeat(force = false): void {
  heatGen += 1;
  if (force) lastRenderAt = 0;
}

/** Smooth ring. Canvas conic stops blend from one degree to the next, so no wedge edges show. */
function renderHeat(slots: (number | null)[], fuelOnTop: number, innerFrac: number): string {
  if (typeof document === "undefined") return "";
  if (!heatCanvas) {
    heatCanvas = document.createElement("canvas");
    heatCanvas.width = 768;
    heatCanvas.height = 768;
  }
  const size = heatCanvas.width;
  const ctx = heatCanvas.getContext("2d");
  if (!ctx) return "";
  const cx = size / 2;
  const cy = size / 2;
  const outer = size / 2 - 1;
  const inner = Math.max(0, innerFrac) * (size / 2);
  let lo = Infinity;
  let hi = -Infinity;
  let known = 0;
  for (let i = 0; i < slots.length; i += 1) {
    const value = slots[i];
    if (value == null) continue;
    known += 1;
    if (value < lo) lo = value;
    if (value > hi) hi = value;
  }
  const colorAt = (lab: number) => {
    const value = slots[slotIndex(lab)];
    return value == null || known === 0 ? "#cbd5e1" : sectionColor(value, lo, hi);
  };
  ctx.clearRect(0, 0, size, size);
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, outer, 0, Math.PI * 2);
  ctx.clip();
  if (typeof ctx.createConicGradient === "function") {
    // Canvas angles start at +x and run clockwise. Lab angle grows counter-clockwise from fuelOnTop.
    const gradient = ctx.createConicGradient((-fuelOnTop * Math.PI) / 180, cx, cy);
    for (let i = 0; i <= HEAT_BINS; i += 1) {
      gradient.addColorStop(i / HEAT_BINS, colorAt(-i));
    }
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
  } else {
    const radius = (outer + inner) / 2;
    ctx.lineWidth = Math.max(1, outer - inner);
    for (let i = 0; i < HEAT_BINS; i += 1) {
      ctx.strokeStyle = colorAt(i);
      ctx.beginPath();
      const a0 = -((fuelOnTop + i - 0.35) * Math.PI) / 180;
      const a1 = -((fuelOnTop + i + 1.35) * Math.PI) / 180;
      ctx.arc(cx, cy, radius, a0, a1, true);
      ctx.stroke();
    }
  }
  ctx.restore();
  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx, cy, Math.max(0, inner - 0.5), 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
  return heatCanvas.toDataURL();
}

/** Spin the section-0 mark, and rebuild the ring only after the temperature memory changes. */
function applyDiskPaint(svg: SVGSVGElement | null, angleDeg: number, slots: (number | null)[]): void {
  if (!svg) return;
  const transform = `rotate(${(-angleDeg).toFixed(2)})`;
  svg.querySelectorAll("[data-rotor]").forEach((node) => {
    node.setAttribute("transform", transform);
  });
  const geom = `${svg.getAttribute("data-fuel-on-top")}|${svg.getAttribute("data-inner")}`;
  const images = svg.querySelectorAll("[data-heat]");
  const dirty = paintedGen !== heatGen || paintedGeom !== geom || !heatUrl;
  if (dirty && (heatUrl === "" || performance.now() - lastRenderAt >= 200)) {
    heatUrl = renderHeat(slots, Number(svg.getAttribute("data-fuel-on-top")), Number(svg.getAttribute("data-inner")));
    lastRenderAt = performance.now();
    paintedGen = heatGen;
    paintedGeom = geom;
    images.forEach((node) => node.setAttribute("data-painted", ""));
  }
  images.forEach((node) => {
    if (node.getAttribute("data-painted") === "1") return;
    node.setAttribute("href", heatUrl);
    node.setAttribute("data-painted", "1");
  });
}

/**
 * Rebuild the color memory by walking the recorded speed.
 * A repeated timestamp only refreshes the place section 0 is already on.
 * A large step backwards is a new run and starts the memory over once.
 */
function slotsFromHistory(history: LiveSample[]): { slots: (number | null)[]; angle: number } {
  const slots = emptySlots();
  let angle = 0;
  let prevT: number | null = null;
  let prevTemp: number | null = null;
  for (const sample of history) {
    if (!Number.isFinite(sample.section0C)) continue;
    if (prevT != null && sample.timeS + 0.5 < prevT) {
      slots.fill(null);
      angle = 0;
      prevT = null;
      prevTemp = null;
    }
    const dt = prevT == null ? 0 : sample.timeS - prevT;
    if (dt > 1e-6) {
      const next = angle + 360 * Math.max(0, sample.rps) * dt;
      paintTravelLerp(slots, angle, next, prevTemp ?? sample.section0C, sample.section0C);
      angle = mod360(next);
    } else {
      slots[slotIndex(angle)] = sample.section0C;
    }
    prevT = sample.timeS;
    prevTemp = sample.section0C;
  }
  return { slots, angle };
}

type ReadyEvent = {
  type: "ready";
  running?: boolean;
  message?: string;
  history?: LiveSample[];
};

type StreamEvent =
  | ReadyEvent
  | { type: "status"; running?: boolean; message?: string }
  | { type: "sample"; sample: LiveSample }
  | { type: "control"; powerW: number; rps: number; scale: number }
  | { type: "done"; message?: string }
  | { type: "error"; message?: string };

type Props = {
  geometryBody: Record<string, number>;
  nominalPowerW: number;
  diskRps: string;
  columns: number;
  innerRadiusM: number;
  outerRadiusM: number;
  fuelArcFrac: number;
  shield1ArcFrac: number;
  tpvArcFrac: number;
  shield2ArcFrac: number;
  batchRunning: boolean;
};

function storedNumber(key: string): number | null {
  try {
    const value = Number(window.localStorage.getItem(key));
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

function remember(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage may be unavailable */
  }
}

function sectionColor(tempC: number, lo: number, hi: number): string {
  const span = Math.max(8, hi - lo);
  const t = Math.min(1, Math.max(0, (tempC - lo) / span));
  const r = Math.round(36 + 214 * t);
  const g = Math.round(64 + 150 * Math.sin(Math.PI * t));
  const b = Math.round(196 * (1 - t));
  return `rgb(${r},${g},${b})`;
}

function arcPath(a0: number, a1: number, r0: number, r1: number): string {
  const steps = 10;
  const point = (radius: number, deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return `${(radius * Math.cos(rad)).toFixed(2)},${(-radius * Math.sin(rad)).toFixed(2)}`;
  };
  const outer: string[] = [];
  const inner: string[] = [];
  for (let i = 0; i <= steps; i += 1) {
    const deg = a0 + ((a1 - a0) * i) / steps;
    outer.push(point(r1, deg));
    inner.push(point(r0, deg));
  }
  return `M ${outer[0]} ${outer.slice(1).map((p) => `L ${p}`).join(" ")} ${inner
    .reverse()
    .map((p) => `L ${p}`)
    .join(" ")} Z`;
}

const DiskView = React.memo(function DiskView({
  columns,
  innerFrac,
  angleRef,
  svgRef,
  slotsRef,
  fuelArcFrac,
  shield1ArcFrac,
  tpvArcFrac,
  shield2ArcFrac,
}: {
  columns: number;
  innerFrac: number;
  /** Live rotation, degrees. The animation writes this; render must not snap it back to 0. */
  angleRef: React.MutableRefObject<number>;
  svgRef: React.MutableRefObject<SVGSVGElement | null>;
  /** Temperature section 0 left at each lab degree. The animation paints the slices from this. */
  slotsRef: React.MutableRefObject<(number | null)[]>;
  fuelArcFrac: number;
  shield1ArcFrac: number;
  tpvArcFrac: number;
  shield2ArcFrac: number;
}) {
  const n = Math.min(3, Math.max(1, Math.round(columns) || 1));
  const pitch = 2.7;
  const width = n * pitch + 0.4;
  const fuelEnd = fuelArcFrac * 360;
  const shield1End = fuelEnd + shield1ArcFrac * 360;
  const tpvEnd = shield1End + tpvArcFrac * 360;
  const shield2End = tpvEnd + shield2ArcFrac * 360;
  // Model 0° is the start of the fuel arc, drawn to the right. Shift so that arc is centered at the top.
  const fuelOnTop = 90 - fuelEnd / 2;
  const stator = [
    { a0: fuelOnTop, a1: fuelOnTop + fuelEnd, fill: "rgba(217, 119, 6, 0.55)", name: "Fuel" },
    { a0: fuelOnTop + fuelEnd, a1: fuelOnTop + shield1End, fill: "rgba(100, 116, 139, 0.45)", name: "Shield" },
    { a0: fuelOnTop + shield1End, a1: fuelOnTop + tpvEnd, fill: "rgba(37, 99, 235, 0.4)", name: "TPV" },
    { a0: fuelOnTop + tpvEnd, a1: fuelOnTop + shield2End, fill: "rgba(71, 85, 105, 0.4)", name: "Shield" },
  ];
  const rim = (fuelOnTop * Math.PI) / 180;
  const rimCos = Math.cos(rim);
  const rimSin = -Math.sin(rim);
  useLayoutEffect(() => {
    applyDiskPaint(svgRef.current, angleRef.current, slotsRef.current);
  });

  return (
    <svg
      ref={svgRef}
      viewBox={`${-width / 2} -1.55 ${width} 3.15`}
      data-fuel-on-top={fuelOnTop}
      data-inner={innerFrac}
      role="img"
      aria-label="Turning disk colored by the continuous temperature section 0 left behind"
    >
      {Array.from({ length: n }, (_, disk) => {
        const cx = (disk - (n - 1) / 2) * pitch;
        return (
          <g key={disk} transform={`translate(${cx} 0)`}>
            {stator.map((arc) =>
              arc.a1 - arc.a0 > 0.5 ? (
                <path key={arc.name + arc.a0} d={arcPath(arc.a0, arc.a1, 1.08, 1.34)} fill={arc.fill} />
              ) : null,
            )}
            <image data-heat="" x={-1} y={-1} width={2} height={2} href="" />
            <g data-rotor="">
              <path d={arcPath(fuelOnTop, fuelOnTop + SECTION_DEG, 1.015, 1.055)} fill="#0f172a" />
              <line
                x1={rimCos}
                y1={rimSin}
                x2={1.07 * rimCos}
                y2={1.07 * rimSin}
                stroke="#0f172a"
                strokeWidth={0.03}
                strokeLinecap="round"
              />
            </g>
            <circle r={innerFrac * 0.72} fill="#f8fafc" stroke="#94a3b8" strokeWidth={0.02} />
          </g>
        );
      })}
    </svg>
  );
});

function LiveChart({ samples }: { samples: LiveSample[] }) {
  const width = 640;
  const height = 180;
  const pad = { left: 48, right: 12, top: 16, bottom: 28 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const windowed = samples.slice(-240);
  const paths = useMemo(() => {
    if (windowed.length < 2) return [];
    const t0 = windowed[0].timeS;
    const t1 = windowed[windowed.length - 1].timeS;
    const temps = windowed.flatMap((sample) => [sample.fuelC, sample.shellC, sample.shieldC]);
    let lo = Math.min(...temps);
    let hi = Math.max(...temps);
    if (hi - lo < 5) {
      lo -= 2.5;
      hi += 2.5;
    }
    const xOf = (time: number) => pad.left + ((time - t0) / Math.max(1e-6, t1 - t0)) * plotW;
    const yOf = (temp: number) => pad.top + ((hi - temp) / (hi - lo)) * plotH;
    const line = (pick: (sample: LiveSample) => number) =>
      windowed.map((sample, index) => `${index === 0 ? "M" : "L"} ${xOf(sample.timeS).toFixed(1)} ${yOf(pick(sample)).toFixed(1)}`).join(" ");
    return [
      { name: "Fuel", color: "#c2410c", path: line((sample) => sample.fuelC) },
      { name: "Shield", color: "#475569", path: line((sample) => sample.shieldC) },
      { name: "Shell", color: "#2563eb", path: line((sample) => sample.shellC) },
    ];
  }, [windowed, plotW, plotH]);
  if (windowed.length < 2) return null;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Live fuel, shield, and shell temperature">
      {paths.map((item) => (
        <path key={item.name} d={item.path} fill="none" stroke={item.color} strokeWidth={2} />
      ))}
      {paths.map((item, index) => (
        <text key={item.name} x={pad.left + index * 90} y={14} fill={item.color} fontSize={12}>
          {item.name}
        </text>
      ))}
      <text x={width / 2} y={height - 6} textAnchor="middle" fontSize={11} fill="#64748b">
        model time (s)
      </text>
    </svg>
  );
}

const LiveReactorPanel: React.FC<Props> = ({
  geometryBody,
  nominalPowerW,
  diskRps,
  columns,
  innerRadiusM,
  outerRadiusM,
  fuelArcFrac,
  shield1ArcFrac,
  tpvArcFrac,
  shield2ArcFrac,
  batchRunning,
}) => {
  const nominalKw = nominalPowerW > 0 ? nominalPowerW / 1000 : 0;
  const [powerText, setPowerText] = useState(() => {
    const stored = storedNumber(POWER_KEY);
    return (stored != null && stored >= 0 ? stored : nominalKw).toFixed(1);
  });
  const [scale, setScale] = useState(() => {
    const stored = storedNumber(SCALE_KEY);
    return stored === 10 || stored === 60 ? stored : 1;
  });
  const [live, setLive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState("Idle");
  const [error, setError] = useState<string | null>(null);
  const [sample, setSample] = useState<LiveSample | null>(null);
  const [samples, setSamples] = useState<LiveSample[]>([]);
  const [slotC, setSlotC] = useState<(number | null)[]>(emptySlots);
  const bodyRef = useRef(geometryBody);
  bodyRef.current = geometryBody;
  const svgRef = useRef<SVGSVGElement | null>(null);
  const angleRef = useRef(0);
  const anchorRef = useRef<{ angle: number; temp: number } | null>(null);
  const lastTempRef = useRef<number | null>(null);
  const slotsRef = useRef<(number | null)[]>(emptySlots());
  const scaleRef = useRef(scale);
  scaleRef.current = scale;
  const liveRef = useRef(live);
  liveRef.current = live;
  const rpsNow = Number(diskRps);
  const rpsRef = useRef(0);
  rpsRef.current = Number.isFinite(rpsNow) && rpsNow >= 0 ? rpsNow : 0;

  const slotsPosted = useRef(0);
  const publishSlots = (next: (number | null)[], force = false) => {
    slotsRef.current = next;
    const now = performance.now();
    if (!force && now - slotsPosted.current < 200) return;
    slotsPosted.current = now;
    setSlotC(next.slice());
  };

  const resetDisk = () => {
    angleRef.current = 0;
    anchorRef.current = null;
    lastTempRef.current = null;
    publishSlots(emptySlots(), true);
    touchHeat(true);
    applyDiskPaint(svgRef.current, 0, slotsRef.current);
  };

  useEffect(() => {
    const source = new EventSource("/api/rimael/live/stream");
    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as StreamEvent;
      if (data.type === "ready" || data.type === "status") {
        if (typeof data.running === "boolean") setLive(data.running);
        if (data.message) setMessage(data.message);
        if (data.type === "ready" && Array.isArray(data.history) && data.history.length) {
          setSamples(data.history);
          setSample(data.history[data.history.length - 1]);
          const built = slotsFromHistory(data.history);
          if (!liveRef.current) angleRef.current = built.angle;
          lastTempRef.current = data.history[data.history.length - 1].section0C;
          anchorRef.current = { angle: angleRef.current, temp: lastTempRef.current };
          publishSlots(built.slots, true);
          touchHeat(true);
          applyDiskPaint(svgRef.current, angleRef.current, slotsRef.current);
        }
      } else if (data.type === "sample") {
        setSample(data.sample);
        if (Number.isFinite(data.sample.section0C)) {
          const temp = data.sample.section0C;
          lastTempRef.current = temp;
          const anchor = anchorRef.current;
          if (anchor) {
            const span = Math.min(90, mod360(angleRef.current - anchor.angle));
            paintTravelLerp(slotsRef.current, angleRef.current - span, angleRef.current, anchor.temp, temp);
          } else {
            slotsRef.current[slotIndex(angleRef.current)] = temp;
            touchHeat();
          }
          anchorRef.current = { angle: angleRef.current, temp };
          publishSlots(slotsRef.current);
        }
        setSamples((prev) => {
          const last = prev[prev.length - 1];
          if (last && data.sample.timeS <= last.timeS + 1e-9) {
            const next = prev.slice();
            next[next.length - 1] = data.sample;
            return next;
          }
          const next = prev.length > 2000 ? prev.slice(-1500) : prev.slice();
          next.push(data.sample);
          return next;
        });
      } else if (data.type === "done") {
        setLive(false);
        if (data.message) setMessage(data.message);
      } else if (data.type === "error") {
        setError(data.message || "The live simulation failed.");
        setLive(false);
      }
    };
    source.onerror = () => {
      /* The browser reconnects. A missing dev server surfaces on Start. */
    };
    return () => source.close();
  }, []);

  useEffect(() => {
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      if (liveRef.current && rpsRef.current > 0) {
        const delta = 360 * rpsRef.current * scaleRef.current * dt;
        angleRef.current = mod360(angleRef.current + delta);
      }
      applyDiskPaint(svgRef.current, angleRef.current, slotsRef.current);
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!live) return;
    const powerKw = Number(powerText);
    const rps = Number(diskRps);
    if (!Number.isFinite(powerKw) || powerKw < 0 || !Number.isFinite(rps) || rps < 0) return;
    const handle = window.setTimeout(() => {
      void fetch("/api/rimael/live/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ power_w: powerKw * 1000, disk_rps: rps, time_scale: scale }),
      });
    }, 150);
    return () => window.clearTimeout(handle);
  }, [live, powerText, diskRps, scale]);

  const powerKw = Number(powerText);
  const sliderMax = Math.max(10, nominalKw * 2, Number.isFinite(powerKw) ? powerKw : 0);
  const innerFrac =
    outerRadiusM > 0 ? Math.min(0.85, Math.max(0.12, innerRadiusM / outerRadiusM)) : 0.25;
  const knownSlots = slotC.filter((value): value is number => value != null);
  const lo = knownSlots.length ? Math.min(...knownSlots) : null;
  const hi = knownSlots.length ? Math.max(...knownSlots) : null;

  const onStart = async () => {
    const rps = Number(diskRps);
    if (!Number.isFinite(powerKw) || powerKw < 0) {
      setError("Reactor power must be zero or a positive number of kilowatts.");
      return;
    }
    if (!Number.isFinite(rps) || rps < 0) {
      setError("Disk speed must be zero or a positive number of revolutions per second.");
      return;
    }
    setStarting(true);
    setError(null);
    setSamples([]);
    setSample(null);
    resetDisk();
    try {
      const response = await fetch("/api/rimael/live/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...bodyRef.current,
          power_w: powerKw * 1000,
          disk_rps: rps,
          time_scale: scale,
        }),
      });
      const data = (await response.json()) as { error?: string; ok?: boolean };
      if (!response.ok || data.ok === false) {
        setError(data.error || `Live start failed (${response.status})`);
        setLive(false);
        return;
      }
      setLive(true);
      setMessage("OpenModelica is integrating in real time");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  const onStop = async () => {
    setLive(false);
    await fetch("/api/rimael/live/stop", { method: "POST" });
    setMessage("Stopped");
  };

  return (
    <div className="mb-4 pb-3 border-bottom">
      <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
        <h2 className="h6 mb-0">Live reactor control</h2>
        <div className="d-flex gap-2">
          <Button size="sm" variant="primary" disabled={starting || batchRunning || live} onClick={() => void onStart()}>
            {starting ? "Starting…" : "Start live"}
          </Button>
          <Button size="sm" variant="outline-secondary" disabled={!live && !starting} onClick={() => void onStop()}>
            Stop
          </Button>
        </div>
      </div>
      <p className="small text-secondary mb-2">
        One OpenModelica process keeps integrating <code>RIMAEL.Reactor</code>. Several times a second it reads the
        power and disk speed you set here, and writes back the fuel, shield, shell, and section 0 temperatures.
        The disk turns steadily in the browser from the speed above. Section 0 leaves a smooth trail of the
        temperature it had as it passed, and that color stays until it comes around again. The ring outside the
        disk is the fixed fuel, shield, and TPV arcs.
      </p>
      <div className="d-flex flex-wrap align-items-end gap-3 mb-2">
        <Form.Group controlId="live-power-kw">
          <Form.Label className="small mb-1">Reactor power (kW)</Form.Label>
          <Form.Control
            size="sm"
            type="number"
            min={0}
            step={1}
            value={powerText}
            style={{ width: "7rem" }}
            onChange={(event) => {
              setPowerText(event.target.value);
              const value = Number(event.target.value);
              if (Number.isFinite(value) && value >= 0) remember(POWER_KEY, String(value));
            }}
          />
        </Form.Group>
        <Form.Group controlId="live-power-range" className="flex-grow-1" style={{ minWidth: "10rem" }}>
          <Form.Label className="small mb-1">
            {Number.isFinite(powerKw) ? powerKw.toFixed(1) : "—"} kW
            {nominalKw > 0 ? ` · operating point ${nominalKw.toFixed(1)} kW` : ""}
          </Form.Label>
          <Form.Range
            min={0}
            max={sliderMax}
            step={nominalKw > 50 ? 1 : 0.1}
            value={Number.isFinite(powerKw) ? Math.min(sliderMax, Math.max(0, powerKw)) : 0}
            onChange={(event) => {
              setPowerText(event.target.value);
              remember(POWER_KEY, event.target.value);
            }}
          />
        </Form.Group>
        <div>
          <div className="small mb-1">Time scale</div>
          <div className="btn-group btn-group-sm" role="group" aria-label="Model time scale">
            {SCALES.map((value) => (
              <Button
                key={value}
                size="sm"
                variant={scale === value ? "primary" : "outline-primary"}
                onClick={() => {
                  setScale(value);
                  remember(SCALE_KEY, String(value));
                }}
              >
                {value}×
              </Button>
            ))}
          </div>
        </div>
      </div>
      <div className="small text-secondary mb-2">
        Disk speed is the field above. {message}
        {sample
          ? ` · t = ${sample.timeS.toFixed(1)} s · fuel ${sample.fuelC.toFixed(1)} °C · shield ${sample.shieldC.toFixed(1)} °C · shell ${sample.shellC.toFixed(1)} °C · ${sample.rps.toFixed(3)} rev/s · ${(sample.powerW / 1000).toFixed(1)} kW`
          : ""}
        {sample ? ` · section 0 ${sample.section0C.toFixed(1)} °C` : ""}
        {lo != null && hi != null ? ` · around the disk ${lo.toFixed(1)}–${hi.toFixed(1)} °C` : ""}
      </div>
      {error && (
        <Alert variant="danger" className="py-2 px-3 small">
          {error}
        </Alert>
      )}
      <DiskView
        columns={columns}
        innerFrac={innerFrac}
        angleRef={angleRef}
        svgRef={svgRef}
        slotsRef={slotsRef}
        fuelArcFrac={fuelArcFrac}
        shield1ArcFrac={shield1ArcFrac}
        tpvArcFrac={tpvArcFrac}
        shield2ArcFrac={shield2ArcFrac}
      />
      <div className="d-flex gap-3 small text-secondary mb-2">
        <span>Cooler places are blue, hotter places are red. Gray has not been visited yet.</span>
        <span>The dark arc just outside the disk is section 0 and turns with it. Outer ring: fuel, shield, TPV, shield.</span>
      </div>
      <LiveChart samples={samples} />
    </div>
  );
};

export default LiveReactorPanel;
