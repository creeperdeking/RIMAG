import React, { useEffect, useMemo, useRef, useState } from "react";
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

const SLOT_COUNT = 12;
const SLOT_DEG = 30;

function emptySlots(): (number | null)[] {
  return Array.from({ length: SLOT_COUNT }, () => null);
}

function mod360(deg: number): number {
  const wrapped = deg % 360;
  return wrapped < 0 ? wrapped + 360 : wrapped;
}

function slotIndex(deg: number): number {
  return Math.floor(mod360(deg) / SLOT_DEG) % SLOT_COUNT;
}

/** Paint every 30° place between the two angles, going counter-clockwise. */
function paintTravel(slots: (number | null)[], fromDeg: number, toDeg: number, tempC: number): void {
  const span = mod360(toDeg - fromDeg);
  const steps = Math.max(1, Math.ceil(span / SLOT_DEG));
  for (let i = 0; i <= steps; i += 1) {
    const at = i === steps ? toDeg : fromDeg + (span * i) / steps;
    slots[slotIndex(at)] = tempC;
  }
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
  for (const sample of history) {
    if (!Number.isFinite(sample.section0C)) continue;
    if (prevT != null && sample.timeS + 0.5 < prevT) {
      slots.fill(null);
      angle = 0;
      prevT = null;
    }
    const dt = prevT == null ? 0 : sample.timeS - prevT;
    if (dt > 1e-6) {
      const next = angle + 360 * Math.max(0, sample.rps) * dt;
      paintTravel(slots, angle, next, sample.section0C);
      angle = mod360(next);
    } else {
      slots[slotIndex(angle)] = sample.section0C;
    }
    prevT = sample.timeS;
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

function DiskView({
  columns,
  innerFrac,
  angleRef,
  svgRef,
  slotC,
  fuelArcFrac,
  shield1ArcFrac,
  tpvArcFrac,
  shield2ArcFrac,
}: {
  columns: number;
  innerFrac: number;
  /** Live rotation, degrees. The animation writes this; render must not snap it back to 0. */
  angleRef: React.MutableRefObject<number>;
  svgRef: React.RefObject<SVGSVGElement | null>;
  /** Temperature last left by section 0 in each fixed 30° place. */
  slotC: (number | null)[];
  fuelArcFrac: number;
  shield1ArcFrac: number;
  tpvArcFrac: number;
  shield2ArcFrac: number;
}) {
  const n = Math.min(3, Math.max(1, Math.round(columns) || 1));
  const known = slotC.filter((value): value is number => value != null);
  const lo = known.length ? Math.min(...known) : 0;
  const hi = known.length ? Math.max(...known) : 1;
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
  // SVG rotate() is clockwise on screen. Our angles grow counter-clockwise (y up).
  // Re-apply after every render so a temperature update does not snap the disk back.
  const bindRotor = (node: SVGGElement | null) => {
    if (!node) return;
    node.setAttribute("transform", `rotate(${(-angleRef.current).toFixed(2)})`);
  };

  return (
    <svg ref={svgRef} viewBox={`${-width / 2} -1.55 ${width} 3.15`} role="img" aria-label="Disk colored by where section 0 last was, turning with the set speed">
      {Array.from({ length: n }, (_, disk) => {
        const cx = (disk - (n - 1) / 2) * pitch;
        return (
          <g key={disk} transform={`translate(${cx} 0)`}>
            {stator.map((arc) =>
              arc.a1 - arc.a0 > 0.5 ? (
                <path key={arc.name + arc.a0} d={arcPath(arc.a0, arc.a1, 1.08, 1.34)} fill={arc.fill} />
              ) : null,
            )}
            {Array.from({ length: SLOT_COUNT }, (_, index) => {
              const a0 = index * SLOT_DEG + fuelOnTop;
              const temp = slotC[index];
              return (
                <path
                  key={index}
                  d={arcPath(a0, a0 + SLOT_DEG, innerFrac, 1)}
                  fill={temp == null ? "#cbd5e1" : sectionColor(temp, lo, hi)}
                  stroke="white"
                  strokeWidth={0.012}
                />
              );
            })}
            <g data-rotor="" ref={bindRotor}>
              {Array.from({ length: SLOT_COUNT }, (_, index) => {
                const rad = ((fuelOnTop + index * SLOT_DEG) * Math.PI) / 180;
                const cos = Math.cos(rad);
                const sin = -Math.sin(rad);
                return (
                  <line
                    key={index}
                    x1={innerFrac * cos}
                    y1={innerFrac * sin}
                    x2={cos}
                    y2={sin}
                    stroke="rgba(15, 23, 42, 0.45)"
                    strokeWidth={0.012}
                  />
                );
              })}
              <path
                d={arcPath(fuelOnTop, fuelOnTop + SLOT_DEG, innerFrac, 1)}
                fill="none"
                stroke="#0f172a"
                strokeWidth={0.035}
              />
            </g>
            <circle r={innerFrac * 0.72} fill="#f8fafc" stroke="#94a3b8" strokeWidth={0.02} />
          </g>
        );
      })}
    </svg>
  );
}

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
  const paintFromRef = useRef(0);
  const lastTempRef = useRef<number | null>(null);
  const slotsRef = useRef<(number | null)[]>(emptySlots());
  const scaleRef = useRef(scale);
  scaleRef.current = scale;
  const liveRef = useRef(live);
  liveRef.current = live;
  const rpsNow = Number(diskRps);
  const rpsRef = useRef(0);
  rpsRef.current = Number.isFinite(rpsNow) && rpsNow >= 0 ? rpsNow : 0;

  const publishSlots = (next: (number | null)[]) => {
    slotsRef.current = next;
    setSlotC(next);
  };

  const resetDisk = () => {
    angleRef.current = 0;
    paintFromRef.current = 0;
    lastTempRef.current = null;
    publishSlots(emptySlots());
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
          if (!liveRef.current) {
            angleRef.current = built.angle;
            paintFromRef.current = built.angle;
          }
          lastTempRef.current = data.history[data.history.length - 1].section0C;
          publishSlots(built.slots);
        }
      } else if (data.type === "sample") {
        setSample(data.sample);
        if (Number.isFinite(data.sample.section0C)) {
          lastTempRef.current = data.sample.section0C;
          const index = slotIndex(angleRef.current);
          if (slotsRef.current[index] !== data.sample.section0C) {
            const next = slotsRef.current.slice();
            next[index] = data.sample.section0C;
            publishSlots(next);
          }
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
        const from = angleRef.current;
        const to = mod360(from + 360 * rpsRef.current * scaleRef.current * dt);
        angleRef.current = to;
        const temp = lastTempRef.current;
        if (temp != null && mod360(to - paintFromRef.current) >= 0.4) {
          const next = slotsRef.current.slice();
          paintTravel(next, paintFromRef.current, to, temp);
          paintFromRef.current = to;
          if (next.some((value, index) => value !== slotsRef.current[index])) publishSlots(next);
        }
      }
      const transform = `rotate(${(-angleRef.current).toFixed(2)})`;
      svgRef.current?.querySelectorAll("[data-rotor]").forEach((node) => {
        node.setAttribute("transform", transform);
      });
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
        The disk turns steadily in the browser from the speed above. Each fixed 30° place keeps the temperature
        section 0 had the last time the outline passed it, and that color stays until section 0 comes around again.
        The ring
        outside the disk is the fixed fuel, shield, and TPV arcs.
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
        {lo != null && hi != null ? ` · places ${lo.toFixed(1)}–${hi.toFixed(1)} °C` : ""}
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
        slotC={slotC}
        fuelArcFrac={fuelArcFrac}
        shield1ArcFrac={shield1ArcFrac}
        tpvArcFrac={tpvArcFrac}
        shield2ArcFrac={shield2ArcFrac}
      />
      <div className="d-flex gap-3 small text-secondary mb-2">
        <span>Cooler places are blue, hotter places are red. Gray has not been visited yet.</span>
        <span>The dark outline is section 0. Outer ring: fuel, shield, TPV, shield.</span>
      </div>
      <LiveChart samples={samples} />
    </div>
  );
};

export default LiveReactorPanel;
