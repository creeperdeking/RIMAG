import React, { useMemo, useState } from "react";
import { Alert, Button, Col, Row } from "react-bootstrap";
import type { Setup } from "../configurations";
import type { NumericKey } from "../configurations";

type FuelTrace = {
  timeS: number[];
  fuelTempK: number[];
  fuelTempC: number[];
  stopTimeS: number;
  fuelTempStartC: number;
  reusedBinary: boolean;
  message: string;
};

type Props = {
  setup: Setup;
  /** Solid Disk layer thickness from Layer designer (cm, excludes Void). */
  diskThicknessCm: number;
  renderSlider: (key: NumericKey, label: string, format: (value: number) => string) => React.ReactNode;
};

const fixed =
  (digits: number, suffix = "") =>
  (value: number): string =>
    `${value.toFixed(digits)}${suffix}`;

function FuelTempChart({ trace }: { trace: FuelTrace }) {
  const width = 640;
  const height = 280;
  const pad = { left: 52, right: 16, top: 16, bottom: 36 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const { path, yMin, yMax, xMax } = useMemo(() => {
    const xs = trace.timeS;
    const ys = trace.fuelTempC;
    const xMaxLocal = Math.max(...xs, 1);
    let yMinLocal = Math.min(...ys);
    let yMaxLocal = Math.max(...ys);
    if (!(yMaxLocal > yMinLocal)) {
      yMinLocal -= 1;
      yMaxLocal += 1;
    }
    const padY = 0.05 * (yMaxLocal - yMinLocal);
    yMinLocal -= padY;
    yMaxLocal += padY;
    const points = xs.map((t, i) => {
      const x = pad.left + (t / xMaxLocal) * plotW;
      const y = pad.top + (1 - (ys[i] - yMinLocal) / (yMaxLocal - yMinLocal)) * plotH;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    return {
      path: `M ${points.join(" L ")}`,
      yMin: yMinLocal,
      yMax: yMaxLocal,
      xMax: xMaxLocal,
    };
  }, [trace, plotW, plotH, pad.left, pad.top]);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => yMin + f * (yMax - yMin));
  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xMax);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="rimael-fuel-chart" role="img" aria-label="Fuel temperature vs time">
      <rect x={pad.left} y={pad.top} width={plotW} height={plotH} fill="#fafbfc" stroke="#dee2e6" />
      {yTicks.map((value) => {
        const y = pad.top + (1 - (value - yMin) / (yMax - yMin)) * plotH;
        return (
          <g key={`y-${value}`}>
            <line x1={pad.left} x2={pad.left + plotW} y1={y} y2={y} stroke="#e9ecef" />
            <text x={pad.left - 8} y={y + 4} textAnchor="end" className="rimael-chart-label">
              {value.toFixed(0)}
            </text>
          </g>
        );
      })}
      {xTicks.map((value) => {
        const x = pad.left + (value / xMax) * plotW;
        return (
          <g key={`x-${value}`}>
            <line x1={x} x2={x} y1={pad.top} y2={pad.top + plotH} stroke="#e9ecef" />
            <text x={x} y={height - 12} textAnchor="middle" className="rimael-chart-label">
              {value.toFixed(0)}
            </text>
          </g>
        );
      })}
      <path d={path} fill="none" stroke="#c2410c" strokeWidth={2} />
      <text x={width / 2} y={height - 2} textAnchor="middle" className="rimael-chart-axis">
        time (s)
      </text>
      <text
        x={14}
        y={height / 2}
        textAnchor="middle"
        className="rimael-chart-axis"
        transform={`rotate(-90 14 ${height / 2})`}
      >
        FuelPlate.T (°C)
      </text>
    </svg>
  );
}

const ThermodynamicTab: React.FC<Props> = ({ setup, diskThicknessCm, renderSlider }) => {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trace, setTrace] = useState<FuelTrace | null>(null);

  const onRunRim = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch("/api/rimael/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fuel_temp_c: setup.fuel_temp_c,
          fuel_emissivity: setup.fuel_emissivity,
          disk_emissivity: setup.disk_emissivity,
          disk_thickness_cm: diskThicknessCm,
        }),
      });
      const data = (await response.json()) as FuelTrace & { error?: string };
      if (!response.ok) {
        setError(data.error || `Run failed (${response.status})`);
        return;
      }
      setTrace(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Row className="g-4">
      <Col lg={5}>
        <div className="border rounded p-3 bg-white h-100">
          <h2 className="h6 mb-3">TPV and fuel temperature</h2>
          <p className="small text-secondary mb-3">
            Electrical TPV cell loading and conversion efficiency, plus the hot-side fuel temperature used for radiative
            heat balance in RIMAG core characteristics.
          </p>
          {renderSlider("tpv_density", "TPV power density (W/cm²)", fixed(2))}
          {renderSlider("tpv_eff_pct", "TPV efficiency", fixed(0, "%"))}
          {renderSlider("fuel_temp_c", "Fuel temperature (°C)", fixed(0))}
          {renderSlider("fuel_emissivity", "Fuel emissivity", fixed(2))}
          {renderSlider("disk_emissivity", "Disk emissivity", fixed(2))}
          <div className="small text-secondary mt-2">
            Fuel temperature sets initial <code>FuelPlate.T</code> for Run RIM ({Math.round(setup.fuel_temp_c + 273.15)} K)
            and OpenMC. Emissivities set radiative exchange via{" "}
            <code>Gr = A / (1/ε₁ + 1/ε₂ − 1)</code>. Solid disk thickness from Layer designer:{" "}
            <strong>{diskThicknessCm.toFixed(2)} cm</strong> (scales section heat capacity ∝ t and through-thickness G ∝
            1/t; Void gaps are excluded).
          </div>
        </div>
      </Col>
      <Col lg={7}>
        <div className="border rounded p-3 bg-white h-100">
          <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
            <h2 className="h6 mb-0">RIMAEL Modelica — fuel temperature</h2>
            <Button size="sm" variant="primary" disabled={running} onClick={() => void onRunRim()}>
              {running ? "Running…" : "Run RIM"}
            </Button>
          </div>
          <p className="small text-secondary mb-3">
            Runs <code>RIMAEL.Reactor</code> via local OpenModelica, starting from the fuel temperature slider. First
            compile can take a couple of minutes; later runs reuse the binary (~10–20 s). Plots <code>FuelPlate.T</code>{" "}
            over 0–700 s.
          </p>
          {error && (
            <Alert variant="danger" className="py-2 px-3 small">
              {error}
            </Alert>
          )}
          {trace && (
            <>
              <div className="small text-secondary mb-2">
                {trace.message}
                {" · "}
                {trace.timeS.length} samples · final{" "}
                {trace.fuelTempC[trace.fuelTempC.length - 1]?.toFixed(1)} °C at {trace.stopTimeS.toFixed(0)} s
              </div>
              <FuelTempChart trace={trace} />
            </>
          )}
          {!trace && !running && !error && (
            <div className="small text-secondary">Click Run RIM to simulate and plot fuel temperature.</div>
          )}
          {running && <div className="small text-secondary">OpenModelica is simulating…</div>}
        </div>
      </Col>
    </Row>
  );
};

export default ThermodynamicTab;
