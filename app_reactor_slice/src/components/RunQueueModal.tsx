import React, { useEffect, useState } from "react";
import { Alert, Button, Form, Modal } from "react-bootstrap";
import {
  NSM_MATERIALS,
  PARTICLE_TYPES,
  RUN_MODES,
  WEIGHT_WINDOWS_RUN,
  type NsmMaterial,
  type ParticleType,
  type RunMode,
  type WeightWindowsRun,
} from "../constants";
import {
  normalizeSetup,
  normalizeSimulation,
  type Setup,
  type SimulationParams,
} from "../configurations";
import { FieldLabel, InfoTip } from "./SimulationFieldLabel";

export type QueueModalMode = "append" | "edit" | "view";

/** Local clock time a past run finished, from the stored ISO timestamp. */
export function formatEndedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const pad = (n: number) => String(n).padStart(2, "0");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${date.getDate()} ${months[date.getMonth()]} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

type QueueResult = {
  summary?: string | null;
  keff?: number | null;
  keffUncertainty?: number | null;
  ingaasReached?: number | null;
  ingaasVoxels?: number | null;
  ingaasReachFraction?: number | null;
  ingaasEnergyFraction?: number | null;
  gammaKGy?: number | null;
  gammaCi95Pct?: number | null;
  gammaYears?: number | null;
  dddMeVPerG?: number | null;
  dddCi95Pct?: number | null;
  dddYears?: number | null;
  pmaxRemaining?: number | null;
  pmaxCi95Pct?: number | null;
  pmaxYears?: number | null;
  pmaxFluenceM2?: number | null;
  pmaxOutsideRange?: boolean | null;
  pmaxFastRemaining?: number | null;
  pmaxTruncatedRemaining?: number | null;
  depletionYears?: number | null;
  depletionDays?: number | null;
  depletionBurnup?: number | null;
  depletionBelowOne?: boolean | null;
};

type Props = {
  show: boolean;
  mode: QueueModalMode;
  title: string;
  setup: Setup;
  /** Seed form from the live calculator (append) or from a queue item. */
  initialSimulation: SimulationParams & { weight_windows?: WeightWindowsRun | string };
  /** Thermodynamics-tab stack thermal power [MW], shown read-only. */
  defaultThermalPowerMw?: number | null;
  /** True when runs/default already has weight_windows.h5 (needed for refine). */
  wwPresent?: boolean;
  result?: QueueResult | null;
  exitCode?: number | null;
  statusLabel?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  saving?: boolean;
  error?: string | null;
  onHide: () => void;
  onSubmit?: (simulation: SimulationParams & { weight_windows: WeightWindowsRun }) => void;
};

const WW_OPTION_LABELS: Record<WeightWindowsRun, string> = {
  no: "no (analog)",
  use: "use (apply existing windows)",
  generate: "generate (legacy)",
  seed: "seed (MAGIC after analog keff)",
  refine: "refine (one MAGIC pass)",
  autorefine: "autorefine (until InGaAs ≥ 80%)",
};

function applyWwPreset(
  draft: SimulationParams & { weight_windows: WeightWindowsRun },
  weight_windows: WeightWindowsRun,
): SimulationParams & { weight_windows: WeightWindowsRun } {
  if (weight_windows === "seed") {
    return {
      ...draft,
      weight_windows,
      run_mode: "keff_notallies",
      survival_biasing: true,
    };
  }
  if (weight_windows === "refine" || weight_windows === "autorefine") {
    return {
      ...draft,
      weight_windows,
      run_mode: "keff_notallies",
      survival_biasing: false,
    };
  }
  if (weight_windows === "no" || weight_windows === "use") {
    return {
      ...draft,
      weight_windows,
      run_mode: draft.run_mode === "keff_notallies" ? "keff" : draft.run_mode,
    };
  }
  return { ...draft, weight_windows };
}

