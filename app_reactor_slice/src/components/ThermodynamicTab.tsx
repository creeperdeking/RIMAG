import React, { useMemo, useState } from "react";
import { Alert, Button, Col, Row } from "react-bootstrap";
import type { NumericKey, Setup } from "../configurations";
import {
  GRAPHITE_CP_J_KG_K,
  GRAPHITE_DENSITY_KG_M3,
  GRAPHITE_K_W_M_K,
  RIMAEL_N_SECTIONS,
  TPV_CELL_TEMP_K,
  diskCircuitArcsFromAngles,
  diskSectionThermal,
  graphiteLumpedThermal,
} from "../../shared/diskThermal";
import {
  AIRBRIDGE_CELLS,
  airbridgeCurves,
  interpolateTpvValue,
  type AirbridgeOperatingPoint,
  type TpvPoint,
} from "../data/tpvEmpiricalLimits";

type FuelTrace = {
  timeS: number[];
  fuelTempK: number[];
  fuelTempC: number[];
  stopTimeS: number;
  fuelTempStartC: number;
  fuelArcFrac?: number;
  tpvArcFrac?: number;
  fuelHeatingPowerW?: number;
  reusedBinary: boolean;
  message: string;
};

type Props = {
  setup: Setup;
  /** Solid Disk layer thickness from Layer designer (cm, excludes Void). */
  diskThicknessCm: number;
  /** Helium gap on the fuel side of the disk (leading Void sheets, cm). */
  fuelGapCm: number;
  /** Helium gap between the disk and the vacuum shell (trailing Void sheets, cm). */
  tpvGapCm: number;
  /** One-disk annulus face area from Geometry (m²). */
  diskAreaM2: number;
  /** Solid fuel-stack thickness from Layer designer (cm, excludes Void). */
  fuelThicknessCm: number;
  /** Fuel-sector face area from Geometry (m²). */
  fuelAreaM2: number;
  /** Fuel / TPV zone angles from Geometry (rad). */
  fuelAngleRad: number;
  tpvAngleRad: number;
  /** TPV (opposite) face area of one disk from Geometry (m²). */
  tpvAreaM2: number;
  /** Shell temperature, power, efficiency, and reflectance at the fixed fuel temperature. */
  operatingPoint: AirbridgeOperatingPoint;
  renderSlider: (key: NumericKey, label: string, format: (value: number) => string) => React.ReactNode;
  /** Apply a numeric setup field (the air-bridge cell choice). */
  onNumericChange?: (key: NumericKey, value: number) => void;
};

