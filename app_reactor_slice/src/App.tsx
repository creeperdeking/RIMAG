import React, { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Col, Form, Row, Tab, Tabs } from "react-bootstrap";
import { Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import CompactSection from "./components/CompactSection";
import LayerChart from "./components/LayerChart";
import LayerEditor from "./components/LayerEditor";
import SimulationTab from "./components/SimulationTab";
import ThermodynamicTab from "./components/ThermodynamicTab";
import VisualisationTab from "./components/VisualisationTab";
import ZoneChart, { columnPoses } from "./components/ZoneChart";
import { LAYER_GROUPS, LAYER_MATCH_NOTE, TAB_KEYS, type LayerGroupId, type TabKey } from "./constants";
import {
  NUMERIC_FIELDS,
  RELOAD_FRACTIONS,
  formatPower,
  normalizeSetup,
  reloadShare,
  snap,
  type NumericKey,
  type ReloadFraction,
  type Setup,
  type SimulationParams,
} from "./configurations";
import { burnupDays, computeLayoutForRatio, formatBurnupTime, uraniumInventoryKg, type LayerRow } from "./geometry";
import {
  applyTrisoFuel,
  groupThicknesses,
  sameMaterialNames,
  setupFromState,
  sharedThickness,
  diskHeliumGapsCm,
  solidDiskThicknessCm,
  solidFuelThicknessCm,
  thicknessWarning,
  type Groups,
} from "./layers";
import { materialLibrary, materialLines } from "./materials";
import { airbridgeOperatingPoint } from "./data/tpvEmpiricalLimits";
import { chooseSetupToOpen, readStoredSetup, usesSavedFile, writeStoredSetup } from "./openSetup";

const TAB_STORAGE_KEY = "reactor-slice-active-tab";
const SETUPS_URL = "/api/setups";

const TAB_LABELS: Record<TabKey, string> = {
  overview: "Geometry",
  fuel: "Fuel setup",
  designer: "Layer designer",
  thermodynamic: "Thermodynamic",
  simulation: "Neutronics",
  visualisation: "Visualisation",
};

/** Stable reference so LayerChart's memo does not recompute on every render. */
const FUEL_ONLY: string[] = ["fuel"];

const NUMERIC_KEYS = Object.keys(NUMERIC_FIELDS) as NumericKey[];

type Notice = { kind: "success" | "danger"; text: string };

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

const fixed =
  (digits: number, suffix = "") =>
  (value: number): string =>
    `${value.toFixed(digits)}${suffix}`;

/** Like Python's `.3g`. */
function fmtG(value: number, digits = 3): string {
  return Number(value.toPrecision(digits)).toString();
}

function isTabKey(value: string | null): value is TabKey {
  return value !== null && (TAB_KEYS as readonly string[]).includes(value);
}

function readStoredTab(): TabKey | null {
  try {
    const stored = window.localStorage.getItem(TAB_STORAGE_KEY);
    return isTabKey(stored) ? stored : null;
  } catch {
    return null;
  }
}

function isPlaceholderStack(rows: LayerRow[], id: LayerGroupId): boolean {
  return rows.length === 1 && Math.abs(rows[0].cm - 1) < 1e-6 && rows[0].name === titleOf(id);
}

function titleOf(id: LayerGroupId): string {
  if (id === "disk") return "Disk layer";
  const found = LAYER_GROUPS.find(([groupId]) => groupId === id);
  return found ? found[1] : id;
}

/** Replace stacks that are still the titled 1 cm placeholder with the saved ones. */
function hydratePlaceholders(layers: Groups, from: Setup): Groups {
  const next = { ...layers };
  let changed = false;
  for (const id of Object.keys(layers) as LayerGroupId[]) {
    const saved = from.layers[id];
    if (isPlaceholderStack(layers[id], id) && saved && saved.length) {
      next[id] = saved.map((row) => ({ ...row }));
      changed = true;
    }
  }
  return changed ? next : layers;
}

function urlHasState(params: URLSearchParams): boolean {
  return params.has("layers") || params.has("simulation") || NUMERIC_KEYS.some((key) => params.has(key));
}

/** Restore numeric fields, dims, reload fraction, layers, and run params from the page address. */
function parseUrlSetup(params: URLSearchParams): Setup {
  const raw: Record<string, unknown> = {};
  for (const key of NUMERIC_KEYS) {
    const text = params.get(key);
    if (text !== null && text.trim() !== "") raw[key] = Number(text);
  }
  const reload = params.get("reload_fraction");
  if (reload) raw.reload_fraction = reload;
  const dims = params.get("dims");
  if (dims !== null) raw.dims = dims;
  const layers = params.get("layers");
  if (layers) {
    try {
      raw.layers = JSON.parse(layers) as unknown;
    } catch {
      // Ignore a damaged address and keep the default stacks.
    }
  }
  const simulation = params.get("simulation");
  if (simulation) {
    try {
      raw.simulation = JSON.parse(simulation) as unknown;
    } catch {
      // Ignore a damaged simulation blob.
    }
  }
  return normalizeSetup(raw);
}

function normalizeAll(data: unknown): Record<string, Setup> {
  const result: Record<string, Setup> = {};
  if (!data || typeof data !== "object" || Array.isArray(data)) return result;
  for (const [name, value] of Object.entries(data as Record<string, unknown>)) {
    try {
      result[name] = normalizeSetup(value);
    } catch {
      // Skip entries that are not configurations.
    }
  }
  return result;
}

async function fetchSetups(): Promise<Record<string, Setup>> {
  const response = await fetch(SETUPS_URL);
  if (!response.ok) throw new Error(`Could not read saved configurations (${response.status}).`);
  return normalizeAll((await response.json()) as unknown);
}

async function putSetups(all: Record<string, Setup>): Promise<Record<string, Setup>> {
  const response = await fetch(SETUPS_URL, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(all),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Could not save configurations (${response.status}).`);
  }
  return normalizeAll((await response.json()) as unknown);
}

// ---------------------------------------------------------------------------
// Presentational components
// ---------------------------------------------------------------------------

type SliderProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
  onChange: (value: number) => void;
};

/** Compact slider: label left, value right (double-click the value to type one). */
const Slider: React.FC<SliderProps> = ({ label, value, min, max, step, format, onChange }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const startEdit = () => {
    setDraft(String(value));
    setEditing(true);
  };

  const commit = () => {
    const parsed = Number(draft.replace(",", "."));
    if (draft.trim() !== "" && Number.isFinite(parsed)) onChange(snap(parsed, min, max, step));
    setEditing(false);
  };

  return (
    <Form.Group className="control-slider">
      <Form.Label className="d-flex justify-content-between align-items-baseline w-100">
        <span>{label}</span>
        <span className="slider-value-wrap">
          {editing ? (
            <Form.Control
              autoFocus
              size="sm"
              className="slider-value-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onBlur={commit}
              onKeyDown={(event) => {
                if (event.key === "Enter") commit();
                if (event.key === "Escape") setEditing(false);
              }}
            />
          ) : (
            <span
              className="slider-value fw-semibold"
              title="Double-click to type a value"
              onDoubleClick={startEdit}
            >
              {format(value)}
            </span>
          )}
        </span>
      </Form.Label>
      <Form.Range
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(snap(Number(event.target.value), min, max, step))}
      />
    </Form.Group>
  );
};

const Metric: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="border rounded p-3 bg-white">
    <div className="small text-secondary">{label}</div>
    <div className="fs-5 fw-semibold">{value}</div>
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const Explorer: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  // Some router versions change setSearchParams whenever the address changes;
  // keep it in a ref so writing the address never retriggers the sync effect.
  const writeParams = useRef(setSearchParams);
  writeParams.current = setSearchParams;

  // Read the address once, on first render.
  const [boot] = useState(() => ({
    setup: parseUrlSetup(searchParams),
    cfg: searchParams.get("cfg"),
    hasUrlState: urlHasState(searchParams),
    tab: isTabKey(searchParams.get("tab")) ? (searchParams.get("tab") as TabKey) : readStoredTab() ?? "overview",
  }));

  const [setup, setSetup] = useState<Setup>(boot.setup);
  const [tab, setTab] = useState<TabKey>(boot.tab);
  const [saved, setSaved] = useState<Record<string, Setup>>({});
  const [loadedCfg, setLoadedCfg] = useState<string | null>(boot.cfg);
  const [choice, setChoice] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [copying, setCopying] = useState(false);
  const [copyNote, setCopyNote] = useState<Notice | null>(null);

  const savedNames = useMemo(() => Object.keys(saved).sort((a, b) => a.localeCompare(b)), [saved]);

  // -- Saved setups: load once on mount ------------------------------------
  useEffect(() => {
    let cancelled = false;
    fetchSetups()
      .then((all) => {
        if (cancelled) return;
        setSaved(all);
        const names = Object.keys(all);
        const remembered = readStoredSetup();
        const name = chooseSetupToOpen(names, boot.cfg, remembered);
        if (name && all[name]) {
          const target = all[name];
          const openedFromMemory = !boot.cfg && name === remembered;
          if (usesSavedFile(boot.hasUrlState, openedFromMemory)) {
            setSetup(target);
          } else {
            setSetup((prev) => ({ ...prev, layers: hydratePlaceholders(prev.layers, target) }));
          }
          setLoadedCfg(name);
          setChoice(name);
          writeStoredSetup(name);
        } else if (boot.cfg) {
          setLoadedCfg(null);
          if (readStoredSetup() === boot.cfg) writeStoredSetup(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setNotice({ kind: "danger", text: error instanceof Error ? error.message : String(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [boot]);

  // Keep the load choice pointing at a saved name.
  useEffect(() => {
    if (savedNames.length && !savedNames.includes(choice)) setChoice(savedNames[0]);
    if (!savedNames.length && choice) setChoice("");
  }, [savedNames, choice]);

  // -- Fuel layers follow the TRISO parameters ------------------------------
  const triso = useMemo(
    () =>
      applyTrisoFuel(
        setup.layers,
        setup.cylinder_diameter_mm,
        setup.wall_margin_mm,
        setup.compact_spacing_mm,
        setup.packing_pct,
        setup.hm_particle_pct,
      ),
    [
      setup.layers,
      setup.cylinder_diameter_mm,
      setup.wall_margin_mm,
      setup.compact_spacing_mm,
      setup.packing_pct,
      setup.hm_particle_pct,
    ],
  );
  const groups: Groups = triso.groups;

  useEffect(() => {
    if (triso.groups === setup.layers) return;
    setSetup((prev) => {
      const next = applyTrisoFuel(
        prev.layers,
        prev.cylinder_diameter_mm,
        prev.wall_margin_mm,
        prev.compact_spacing_mm,
        prev.packing_pct,
        prev.hm_particle_pct,
      ).groups;
      return next === prev.layers ? prev : { ...prev, layers: next };
    });
  }, [triso, setup.layers]);

  // -- Layer thickness ------------------------------------------------------
  const layerTotals = useMemo(() => groupThicknesses(groups), [groups]);
  const layerCm = useMemo(() => sharedThickness(layerTotals), [layerTotals]);

  // -- Geometry -------------------------------------------------------------
  const mergeReflector = sameMaterialNames(groups.reflector, groups.shield_moderator);
  const shieldA = mergeReflector ? setup.a + setup.refl : setup.a;
  const reflector = mergeReflector ? 0 : setup.refl;
  const layout = useMemo(
    () =>
      computeLayoutForRatio(
        shieldA,
        (setup.a * setup.b_pct) / 100,
        setup.w,
        setup.ratio_pct / 100,
        reflector,
        setup.abs,
      ),
    [shieldA, setup.a, setup.b_pct, setup.w, setup.ratio_pct, reflector, setup.abs],
  );

  // -- Power ----------------------------------------------------------------
  const columns = Math.round(setup.columns);
  const oppositeArea = layout.oppositeArea <= 1e-6 * layout.totalArea ? 0 : layout.oppositeArea;
  const operatingPoint = useMemo(() => {
    const gaps = diskHeliumGapsCm(groups.disk);
    return airbridgeOperatingPoint({
      fuelTempC: setup.fuel_temp_c,
      fuelEmissivity: setup.fuel_emissivity,
      diskEmissivity: setup.disk_emissivity,
      shellEmissivity: setup.shell_emissivity,
      fuelAreaM2: layout.fuelArea,
      tpvAreaM2: oppositeArea,
      fuelGapCm: gaps.fuelGapCm,
      tpvGapCm: gaps.tpvGapCm,
      cellIndex: setup.tpv_airbridge_cell,
    });
  }, [
    groups.disk,
    setup.fuel_temp_c,
    setup.fuel_emissivity,
    setup.disk_emissivity,
    setup.shell_emissivity,
    setup.tpv_airbridge_cell,
    layout.fuelArea,
    oppositeArea,
  ]);
  // Both TPV faces count. 1 W/cm² over 1 m² is 10 kW.
  const slicePower = 2 * operatingPoint.powerWPerCm2 * 10 * oppositeArea * columns;
  const nSlices = layerCm === null ? null : setup.stack_m / (layerCm / 100);
  const stackPower = nSlices === null ? null : slicePower * nSlices;
  const sliceThermalKw = 2 * operatingPoint.absorbedWPerCm2 * 10 * oppositeArea * columns;
  const thermalPower = nSlices === null ? null : sliceThermalKw * nSlices;

  // -- Fuel / materials -----------------------------------------------------
  const { specs, mixed } = useMemo(() => materialLibrary(setup.enrichment_pct), [setup.enrichment_pct]);
  const burnup = (setup.enrichment_pct / 100) * 1200;

  const burnupSummary = useMemo((): { time: string; note: string | null } => {
    if (thermalPower === null || layerCm === null) {
      return { time: "—", note: "Shown once Zones overview has a thermal power." };
    }
    const { massKg, skipped } = uraniumInventoryKg(
      groups.fuel,
      layout.fuelArea,
      columns,
      setup.stack_m,
      layerCm,
      specs,
      mixed,
    );
    const extra = skipped.length
      ? ` ${skipped.map((name) => `'${name}'`).join(", ")} ${skipped.length === 1 ? "is" : "are"} left out of the fuel mass.`
      : "";
    if (massKg <= 0) return { time: "—", note: `This layer has no uranium-bearing material.${extra}` };
    if (thermalPower <= 0) return { time: "—", note: `Thermal power is zero.${extra}` };
    const days = burnupDays(massKg, Math.round(burnup), thermalPower) * reloadShare(setup.reload_fraction);
    return { time: formatBurnupTime(days), note: extra.trim() || null };
  }, [thermalPower, layerCm, groups.fuel, layout.fuelArea, columns, setup.stack_m, specs, mixed, burnup, setup.reload_fraction]);

  // -- Page address and tab persistence -------------------------------------
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("a", setup.a.toFixed(2));
    params.set("abs", setup.abs.toFixed(2));
    params.set("refl", setup.refl.toFixed(2));
    params.set("b_pct", setup.b_pct.toFixed(0));
    params.set("w", setup.w.toFixed(2));
    params.set("ratio_pct", setup.ratio_pct.toFixed(0));
    params.set("fuel_temp_c", setup.fuel_temp_c.toFixed(0));
    params.set("fuel_emissivity", setup.fuel_emissivity.toFixed(2));
    params.set("disk_emissivity", setup.disk_emissivity.toFixed(2));
    params.set("shell_emissivity", setup.shell_emissivity.toFixed(2));
    params.set("tpv_airbridge_cell", String(setup.tpv_airbridge_cell));
    params.set("enrichment_pct", setup.enrichment_pct.toFixed(1));
    params.set("packing_pct", setup.packing_pct.toFixed(0));
    params.set("hm_particle_pct", setup.hm_particle_pct.toFixed(0));
    params.set("cylinder_diameter_mm", setup.cylinder_diameter_mm.toFixed(1));
    params.set("wall_margin_mm", setup.wall_margin_mm.toFixed(1));
    params.set("compact_spacing_mm", setup.compact_spacing_mm.toFixed(1));
    params.set("reload_fraction", setup.reload_fraction);
    params.set("layer_cm", layerCm === null ? "" : layerCm.toFixed(2));
    const compact: Record<string, Array<{ n: string; cm: number }>> = {};
    for (const [id, rows] of Object.entries(groups)) {
      compact[id] = rows.map((row) => ({ n: row.name, cm: Math.round(row.cm * 10000) / 10000 }));
    }
    params.set("layers", JSON.stringify(compact));
    params.set("stack_m", setup.stack_m.toFixed(1));
    params.set("columns", String(columns));
    params.set("dims", setup.dims ? "1" : "0");
    params.set("simulation", JSON.stringify(setup.simulation));
    if (loadedCfg) params.set("cfg", loadedCfg);
    params.set("tab", tab);
    writeParams.current(params, { replace: true });
  }, [setup, groups, layerCm, columns, loadedCfg, tab]);

  useEffect(() => {
    try {
      window.localStorage.setItem(TAB_STORAGE_KEY, tab);
    } catch {
      // Storage may be unavailable; the address still keeps the tab.
    }
  }, [tab]);

  // -- Handlers -------------------------------------------------------------
  const setNumber = (key: NumericKey, value: number) => {
    setSetup((prev) => ({ ...prev, [key]: value }) as Setup);
  };

  const setGroupRows = (id: LayerGroupId, rows: LayerRow[]) => {
    setSetup((prev) => ({ ...prev, layers: { ...prev.layers, [id]: rows } }));
  };

  const withOperatingPoint = (base: Setup): Setup => ({
    ...base,
    tpv_density: operatingPoint.powerWPerCm2,
    tpv_eff_pct: operatingPoint.efficiencyPct,
    tpv_absorbed_w_per_cm2: operatingPoint.absorbedWPerCm2,
    shell_temp_c: operatingPoint.shellTempC,
    period_thermal_w: sliceThermalKw * 1000,
    period_electric_w: slicePower * 1000,
  });

  const currentSetup = (): Setup =>
    withOperatingPoint(normalizeSetup(setupFromState(setup, groups)));

  const persistNamed = async (name: string, message?: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      setNotice({ kind: "danger", text: "Enter a configuration name." });
      return;
    }
    try {
      const persisted = await putSetups({ ...saved, [trimmed]: currentSetup() });
      setSaved(persisted);
      setChoice(trimmed);
      setLoadedCfg(trimmed);
      writeStoredSetup(trimmed);
      setNotice({ kind: "success", text: message ?? `Saved ${trimmed}.` });
    } catch (error) {
      setNotice({ kind: "danger", text: error instanceof Error ? error.message : String(error) });
    }
  };

  const onSave = async () => {
    if (loadedCfg) {
      await persistNamed(loadedCfg, `Updated ${loadedCfg}.`);
      return;
    }
    const typed = window.prompt("Configuration name");
    if (typed == null) return;
    await persistNamed(typed);
  };

  const onCreate = async () => {
    const typed = window.prompt("New configuration name", loadedCfg ? `${loadedCfg}-copy` : "");
    if (typed == null) return;
    await persistNamed(typed, `Created ${typed.trim()}.`);
  };

  const onSelectConfig = (name: string) => {
    setChoice(name);
    const target = saved[name];
    if (!target) return;
    setSetup(target);
    setLoadedCfg(name);
    writeStoredSetup(name);
    setNotice({ kind: "success", text: `Loaded ${name}.` });
  };

  const onCopyBlender = async () => {
    setCopying(true);
    setCopyNote(null);
    try {
      const centers = columnPoses(columns, layout.rOuter).map(([x, y]) => [x, y]);
      const response = await fetch("/api/blender-clipboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ radius: layout.rOuter, height: setup.stack_m, centers }),
      });
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      if (!response.ok) throw new Error(payload.error || "Could not copy the 3D model.");
      const noun = columns === 1 ? "cylinder" : "cylinders";
      setCopyNote({
        kind: "success",
        text: `Copied ${columns} ${noun}. Paste in Blender's 3D View with Ctrl+V.`,
      });
    } catch (error) {
      setCopyNote({ kind: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setCopying(false);
    }
  };

  const onDelete = async () => {
    const name = loadedCfg || choice;
    if (!name || !saved[name]) return;
    if (!window.confirm(`Delete ${name} from the save folder?`)) return;
    const next = { ...saved };
    delete next[name];
    try {
      const persisted = await putSetups(next);
      setSaved(persisted);
      if (loadedCfg === name) setLoadedCfg(null);
      if (readStoredSetup() === name) writeStoredSetup(null);
      setNotice({ kind: "success", text: `Deleted ${name}.` });
    } catch (error) {
      setNotice({ kind: "danger", text: error instanceof Error ? error.message : String(error) });
    }
  };

  // -- Render helpers -------------------------------------------------------
  const renderSlider = (key: NumericKey, label: string, format: (value: number) => string) => {
    const [min, max, step] = NUMERIC_FIELDS[key];
    return (
      <Slider
        key={key}
        label={label}
        value={setup[key]}
        min={min}
        max={max}
        step={step}
        format={format}
        onChange={(value) => setNumber(key, value)}
      />
    );
  };

  const shieldLabel = mergeReflector ? "Shield moderator (+ reflector)" : "Shield moderator";
  const resultRows: Array<[string, string]> = [
    ["Thermal", thermalPower === null ? "—" : formatPower(thermalPower)],
    ["Stack", stackPower === null ? "—" : formatPower(stackPower)],
    ["Fuel", `${fmtG(layout.fuelArea * columns)} m²`],
  ];
  if (!mergeReflector) resultRows.push(["Reflector", `${fmtG(layout.reflectorArea * columns)} m²`]);
  resultRows.push(
    ["TPV", `${fmtG(oppositeArea * columns)} m²`],
    [shieldLabel, `${fmtG(layout.gapArea * columns)} m²`],
    ["Shield absorber", `${fmtG(layout.absorberArea * columns)} m²`],
    ["Disk", `${fmtG(layout.totalArea * columns)} m²`],
    ["Diameter", `${fmtG(2 * layout.rOuter)} m`],
  );
  const resultNote =
    nSlices === null || layerCm === null
      ? LAYER_MATCH_NOTE
      : `${columns} column${columns === 1 ? "" : "s"}, ${fmtG(nSlices, 4)} slices of ${layerCm.toFixed(2)} cm in ${setup.stack_m.toFixed(1)} m, both TPV faces`;

  const graphiteFraction = 1 - triso.hmFraction;
  const uo2ToGraphite = graphiteFraction > 0 ? triso.hmFraction / graphiteFraction : Infinity;

  // -- Tabs -----------------------------------------------------------------
  const geometryControls = (
    <div className="controls geometry-controls border rounded p-3 h-100">
      {renderSlider("a", "shield moderator thickness (m)", fixed(1))}
      {renderSlider("abs", "shield absorber thickness (m)", fixed(2))}
      {renderSlider("refl", "reflector thickness (m)", fixed(1))}
      {renderSlider("b_pct", "b (%)", fixed(0, "%"))}
      {renderSlider("w", "w (rim width)", fixed(1))}
      {renderSlider("ratio_pct", "fuel / TPV", fixed(0, "%"))}
      {layerCm === null && (
        <Alert variant="warning" className="py-2 px-3 small my-2">
          <div className="fw-semibold">Layers must have the same thickness</div>
          {thicknessWarning(layerTotals)}
        </Alert>
      )}
      {renderSlider("stack_m", "stack height (m)", fixed(1))}
      {renderSlider("columns", "columns", fixed(0))}
      <Form.Check
        type="checkbox"
        id="show-dims"
        className="small mt-1"
        label="Show dimension lines"
        checked={setup.dims}
        onChange={(event) => setSetup((prev) => ({ ...prev, dims: event.target.checked }))}
      />
    </div>
  );

  const overviewTab = (
    <Row className="g-3">
      <Col lg={3}>{geometryControls}</Col>
      <Col lg={6}>
        <ZoneChart
          layout={layout}
          showDims={setup.dims}
          columns={columns}
          outerReflector={columns === 1 ? setup.refl : 0}
        />
        {mergeReflector && (
          <div className="small text-secondary mt-2">
            Reflector and shield moderator use the same materials, so the reflector ({setup.refl.toFixed(2)} m) is
            folded into the shield moderator ({setup.a.toFixed(2)} m → {(setup.a + setup.refl).toFixed(2)} m) and
            omitted as a separate core sector.
          </div>
        )}
      </Col>
      <Col lg={3}>
        <div className="border rounded p-3 bg-white">
          <h2 className="h6 mb-2">Results</h2>
          <div className="results-compact">
            {resultRows.map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <b>{value}</b>
              </div>
            ))}
            <p>{resultNote}</p>
          </div>
        </div>
        <div className="mt-3">
          <Button variant="outline-secondary" disabled={copying} onClick={() => void onCopyBlender()}>
            {copying ? "Copying…" : "Copy 3D model"}
          </Button>
          <div className="small text-secondary mt-2">
            64 side faces, one cylinder per column. Paste in Blender's 3D View with Ctrl+V.
          </div>
          {copyNote && (
            <Alert
              variant={copyNote.kind}
              dismissible
              className="py-2 px-3 small mt-2 mb-0"
              onClose={() => setCopyNote(null)}
            >
              {copyNote.text}
            </Alert>
          )}
        </div>
      </Col>
    </Row>
  );

  const fuelTab = (
    <Row className="g-4">
      <Col lg={7}>
        <div>
          {renderSlider("enrichment_pct", "Fuel enrichment", fixed(1, "%"))}
          <div className="my-2">
            <Row className="g-2">
              <Col xs={6}>
                <Metric label="Burnup" value={`${Math.round(burnup).toLocaleString("en-US")} MWd/kgHM`} />
              </Col>
              <Col xs={6}>
                <Metric label="Burnup time" value={burnupSummary.time} />
              </Col>
            </Row>
            <div className="small text-secondary mt-1">
              {burnupSummary.note ?? "Burnup is the enrichment fraction multiplied by 1200."}
            </div>
          </div>
          {renderSlider("packing_pct", "Packing fraction", fixed(0, "%"))}
          {renderSlider("hm_particle_pct", "HM fraction per particle", fixed(0, "%"))}
          {renderSlider("cylinder_diameter_mm", "Cylinder diameter", fixed(1, " mm"))}
          {renderSlider("wall_margin_mm", "Fuel compact wall margin", fixed(1, " mm"))}
          {renderSlider("compact_spacing_mm", "Compact spacing", fixed(1, " mm"))}
          <div className="control-heading fw-semibold">Reload fraction</div>
          <div className="btn-group btn-group-sm" role="group" aria-label="Reload fraction">
            {RELOAD_FRACTIONS.map((fraction: ReloadFraction) => (
              <Button
                key={fraction}
                size="sm"
                variant={setup.reload_fraction === fraction ? "primary" : "outline-primary"}
                onClick={() => setSetup((prev) => ({ ...prev, reload_fraction: fraction }))}
              >
                {fraction}
              </Button>
            ))}
          </div>
        </div>
      </Col>
      <Col lg={5}>
        <CompactSection
          diameterMm={setup.cylinder_diameter_mm}
          wallMarginMm={setup.wall_margin_mm}
          spacingMm={setup.compact_spacing_mm}
          packingPct={setup.packing_pct}
          hmParticlePct={setup.hm_particle_pct}
          specs={specs}
          mixed={mixed}
        />
        <div className="small text-secondary mt-1 mb-3">
          Two compacts held by a graphite slab with flat top and bottom. The dashed circle is the wall margin, and the
          kernels are the heavy metal in each particle.
        </div>
        <LayerChart
          groups={groups}
          layerCm={layerCm}
          specs={specs}
          mixed={mixed}
          only={FUEL_ONLY}
          includeDisk={false}
          title="Fuel layer"
          shieldModerator={setup.simulation.nsm_material}
        />
        <div className="small text-secondary mt-1">
          TRISO particles fill {(triso.particleInCylinder * 100).toFixed(1)}% of each cylinder. Heavy metal is{" "}
          {(triso.hmFraction * 100).toFixed(2)}% of the {(setup.cylinder_diameter_mm / 10).toFixed(2)} cm fuel layer.
          UO2 / graphite = {Number.isFinite(uo2ToGraphite) ? uo2ToGraphite.toFixed(3) : "∞"}.
        </div>
      </Col>
    </Row>
  );

  const editorGroups: Array<[LayerGroupId, string]> = [
    ["disk", "Disk layer"],
    ...LAYER_GROUPS.filter(([id]) => id !== "fuel").map(([id, title]): [LayerGroupId, string] => [id, title]),
  ];

  const renderEditor = (id: LayerGroupId, title: string) => (
    <LayerEditor
      key={id}
      title={title}
      fallback={title}
      rows={groups[id]}
      lines={materialLines(groups[id], specs, mixed, setup.simulation.nsm_material)}
      onChange={(rows) => setGroupRows(id, rows)}
    />
  );

  const designerTab = (
    <div className="designer-layout">
      <div>
        <div className="small text-secondary mb-2">
          {LAYER_MATCH_NOTE} That thickness is the slice pitch. Drag a handle to reorder a material. The top row is
          the bottom of the bar.
        </div>
        {renderEditor(editorGroups[0][0], editorGroups[0][1])}
        {layerCm === null && (
          <Alert variant="warning">
            <Alert.Heading className="h6">Layers must have the same thickness</Alert.Heading>
            {thicknessWarning(layerTotals)}
          </Alert>
        )}
        {editorGroups.slice(1).map(([id, title]) => renderEditor(id, title))}
      </div>
      <LayerChart
        groups={groups}
        layerCm={layerCm}
        specs={specs}
        mixed={mixed}
        shieldModerator={setup.simulation.nsm_material}
      />
    </div>
  );

  const diskThicknessCm = useMemo(() => solidDiskThicknessCm(groups.disk), [groups.disk]);
  const fuelThicknessCm = useMemo(() => solidFuelThicknessCm(groups.fuel), [groups.fuel]);
  const heliumGaps = useMemo(() => diskHeliumGapsCm(groups.disk), [groups.disk]);
  const thermodynamicTab = (
    <ThermodynamicTab
      setup={setup}
      diskThicknessCm={diskThicknessCm}
      fuelGapCm={heliumGaps.fuelGapCm}
      tpvGapCm={heliumGaps.tpvGapCm}
      diskAreaM2={layout.totalArea}
      fuelThicknessCm={fuelThicknessCm}
      fuelAreaM2={layout.fuelArea}
      fuelAngleRad={layout.fuelAngle}
      tpvAngleRad={layout.oppositeAngle}
      tpvAreaM2={oppositeArea}
      operatingPoint={operatingPoint}
      renderSlider={renderSlider}
      onNumericChange={setNumber}
    />
  );

  const onSimulationChange = (simulation: SimulationParams) => {
    setSetup((prev) => ({ ...prev, simulation }));
  };

  const simulationTab = (
    <SimulationTab
      params={setup.simulation}
      onChange={onSimulationChange}
      setup={withOperatingPoint(setup)}
      defaultThermalPowerMw={thermalPower == null ? null : thermalPower / 1000}
    />
  );

  const tabContent: Record<TabKey, React.ReactNode> = {
    overview: overviewTab,
    fuel: fuelTab,
    designer: designerTab,
    thermodynamic: thermodynamicTab,
    simulation: simulationTab,
    visualisation: <VisualisationTab />,
  };

  return (
    <div className="app-shell">
      <main className="app-main">
        <div className="app-main-header">
          <h1 className="h5 mb-0">RIMAEL simulations</h1>
          <div className="config-toolbar">
            <Form.Select
              size="sm"
              className="config-toolbar-select"
              value={loadedCfg ?? choice}
              disabled={!savedNames.length}
              aria-label="Saved configuration"
              onChange={(event) => onSelectConfig(event.target.value)}
            >
              {!savedNames.length && <option value="">Unsaved</option>}
              {savedNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Form.Select>
            <Button
              size="sm"
              variant="outline-secondary"
              className="config-toolbar-icon"
              title="Create a new configuration from the current setup"
              onClick={() => void onCreate()}
            >
              +
            </Button>
            <Button
              size="sm"
              variant="primary"
              title={loadedCfg ? `Save ${loadedCfg}` : "Save configuration"}
              onClick={() => void onSave()}
            >
              Save
            </Button>
            {loadedCfg && (
              <Button
                size="sm"
                variant="link"
                className="config-toolbar-delete"
                title={`Delete ${loadedCfg}`}
                onClick={() => void onDelete()}
              >
                ×
              </Button>
            )}
          </div>
        </div>
        {notice && (
          <Alert
            variant={notice.kind}
            dismissible
            className="py-2 px-3 small config-toolbar-notice"
            onClose={() => setNotice(null)}
          >
            {notice.text}
          </Alert>
        )}
        <Tabs
          activeKey={tab}
          onSelect={(key) => {
            if (isTabKey(key)) setTab(key);
          }}
          mountOnEnter
          // Keep mounted tabs alive so Simulation can keep streaming output.
          unmountOnExit={false}
          className="mb-0 app-main-tabs"
        >
          {TAB_KEYS.map((key) => (
            <Tab key={key} eventKey={key} title={TAB_LABELS[key]} className="pt-3">
              {tabContent[key]}
            </Tab>
          ))}
        </Tabs>
      </main>
    </div>
  );
};

const App: React.FC = () => (
  <Routes>
    <Route path="/" element={<Explorer />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);

export default App;