function queueSimulationFromRaw(
  raw: SimulationParams & { weight_windows?: WeightWindowsRun | string },
): SimulationParams & { weight_windows: WeightWindowsRun } {
  const base = normalizeSimulation(raw);
  const ww = typeof raw.weight_windows === "string" ? raw.weight_windows : base.weight_windows;
  const weight_windows = (WEIGHT_WINDOWS_RUN as readonly string[]).includes(ww)
    ? (ww as WeightWindowsRun)
    : "no";
  return { ...base, weight_windows };
}

function formatSci(value: number): string {
  const [coef, exp] = value.toExponential(4).split("e");
  const sign = exp.startsWith("-") ? "-" : "+";
  const mag = exp.replace(/^[+-]/, "");
  return `${coef}e${sign}${mag.padStart(2, "0")}`;
}

function formatDoseYears(years: number): string {
  const rounded = Math.round(years);
  if (Math.abs(years - rounded) < 1e-6) return String(rounded);
  return String(Number(years.toPrecision(4)));
}

const RUN_MODE_LABEL: Record<string, string> = {
  slab: "fast slab",
  depletion: "fuel depletion",
  keff_gamma_dose: "InGaAs gamma dose",
  keff_emitter_gamma_source: "emitter gamma (fixed source)",
};

function formatBurnup(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 100) return value.toFixed(1);
  if (Math.abs(value) >= 10) return value.toFixed(2);
  return value.toPrecision(3);
}

function formatDepletionTime(years: number, days: number | null | undefined): string {
  if (years < 0.05 && days != null && Number.isFinite(days)) {
    const rounded = Math.round(days * 10) / 10;
    return `${rounded} days`;
  }
  return `${formatDoseYears(years)} years`;
}

type WwLive = {
  passes: number | null;
  lastPass: string | null;
  updatedAt: string | null;
  spatialCoverage: number | null;
  outerCoverage: number | null;
  reachYCm: number | null;
  meshRMaxCm: number | null;
  ingaasVoxels: number | null;
  ingaasReached: number | null;
  ingaasReachFraction: number | null;
  ingaasEnergyFraction: number | null;
};

function coverageBelongs(updatedAt: string | null, startedAt: string | null): boolean {
  if (!updatedAt || !startedAt) return false;
  const updated = Date.parse(updatedAt);
  const started = Date.parse(startedAt);
  if (!Number.isFinite(updated) || !Number.isFinite(started)) return false;
  return updated >= started - 15_000;
}

function CoverageBar({
  label,
  fraction,
  detail,
  marker,
}: {
  label: string;
  fraction: number;
  detail: string;
  marker?: number;
}) {
  const clamped = Math.min(1, Math.max(0, fraction));
  const width = 280;
  const fill = clamped * width;
  const mark = marker != null ? Math.min(1, Math.max(0, marker)) * width : null;
  return (
    <div className="mb-2">
      <div className="d-flex justify-content-between small">
        <span>{label}</span>
        <span className="font-monospace">{detail}</span>
      </div>
      <svg viewBox={`0 0 ${width} 12`} width="100%" role="img" aria-label={`${label} ${detail}`}>
        <rect x="0" y="1" width={width} height="10" rx="2" fill="#e2e8f0" />
        <rect x="0" y="1" width={fill} height="10" rx="2" fill={clamped >= 0.8 ? "#15803d" : "#0f766e"} />
        {mark != null && <line x1={mark} x2={mark} y1="0" y2="12" stroke="#b45309" strokeWidth="1.5" />}
      </svg>
    </div>
  );
}

