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
  sectionC: number[];
};

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
  angleDeg,
  sectionC,
  fuelArcFrac,
  shield1ArcFrac,
  tpvArcFrac,
  shield2ArcFrac,
}: {
  columns: number;
  innerFrac: number;
  angleDeg: number;
  sectionC: number[] | null;
  fuelArcFrac: number;
  shield1ArcFrac: number;
  tpvArcFrac: number;
  shield2ArcFrac: number;
}) {
  const n = Math.min(3, Math.max(1, Math.round(columns) || 1));
  const temps = sectionC && sectionC.length === 12 ? sectionC : null;
  const lo = temps ? Math.min(...temps) : 0;
  const hi = temps ? Math.max(...temps) : 1;
  const pitch = 2.7;
  const width = n * pitch + 0.4;
  const fuelEnd = fuelArcFrac * 360;
  const shield1End = fuelEnd + shield1ArcFrac * 360;
  const tpvEnd = shield1End + tpvArcFrac * 360;
  const shield2End = tpvEnd + shield2ArcFrac * 360;
  const stator = [
    { a0: 0, a1: fuelEnd, fill: "rgba(217, 119, 6, 0.55)", name: "Fuel" },
    { a0: fuelEnd, a1: shield1End, fill: "rgba(100, 116, 139, 0.45)", name: "Shield" },
    { a0: shield1End, a1: tpvEnd, fill: "rgba(37, 99, 235, 0.4)", name: "TPV" },
    { a0: tpvEnd, a1: shield2End, fill: "rgba(71, 85, 105, 0.4)", name: "Shield" },
  ];

  return (
    <svg viewBox={`${-width / 2} -1.55 ${width} 3.15`} role="img" aria-label="Rotating disk sections colored by temperature">
      {Array.from({ length: n }, (_, disk) => {
        const cx = (disk - (n - 1) / 2) * pitch;
        return (
          <g key={disk} transform={`translate(${cx} 0)`}>
            {stator.map((arc) =>
              arc.a1 - arc.a0 > 0.5 ? (
                <path key={arc.name + arc.a0} d={arcPath(arc.a0, arc.a1, 1.08, 1.34)} fill={arc.fill} />
              ) : null,
            )}
            {Array.from({ length: 12 }, (_, index) => {
              const a0 = index * 30 + angleDeg;
              const temp = temps ? temps[index] : null;
              return (
                <path
                  key={index}
                  d={arcPath(a0, a0 + 30, innerFrac, 1)}
                  fill={temp == null ? "#cbd5e1" : sectionColor(temp, lo, hi)}
                  stroke="white"
                  strokeWidth={0.015}
                />
              );
            })}
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
  const [angle, setAngle] = useState(0);
  const motion = useRef({ wall: 0, angle: 0, rps: 0, scale: 1 });
  const liveRef = useRef(false);
  liveRef.current = live;
  const bodyRef = useRef(geometryBody);
  bodyRef.current = geometryBody;

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
        }
      } else if (data.type === "sample") {
        setSample(data.sample);
        setSamples((prev) => {
          const next = prev.length > 2000 ? prev.slice(-1500) : prev.slice();
          next.push(data.sample);
          return next;
        });
      } else if (data.type === "control") {
        motion.current.rps = data.rps;
        motion.current.scale = data.scale;
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
    const tick = (now: number) => {
      const state = motion.current;
      if (state.wall > 0 && liveRef.current) {
        const dt = Math.min(0.1, (now - state.wall) / 1000);
        state.angle = (state.angle + dt * state.scale * state.rps * 360) % 360;
        setAngle(state.angle);
      }
      state.wall = now;
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!sample) return;
    motion.current.rps = sample.rps;
    motion.current.scale = scale;
  }, [sample, scale]);

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
  const sectionC = sample?.sectionC ?? null;
  const lo = sectionC ? Math.min(...sectionC) : null;
  const hi = sectionC ? Math.max(...sectionC) : null;

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
    motion.current.rps = rps;
    motion.current.scale = scale;
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
        power and disk speed you set here, writes the fuel, shield, shell, and twelve section temperatures back, and
        waits so model time stays on the selected wall-clock scale. The disk drawing turns at that speed. Each 30°
        section is tinted from its own temperature. The ring outside the disk is the fixed fuel, shield, and TPV arcs.
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
        {lo != null && hi != null ? ` · sections ${lo.toFixed(1)}–${hi.toFixed(1)} °C` : ""}
      </div>
      {error && (
        <Alert variant="danger" className="py-2 px-3 small">
          {error}
        </Alert>
      )}
      <DiskView
        columns={columns}
        innerFrac={innerFrac}
        angleDeg={angle}
        sectionC={sectionC}
        fuelArcFrac={fuelArcFrac}
        shield1ArcFrac={shield1ArcFrac}
        tpvArcFrac={tpvArcFrac}
        shield2ArcFrac={shield2ArcFrac}
      />
      <div className="d-flex gap-3 small text-secondary mb-2">
        <span>Cooler sections are blue, hotter sections are red.</span>
        <span>Outer ring: fuel, shield, TPV, shield.</span>
      </div>
      <LiveChart samples={samples} />
    </div>
  );
};

export default LiveReactorPanel;