function polylinePath(points: TpvPoint[], xOf: (t: number) => number, yOf: (v: number) => number): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(p.tempC).toFixed(1)} ${yOf(p.value).toFixed(1)}`).join(" ");
}

function TpvModelChart({
  title,
  yLabel,
  points,
  color,
  emitterTempC,
  yMin,
  yMax,
  logY,
  valueFormat,
}: {
  title: string;
  yLabel: string;
  points: TpvPoint[];
  color: string;
  /** Vacuum-shell temperature the cells see (°C). */
  emitterTempC: number;
  yMin: number;
  yMax: number;
  logY?: boolean;
  valueFormat: (v: number) => string;
}) {
  const width = 520;
  const height = 240;
  const pad = { left: 52, right: 16, top: 28, bottom: 36 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const tMin = 600;
  const tMax = 1600;
  const xOf = (t: number) => pad.left + ((t - tMin) / (tMax - tMin)) * plotW;
  const yOf = (v: number) => {
    if (logY) {
      const lo = Math.log10(yMin);
      const hi = Math.log10(yMax);
      const clamped = Math.max(yMin, Math.min(yMax, v));
      return pad.top + (1 - (Math.log10(clamped) - lo) / (hi - lo)) * plotH;
    }
    return pad.top + (1 - (v - yMin) / (yMax - yMin)) * plotH;
  };

  const modelAtEmitter = interpolateTpvValue(points, emitterTempC);
  const opInRange = emitterTempC >= tMin && emitterTempC <= tMax;
  const yTicks = logY
    ? [0.001, 0.01, 0.1, 1, 10].filter((v) => v >= yMin && v <= yMax)
    : Array.from({ length: 6 }, (_, i) => yMin + (i / 5) * (yMax - yMin));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="tpv-eff-chart" role="img" aria-label={title}>
      <text x={pad.left} y={16} className="rimael-chart-axis">
        {title}
      </text>
      <rect x={pad.left} y={pad.top} width={plotW} height={plotH} fill="#fff" stroke="#dee2e6" />
      {yTicks.map((v) => {
        const y = yOf(v);
        return (
          <g key={`y-${v}`}>
            <line x1={pad.left} x2={pad.left + plotW} y1={y} y2={y} stroke="#e9ecef" />
            <text x={pad.left - 8} y={y + 4} textAnchor="end" className="rimael-chart-label">
              {logY ? String(v) : valueFormat(v)}
            </text>
          </g>
        );
      })}
      {[600, 800, 1000, 1200, 1400, 1600].map((t) => {
        const x = xOf(t);
        return (
          <g key={`t-${t}`}>
            <line x1={x} x2={x} y1={pad.top} y2={pad.top + plotH} stroke="#e9ecef" />
            <text x={x} y={height - 10} textAnchor="middle" className="rimael-chart-label">
              {t}
            </text>
          </g>
        );
      })}
      <path
        d={polylinePath(points, xOf, yOf)}
        fill="none"
        stroke={color}
        strokeWidth={2.25}
      />
      {opInRange && (
        <g>
          <line
            x1={xOf(emitterTempC)}
            x2={xOf(emitterTempC)}
            y1={pad.top}
            y2={pad.top + plotH}
            stroke="#64748b"
            strokeDasharray="3 3"
          />
          {modelAtEmitter != null && (
            <circle
              cx={xOf(emitterTempC)}
              cy={yOf(Math.max(yMin, Math.min(yMax, modelAtEmitter)))}
              r={5}
              fill={color}
              stroke="#fff"
              strokeWidth={1.5}
            />
          )}
        </g>
      )}
      <text
        x={14}
        y={height / 2}
        textAnchor="middle"
        className="rimael-chart-axis"
        transform={`rotate(-90 14 ${height / 2})`}
      >
        {yLabel}
      </text>
    </svg>
  );
}

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

const ThermodynamicTab: React.FC<Props> = ({
  setup,
  diskThicknessCm,
  fuelGapCm,
  tpvGapCm,
  diskAreaM2,
  fuelThicknessCm,
  fuelAreaM2,
  fuelAngleRad,
  tpvAngleRad,
  tpvAreaM2,
  operatingPoint,
  renderSlider,
  onNumericChange,
}) => {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trace, setTrace] = useState<FuelTrace | null>(null);
  const cellIndex = setup.tpv_airbridge_cell;
  const viewFactor = setup.tpv_view_factor;

  const curves = useMemo(() => airbridgeCurves(cellIndex, viewFactor), [cellIndex, viewFactor]);
  const effPoints = curves.efficiency;
  const powerPoints = curves.power;
  const egColor = curves.color;

  /** Cells see the vacuum shell, so the shell temperature is the TPV emitter. */
  const emitterTempC = operatingPoint.shellTempC;
  const fuelHeatingPowerW = operatingPoint.heatW;

  const diskThermal = useMemo(
    () => diskSectionThermal(diskAreaM2, diskThicknessCm, RIMAEL_N_SECTIONS),
    [diskAreaM2, diskThicknessCm],
  );
  const fuelThermal = useMemo(
    () => graphiteLumpedThermal(fuelAreaM2, fuelThicknessCm),
    [fuelAreaM2, fuelThicknessCm],
  );
  const circuitArcs = useMemo(
    () => diskCircuitArcsFromAngles(fuelAngleRad, tpvAngleRad),
    [fuelAngleRad, tpvAngleRad],
  );
  const onRunRim = async () => {
    setRunning(true);
    setError(null);
    try {
      if (!(fuelHeatingPowerW > 0)) {
        setError("TPV area is zero — cannot set Modelica fuel heating power P0.");
        return;
      }
      const response = await fetch("/api/rimael/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fuel_temp_c: setup.fuel_temp_c,
          fuel_emissivity: setup.fuel_emissivity,
          disk_emissivity: setup.disk_emissivity,
          ...(operatingPoint.cellReflectance != null
            ? { cell_reflectance: operatingPoint.cellReflectance }
            : {}),
          disk_thickness_cm: diskThicknessCm,
          disk_area_m2: diskAreaM2,
          fuel_thickness_cm: fuelThicknessCm,
          fuel_area_m2: fuelAreaM2,
          fuel_arc_frac: circuitArcs.fuelArcFrac,
          tpv_arc_frac: circuitArcs.tpvArcFrac,
          shield1_arc_frac: circuitArcs.shield1ArcFrac,
          shield2_arc_frac: circuitArcs.shield2ArcFrac,
          fuel_heating_power_w: fuelHeatingPowerW,
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
            Fuel temperature is fixed. Power density, efficiency, and cell reflectance are what the selected cell
            produces when the shell sits at the temperature that carries that heat.
          </p>
          {renderSlider("fuel_temp_c", "Fuel temperature (°C)", fixed(0))}
          {renderSlider("fuel_emissivity", "Fuel emissivity", fixed(2))}
          {renderSlider("disk_emissivity", "Disk emissivity", fixed(2))}
          {renderSlider("shell_emissivity", "Vacuum shell emissivity", fixed(2))}
          <div className="small mb-2">
            Power density <strong>{operatingPoint.powerWPerCm2.toFixed(2)} W/cm²</strong>
            <span className="text-secondary"> · efficiency </span>
            <strong>{operatingPoint.efficiencyPct.toFixed(1)}%</strong>
          </div>
          <div className="small mb-2">
            Cell reflectance{" "}
            {operatingPoint.cellReflectance != null && operatingPoint.cellEmissivity != null ? (
              <strong>
                {(100 * operatingPoint.cellReflectance).toFixed(1)}%
                <span className="text-secondary"> (ε={operatingPoint.cellEmissivity.toFixed(3)})</span>
              </strong>
            ) : (
              <strong>no solution</strong>
            )}
          </div>
          {operatingPoint.cellReflectance == null && (
            <Alert variant="warning" className="py-2 px-3 small">
              The shell cannot emit the heat this cell absorbs. Raise the shell emissivity or lower the view factor.
            </Alert>
          )}

          <div className="mt-3 pt-3 border-top">
            <h3 className="h6 mb-2">Air-bridge TPV cells (Roy-Layinde et al.)</h3>
            <div className="btn-group btn-group-sm mb-3" role="group" aria-label="Air-bridge band gap">
              {AIRBRIDGE_CELLS.map((cell) => (
                <Button
                  key={cell.id}
                  size="sm"
                  variant={cellIndex === cell.index ? "primary" : "outline-primary"}
                  onClick={() => onNumericChange?.("tpv_airbridge_cell", cell.index)}
                >
                  {cell.label}
                </Button>
              ))}
            </div>
            {renderSlider("tpv_view_factor", "View factor", fixed(2))}
            <p className="small text-secondary mb-2">
              Each curve is that cell’s measured reflectance and its two-diode fit. The view factor scales the
              current and the absorbed heat together. The deposited scripts use 0.35, 0.3214, and 0.27. The 0.90 and
              1.10 files integrate at 0.88 and 1.08 eV. The mark is the vacuum-shell temperature the cells see.
            </p>
            <div className="small mb-2">
              Fuel <strong>{setup.fuel_temp_c.toFixed(0)} °C</strong>
              <span className="text-secondary">
                {" "}
                supplies {(operatingPoint.heatW / 1000).toFixed(1)} kW. The same heat crosses the disk and is what the
                cell absorbs.
              </span>
            </div>
            <div className="small mb-2">
              Disk <strong>{operatingPoint.diskTempC.toFixed(0)} °C</strong>
              <span className="text-secondary">
                {" "}
                ({(operatingPoint.diskTempC - emitterTempC).toFixed(0)} °C above the shell,{" "}
                {Math.round(100 * operatingPoint.conductionShareDisk)}% of the heat by conduction across{" "}
                {tpvGapCm.toFixed(2)} cm of helium).
              </span>
            </div>
            <div className="small mb-2">
              Shell <strong>{emitterTempC.toFixed(0)} °C</strong>
              <span className="text-secondary">
                {" "}
                radiates in vacuum onto the cells at {(TPV_CELL_TEMP_K - 273.15).toFixed(0)} °C. Across the{" "}
                {fuelGapCm.toFixed(2)} cm fuel gap, conduction carries{" "}
                {Math.round(100 * operatingPoint.conductionShareFuel)}% of the heat.
              </span>
            </div>
            <TpvModelChart
              title={`Efficiency — ${curves.label} · F ${viewFactor.toFixed(2)}`}
              yLabel="η (%)"
              points={effPoints}
              color={egColor}
              emitterTempC={emitterTempC}
              yMin={0}
              yMax={50}
              valueFormat={(v) => v.toFixed(0)}
            />
            <TpvModelChart
              title={`Power density — ${curves.label} · F ${viewFactor.toFixed(2)}`}
              yLabel="P (W/cm²)"
              points={powerPoints}
              color={egColor}
              emitterTempC={emitterTempC}
              yMin={0.001}
              yMax={10}
              logY
              valueFormat={(v) => v.toFixed(2)}
            />
          </div>

          <div className="small text-secondary mt-2">
            Fuel temperature is the OpenMC fuel temperature and the initial <code>FuelPlate.T</code> of Run Sim (
            {Math.round(setup.fuel_temp_c + 273.15)} K). Helium gaps are the Void
            sheets on the disk stack. Across helium,{" "}
            <code>Q = σ Gr (T_hot⁴ − T_cold⁴) + k_He A ΔT / d</code>. From the shell to the cells the gap is vacuum,
            so only radiation remains, with <code>ε_cell = 1 − R</code>.
          </div>
          <div className="small text-secondary mt-2">
            Graphite ρ={(GRAPHITE_DENSITY_KG_M3 / 1000).toFixed(2)} g/cm³, cₚ={GRAPHITE_CP_J_KG_K} J/(kg·K), k=
            {GRAPHITE_K_W_M_K} W/(m·K). Void gaps excluded from thicknesses.
            <br />
            Fuel plate: area <strong>{fuelAreaM2.toFixed(3)} m²</strong>, stack{" "}
            <strong>{fuelThicknessCm.toFixed(2)} cm</strong> →{" "}
            <code>FuelPlate.C = ρ·A·t·cₚ = {fuelThermal.heatCapacity.toFixed(0)} J/K</code> (m=
            {fuelThermal.massKg.toFixed(1)} kg).
            <br />
            Disk: area <strong>{diskAreaM2.toFixed(3)} m²</strong>, solid{" "}
            <strong>{diskThicknessCm.toFixed(2)} cm</strong>, {RIMAEL_N_SECTIONS} sectors →{" "}
            <code>
              C_sec = ρ·A·t·cₚ / {RIMAEL_N_SECTIONS} = {diskThermal.heatCapacitySection.toFixed(0)} J/K
            </code>
            {" · "}
            <code>G = {diskThermal.throughThicknessG.toFixed(0)} W/K</code>.
            <br />
            Circuit arcs from Geometry: fuel{" "}
            <strong>{(100 * circuitArcs.fuelArcFrac).toFixed(1)}%</strong>, TPV{" "}
            <strong>{(100 * circuitArcs.tpvArcFrac).toFixed(1)}%</strong>, each shield{" "}
            <strong>{(100 * circuitArcs.shield1ArcFrac).toFixed(1)}%</strong> → Modelica{" "}
            <code>fuel_arc_frac</code> / <code>tpv_arc_frac</code> / <code>shield*_arc_frac</code>.
            <br />
            Fuel heating (one disk × one slice):{" "}
            <code>
              P0 = 2·ρ·10·A_tpv / η = {(fuelHeatingPowerW / 1000).toFixed(1)} kW
            </code>{" "}
            (A_tpv={tpvAreaM2.toFixed(3)} m²).
          </div>
        </div>
      </Col>
      <Col lg={7}>
        <div className="border rounded p-3 bg-white h-100">
          <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
            <h2 className="h6 mb-0">RIMAEL Modelica — fuel temperature</h2>
            <Button size="sm" variant="primary" disabled={running} onClick={() => void onRunRim()}>
              {running ? "Running…" : "Run Sim"}
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
            <div className="small text-secondary">Click Run Sim to simulate and plot fuel temperature.</div>
          )}
          {running && <div className="small text-secondary">OpenModelica is simulating…</div>}
        </div>
      </Col>
    </Row>
  );
};

export default ThermodynamicTab;