function LiveWwCoverage({ startedAt }: { startedAt: string | null }) {
  const [status, setStatus] = useState<WwLive | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const response = await fetch("/api/simulation/weight-windows");
        if (!response.ok || stop) return;
        const data = (await response.json()) as WwLive;
        if (!stop) setStatus(data);
      } catch {
        // keep the last picture
      } finally {
        if (!stop) setLoaded(true);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 10_000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, []);

  const ready = status != null && coverageBelongs(status.updatedAt, startedAt);
  if (!loaded) {
    return <p className="small text-secondary mb-0">Reading the latest weight-window coverage…</p>;
  }
  if (!ready || status.ingaasReachFraction == null) {
    return (
      <p className="small text-secondary mb-0">
        The first pass is still running. Coverage shows here when that pass finishes.
      </p>
    );
  }
  const ingaas = status.ingaasReachFraction;
  const reach =
    status.reachYCm != null && status.meshRMaxCm != null && status.meshRMaxCm > 0
      ? status.reachYCm / status.meshRMaxCm
      : null;
  return (
    <div>
      <div className="small text-secondary mb-2">
        After pass {status.passes ?? "—"}
        {status.updatedAt ? ` · ${status.updatedAt.replace("T", " ").replace("Z", " UTC")}` : ""}
      </div>
      <CoverageBar
        label="InGaAs mesh"
        fraction={ingaas}
        marker={0.8}
        detail={
          status.ingaasReached != null && status.ingaasVoxels != null
            ? `${status.ingaasReached}/${status.ingaasVoxels} · ${(100 * ingaas).toFixed(0)}%`
            : `${(100 * ingaas).toFixed(0)}%`
        }
      />
      <div className="small text-secondary mb-2">The mark is the 80% target.</div>
      {status.ingaasEnergyFraction != null && (
        <CoverageBar
          label="Energy groups in reached cells"
          fraction={status.ingaasEnergyFraction}
          detail={`${(100 * status.ingaasEnergyFraction).toFixed(0)}%`}
        />
      )}
      {status.spatialCoverage != null && (
        <CoverageBar
          label="Mesh cells with a window"
          fraction={status.spatialCoverage}
          detail={`${(100 * status.spatialCoverage).toFixed(0)}%`}
        />
      )}
      {status.outerCoverage != null && (
        <CoverageBar
          label="Outer mesh"
          fraction={status.outerCoverage}
          detail={`${(100 * status.outerCoverage).toFixed(0)}%`}
        />
      )}
      {reach != null && status.reachYCm != null && status.meshRMaxCm != null && (
        <CoverageBar
          label="Reach toward the rim"
          fraction={reach}
          detail={`${status.reachYCm.toFixed(0)} / ${status.meshRMaxCm.toFixed(0)} cm`}
        />
      )}
    </div>
  );
}

const RunQueueModal: React.FC<Props> = ({
  show,
  mode,
  title,
  setup,
  initialSimulation,
  defaultThermalPowerMw = null,
  wwPresent = false,
  result,
  exitCode,
  statusLabel,
  startedAt = null,
  finishedAt = null,
  saving = false,
  error = null,
  onHide,
  onSubmit,
}) => {
  const readOnly = mode === "view";
  const [draft, setDraft] = useState(() => queueSimulationFromRaw(initialSimulation));

  useEffect(() => {
    if (!show) return;
    const next = queueSimulationFromRaw(initialSimulation);
    // Append: prefill with the overview stack power so a later geometry can keep it.
    if (
      mode === "append" &&
      next.thermal_power_mw == null &&
      defaultThermalPowerMw != null &&
      Number.isFinite(defaultThermalPowerMw) &&
      defaultThermalPowerMw > 0
    ) {
      next.thermal_power_mw = defaultThermalPowerMw;
    }
    setDraft(next);
  }, [show, initialSimulation, mode, defaultThermalPowerMw]);

  const setField = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const setWeightWindows = (weight_windows: WeightWindowsRun) => {
    setDraft((prev) => applyWwPreset(prev, weight_windows));
  };

  const geometryBits = (() => {
    try {
      const normalized = normalizeSetup({ ...setup, simulation: draft });
      return `${normalized.columns} col · stack ${normalized.stack_m} m · a=${normalized.a}`;
    } catch {
      return "current calculator geometry";
    }
  })();

  const fieldDisabled = readOnly || saving;
  const hasSavedResult =
    result?.keff != null ||
    result?.gammaKGy != null ||
    result?.dddMeVPerG != null ||
    result?.pmaxRemaining != null ||
    result?.depletionBurnup != null ||
    result?.ingaasReachFraction != null ||
    Boolean(result?.summary);

  return (
    <Modal show={show} onHide={onHide} size="lg" centered scrollable>
      <Modal.Header closeButton>
        <Modal.Title className="h5 mb-0">{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p className="small text-secondary mb-3">
          {draft.run_mode === "slab"
            ? "This item is the 1D slab from Fast simulation. The chord below is the one that will be run."
            : `Geometry follows the calculator (${geometryBits}). These fields are the RIMAG run parameters for this queue item.`}
        </p>
        {draft.run_mode === "slab" && (draft.slab_layers?.length ?? 0) > 0 && (
          <p className="small mb-3 font-monospace">
            {draft.slab_layers!.map((layer) => `${layer.cm} cm ${layer.name}`).join(" · ")}
          </p>
        )}
        {statusLabel && (
          <p className="small mb-3">
            Status: <strong>{statusLabel}</strong>
            {exitCode != null ? ` · exit ${exitCode}` : ""}
            {mode === "view" && formatEndedAt(finishedAt)
              ? ` · ended ${formatEndedAt(finishedAt)}`
              : ""}
          </p>
        )}
        {mode === "view" &&
          (draft.weight_windows === "autorefine" || draft.weight_windows === "refine") &&
          statusLabel === "running" && (
            <div className="border rounded p-2 mb-3 bg-light-subtle">
              <div className="small text-uppercase text-secondary fw-semibold mb-2">Coverage</div>
              <LiveWwCoverage startedAt={startedAt} />
            </div>
          )}
        {mode === "view" &&
          (hasSavedResult ||
            (draft.weight_windows !== "autorefine" && draft.weight_windows !== "refine")) && (
          <div className="border rounded p-2 mb-3 bg-light-subtle">
            <div className="small text-uppercase text-secondary fw-semibold mb-1">Result</div>
            {result?.keff != null ? (
              <div className="font-monospace">
                keff {result.keff.toFixed(5)}
                {result.keffUncertainty != null ? ` ± ${result.keffUncertainty.toFixed(5)}` : ""}
              </div>
            ) : draft.weight_windows === "autorefine" || draft.weight_windows === "refine" ? null : (
              <div className="small text-secondary">No keff captured for this run.</div>
            )}
            {result?.gammaKGy != null && (
              <div className="font-monospace mt-1">
                InGaAs gamma dose {formatSci(result.gammaKGy)} kGy
                {result.gammaYears != null ? ` over ${formatDoseYears(result.gammaYears)} years` : ""}
                {result.gammaCi95Pct != null ? ` (± ${result.gammaCi95Pct.toFixed(2)}%, 95% CI)` : ""}
              </div>
            )}
            {result?.dddMeVPerG != null && (
              <div className="font-monospace mt-1">
                InGaAs DDD {formatSci(result.dddMeVPerG)} MeV/g
                {result.dddYears != null ? ` over ${formatDoseYears(result.dddYears)} years` : ""}
                {result.dddCi95Pct != null ? ` (± ${result.dddCi95Pct.toFixed(2)}%, 95% CI)` : ""}
              </div>
            )}
            {result?.pmaxRemaining != null && (
              <div className="font-monospace mt-1">
                InGaAs Pmax {(100 * result.pmaxRemaining).toFixed(1)}% of initial
                {result.pmaxYears != null ? ` over ${formatDoseYears(result.pmaxYears)} years` : ""}
                {result.pmaxCi95Pct != null ? ` (± ${result.pmaxCi95Pct.toFixed(2)}%, 95% CI)` : ""}
                {result.pmaxFluenceM2 != null
                  ? ` · XPNR-equivalent ${formatSci(result.pmaxFluenceM2)} m^-2`
                  : ""}
                {result.pmaxFastRemaining != null || result.pmaxTruncatedRemaining != null ? (
                  <div className="small text-secondary">
                    {result.pmaxFastRemaining != null
                      ? `fast-fluence definition ${(100 * result.pmaxFastRemaining).toFixed(1)}%`
                      : ""}
                    {result.pmaxFastRemaining != null && result.pmaxTruncatedRemaining != null ? " · " : ""}
                    {result.pmaxTruncatedRemaining != null
                      ? `truncated spectrum ${(100 * result.pmaxTruncatedRemaining).toFixed(1)}%`
                      : ""}
                    {result.pmaxOutsideRange ? " · outside the measured Wang range" : ""}
                  </div>
                ) : result.pmaxOutsideRange ? (
                  <div className="small text-secondary">outside the measured Wang range</div>
                ) : null}
                <div className="small text-secondary">
                  Baseline KX is provisional, folded for In0.68Ga0.32As. This cell is In0.53Ga0.47As.
                </div>
              </div>
            )}
            {(result?.dddMeVPerG != null || result?.gammaKGy != null) &&
              !(result?.ingaasReachFraction != null && result.ingaasReachFraction >= 1) && (
                <Alert variant="warning" className="py-2 px-3 small mt-2 mb-0">
                  Empty InGaAs weight-window cells score no neutrons. This dose divides by
                  the full InGaAs volume, so those cells bias it down.
                  {result?.ingaasReachFraction != null
                    ? ` Coverage is ${(100 * result.ingaasReachFraction).toFixed(0)}%.`
                    : ""}
                </Alert>
              )}
            {result?.depletionBurnup != null && result.depletionYears != null && (
              <div className="font-monospace mt-1">
                {result.depletionBelowOne
                  ? `keff below 1 after ${formatDepletionTime(result.depletionYears, result.depletionDays)}`
                  : `keff stayed at or above 1 through ${formatDepletionTime(result.depletionYears, result.depletionDays)}`}
                {` · ${formatBurnup(result.depletionBurnup)} MWd/kgHM`}
              </div>
            )}
            {result?.ingaasReachFraction != null && (
              <div className="font-monospace mt-2">
                InGaAs coverage {(100 * result.ingaasReachFraction).toFixed(0)}%
                {result.ingaasReached != null && result.ingaasVoxels != null
                  ? ` (${result.ingaasReached}/${result.ingaasVoxels} mesh cells)`
                  : ""}
                {result.ingaasReachFraction < 0.8 ? (
                  <span className="small text-secondary"> · target 80%</span>
                ) : (
                  <span className="small text-success"> · target met</span>
                )}
              </div>
            )}
            {result?.ingaasReachFraction != null &&
              result.ingaasReachFraction < 1 &&
              result.dddMeVPerG == null &&
              result.gammaKGy == null && (
                <Alert variant="warning" className="py-2 px-3 small mt-2 mb-0">
                  Empty InGaAs cells score no neutrons. A tally run with these windows
                  divides the dose by the full InGaAs volume, so those cells bias the DDD
                  and the gamma dose down.
                </Alert>
              )}
            {result?.ingaasEnergyFraction != null && (
              <div className="small text-secondary font-monospace">
                InGaAs energy groups {(100 * result.ingaasEnergyFraction).toFixed(0)}%
              </div>
            )}
            {result?.summary && (
              <div className="small text-secondary mt-1 text-break">{result.summary}</div>
            )}
          </div>
        )}
        {error && (
          <Alert variant="danger" className="py-2 px-3 small">
            {error}
          </Alert>
        )}

        <Form.Group className="simulation-field">
          <Form.Label className="small mb-0 simulation-field-label">Run mode</Form.Label>
          <Form.Select
            size="sm"
            value={draft.run_mode}
            disabled={fieldDisabled}
            onChange={(event) => setField("run_mode", event.target.value as RunMode)}
          >
            {RUN_MODES.filter(
              (modeOption) =>
                (modeOption !== "slab" && modeOption !== "keff_emitter_gamma_source") ||
                draft.run_mode === modeOption,
            ).map((modeOption) => (
              <option key={modeOption} value={modeOption}>
                {RUN_MODE_LABEL[modeOption] ?? modeOption}
              </option>
            ))}
          </Form.Select>
        </Form.Group>
        {draft.run_mode === "keff_gamma_dose" && (
          <p className="small text-secondary mb-3">
            Coupled neutron–photon keff. Photon heating in every InGaAs sheet is summed into one kGy
            over the dose time, scaled by this item’s slice of the stack thermal power. Neutron weight
            windows apply. The photons stay analog.
          </p>
        )}
        {draft.run_mode === "depletion" && (
          <p className="small text-secondary mb-3">
            Burns the fuel at this item’s slice thermal power. Each step is an eigenvalue calculation.
            The run stops when the mean keff stays below 1, and reports how long that took and the
            heavy-metal burnup at the crossing. The first steps are a day or less so xenon can build
            in. Later steps are longer while keff is still well above 1, then shorter as it approaches 1.
          </p>
        )}

        <Form.Group className="simulation-field">
          <Form.Label className="small mb-0 simulation-field-label">Batches</Form.Label>
          <Form.Control
            size="sm"
            type="number"
            min={1}
            step={1}
            value={draft.n_batches}
            disabled={fieldDisabled}
            onChange={(event) => setField("n_batches", Math.max(1, Math.round(Number(event.target.value) || 1)))}
          />
        </Form.Group>

        <Form.Group className="simulation-field">
          <FieldLabel info={<>Passed to OpenMC as <code>RIMAG_THREADS</code> / <code>simsettings.json</code>.</>}>
            OpenMP threads
          </FieldLabel>
          <Form.Control
            size="sm"
            type="number"
            min={1}
            max={256}
            step={1}
            value={draft.n_threads}
            disabled={fieldDisabled}
            onChange={(event) =>
              setField("n_threads", Math.max(1, Math.min(256, Math.round(Number(event.target.value) || 1))))
            }
          />
        </Form.Group>

        <Form.Group className="simulation-field">
          <Form.Label className="small mb-0 simulation-field-label">Neutron shield moderator</Form.Label>
          <Form.Select
            size="sm"
            value={draft.nsm_material}
            disabled={fieldDisabled}
            onChange={(event) => setField("nsm_material", event.target.value as NsmMaterial)}
          >
            {NSM_MATERIALS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Form.Select>
        </Form.Group>

        <Form.Group className="simulation-field">
          <FieldLabel info="Stored for the run config; app-slice CSG uses the zone layout.">
            NSM thickness (cm)
          </FieldLabel>
          <Form.Control
            size="sm"
            type="number"
            min={0}
            step={0.1}
            value={draft.nsm_thickness}
            disabled={fieldDisabled}
            onChange={(event) => setField("nsm_thickness", Math.max(0, Number(event.target.value) || 0))}
          />
        </Form.Group>

        <Form.Group className="simulation-field">
          <FieldLabel info="Elemental boron by mass in the graphite of the fuel layer. Reflector, disk, and shield graphite stay pure carbon.">
            Boron concentration (ppm)
          </FieldLabel>
          <Form.Control
            size="sm"
            type="number"
            min={0}
            step={1}
            value={draft.boron_concentration_ppm}
            disabled={fieldDisabled}
            onChange={(event) =>
              setField("boron_concentration_ppm", Math.max(0, Number(event.target.value) || 0))
            }
          />
        </Form.Group>

        <Form.Group className="simulation-field">
          <FieldLabel info="Layer bounds become cones about the disk axis (0° = flat disks). Increasing the conical pitch increases simulation time significantly.">
            Conical pitch (°)
          </FieldLabel>
          <Form.Control
            size="sm"
            type="number"
            min={0}
            max={45}
            step={0.1}
            value={draft.conical_pitch}
            disabled={fieldDisabled}
            onChange={(event) => setField("conical_pitch", Math.max(0, Number(event.target.value) || 0))}
          />
        </Form.Group>

        <Form.Group className="simulation-field">
          <Form.Label className="small mb-0 simulation-field-label">Particle type</Form.Label>
          <Form.Select
            size="sm"
            value={draft.particle_type}
            disabled={fieldDisabled || draft.run_mode === "keff_gamma_dose"}
            onChange={(event) => setField("particle_type", event.target.value as ParticleType)}
          >
            {PARTICLE_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </Form.Select>
        </Form.Group>

        <div className="border rounded p-2 mb-3 bg-light-subtle">
          <FieldLabel
            className="small mb-1 fw-semibold"
            info={
              <>
                For deep shields (~10 orders of magnitude to the InGaAs), seed once, then refine (or use{" "}
                <em>autorefine</em> to loop until ~80% of InGaAs mesh cells are reached) before the next queue
                step. Then set tally mode to <em>use</em> for a tally run.
              </>
            }
          >
            Weight windows
          </FieldLabel>
          {!readOnly && (
            <div className="d-flex flex-wrap gap-2 mb-2">
              <Button
                size="sm"
                variant={draft.weight_windows === "seed" ? "primary" : "outline-primary"}
                disabled={saving}
                onClick={() => setWeightWindows("seed")}
              >
                Seed
              </Button>
              <Button
                size="sm"
                variant={draft.weight_windows === "refine" ? "primary" : "outline-primary"}
                disabled={saving}
                title={
                  !wwPresent
                    ? "No weight_windows.h5 yet — queue a seed first, or refine after one finishes"
                    : undefined
                }
                onClick={() => setWeightWindows("refine")}
              >
                Refine
              </Button>
              <Button
                size="sm"
                variant={draft.weight_windows === "autorefine" ? "primary" : "outline-primary"}
                disabled={saving}
                title={
                  !wwPresent
                    ? "No weight_windows.h5 yet — queue a seed first, or autorefine after one finishes"
                    : "Keep refining until InGaAs mesh coverage reaches 80%"
                }
                onClick={() => setWeightWindows("autorefine")}
              >
                Autorefine
              </Button>
              {(draft.weight_windows === "seed" ||
                draft.weight_windows === "refine" ||
                draft.weight_windows === "autorefine") && (
                <Button
                  size="sm"
                  variant="outline-secondary"
                  disabled={saving}
                  onClick={() => setWeightWindows("no")}
                >
                  Clear to analog
                </Button>
              )}
            </div>
          )}
          <Form.Group className="simulation-field mb-2">
            <Form.Label className="small mb-0 simulation-field-label">Tally / build mode</Form.Label>
            <Form.Select
              size="sm"
              value={draft.weight_windows}
              disabled={fieldDisabled}
              onChange={(event) => setWeightWindows(event.target.value as WeightWindowsRun)}
            >
              {WEIGHT_WINDOWS_RUN.filter((value) => value !== "generate").map((value) => (
                <option key={value} value={value}>
                  {WW_OPTION_LABELS[value]}
                </option>
              ))}
              {draft.weight_windows === "generate" && (
                <option value="generate">{WW_OPTION_LABELS.generate}</option>
              )}
            </Form.Select>
            {(draft.weight_windows === "seed" ||
              draft.weight_windows === "refine" ||
              draft.weight_windows === "autorefine") && (
              <div className="small text-secondary mt-2 mb-0">
                Sets run mode to <code>keff_notallies</code>
                {draft.weight_windows === "seed"
                  ? " with survival biasing on."
                  : " with survival biasing off."}
                {draft.weight_windows === "autorefine" && (
                  <>
                    {" "}
                    Repeats refine until InGaAs coverage reaches 80% (or 25 passes), then the queue continues.
                    If a refine pass crashes (non-zero exit), the queue pauses so the next run does not start
                    with incomplete windows.
                  </>
                )}
                {(draft.weight_windows === "refine" || draft.weight_windows === "autorefine") &&
                  !wwPresent && (
                    <>
                      {" "}
                      Needs an existing <code>weight_windows.h5</code> when this item starts.
                    </>
                  )}
              </div>
            )}
          </Form.Group>
          <Form.Group className="simulation-field">
            <FieldLabel info="Start coarse (40 cm). Finer cells resolve the shield better but make seed/refine much slower.">
              Mesh cell (cm)
            </FieldLabel>
            <Form.Control
              size="sm"
              type="number"
              min={0.5}
              step={0.5}
              value={draft.ww_mesh_cm}
              disabled={fieldDisabled}
              onChange={(event) => setField("ww_mesh_cm", Math.max(0.5, Number(event.target.value) || 0.5))}
            />
          </Form.Group>
          <Form.Group className="simulation-field mb-0">
            <Form.Label className="small mb-0 simulation-field-label">Energy groups</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={1}
              max={200}
              step={1}
              value={draft.ww_energy_groups}
              disabled={fieldDisabled}
              onChange={(event) =>
                setField(
                  "ww_energy_groups",
                  Math.max(1, Math.min(200, Math.round(Number(event.target.value) || 1))),
                )
              }
            />
          </Form.Group>
        </div>

        <Form.Check
          type="checkbox"
          id="queue-survival-biasing"
          className="small mb-3"
          label="Survival biasing"
          checked={draft.survival_biasing}
          disabled={fieldDisabled}
          onChange={(event) => setField("survival_biasing", event.target.checked)}
        />

        <Form.Group className="simulation-field">
          <Form.Label className="small mb-0 simulation-field-label">Dose time (years)</Form.Label>
          <Form.Control
            size="sm"
            type="number"
            min={0}
            step={0.1}
            value={draft.dose_time}
            disabled={fieldDisabled}
            onChange={(event) => setField("dose_time", Math.max(0, Number(event.target.value) || 0))}
          />
        </Form.Group>

        <Form.Group className="simulation-field">
          <FieldLabel
            info={
              <>
                Whole-stack thermal power. The run gives the periodic slice its share,
                period height / stack height, before the source strength and DDD. Prefills
                with the overview stack power. Clear the field to use the thermodynamics-tab
                period power, which follows the geometry.
              </>
            }
          >
            Thermal power (MW)
          </FieldLabel>
          <Form.Control
            size="sm"
            type="number"
            min={0}
            step="any"
            placeholder={
              defaultThermalPowerMw != null && defaultThermalPowerMw > 0
                ? `auto ≈ ${defaultThermalPowerMw.toPrecision(4)} MW`
                : "thermodynamics-tab period"
            }
            value={draft.thermal_power_mw ?? ""}
            disabled={fieldDisabled}
            onChange={(event) => {
              const raw = event.target.value.trim();
              if (raw === "") {
                setField("thermal_power_mw", null);
                return;
              }
              const value = Number(raw);
              setField("thermal_power_mw", Number.isFinite(value) && value > 0 ? value : null);
            }}
          />
          <div className="small text-secondary mt-1">
            {setup.period_thermal_w > 0
              ? `${Number((setup.period_thermal_w / 1e6).toPrecision(4))} MW thermal in the modeled period, from the thermodynamics tab`
              : "The thermodynamics tab has no TPV heat for this geometry."}
            {defaultThermalPowerMw != null && defaultThermalPowerMw > 0
              ? ` (${Number(defaultThermalPowerMw.toPrecision(4))} MW over the stack).`
              : "."}{" "}
            Shell {setup.shell_temp_c.toFixed(0)} °C.
          </div>
        </Form.Group>

        <Form.Check
          type="checkbox"
          id="queue-print-core-characteristics"
          className="small mb-2"
          label="Print core characteristics"
          checked={draft.print_core_characteristics}
          disabled={fieldDisabled}
          onChange={(event) => setField("print_core_characteristics", event.target.checked)}
        />

        <Form.Check
          type="checkbox"
          id="queue-ddd-tallies-only"
          className="small mb-0"
          label={
            <span className="d-inline-flex align-items-center gap-1">
              Photovoltaic DDD tallies only
              <InfoTip text="When on, keff keeps the SR-NIEL flux tally and the InGaAs damage-energy tally (keff itself still comes from the eigenvalue solve). The damage-energy tally is the Wang Pmax result shown next to the DDD. Turn off for heating, tritium, C-14, IFP, and the rest." />
            </span>
          }
          checked={draft.ddd_tallies_only}
          disabled={fieldDisabled}
          onChange={(event) => setField("ddd_tallies_only", event.target.checked)}
        />
      </Modal.Body>
      <Modal.Footer>
        <Button variant="outline-secondary" onClick={onHide} disabled={saving}>
          {readOnly ? "Close" : "Cancel"}
        </Button>
        {!readOnly && onSubmit && (
          <Button
            variant="primary"
            disabled={saving}
            onClick={() => onSubmit({ ...draft, weight_windows: draft.weight_windows })}
          >
            {saving ? "Saving…" : mode === "append" ? "Append to queue" : "Save changes"}
          </Button>
        )}
      </Modal.Footer>
    </Modal>
  );
};

export default RunQueueModal;
