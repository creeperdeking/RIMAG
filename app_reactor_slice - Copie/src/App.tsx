import React, { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Col, Container, Form, Row, Tab, Tabs } from "react-bootstrap";
import { Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import ColumnsView from "./components/ColumnsView";
import CompactSection from "./components/CompactSection";
import LayerChart from "./components/LayerChart";
import LayerEditor from "./components/LayerEditor";
import ZoneChart from "./components/ZoneChart";
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
} from "./configurations";
import { burnupDays, computeLayoutForRatio, formatBurnupTime, uraniumInventoryKg, type LayerRow } from "./geometry";
import {
  applyTrisoFuel,
  groupThicknesses,
  sameMaterialNames,
  setupFromState,
  sharedThickness,
  thicknessWarning,
  type Groups,
} from "./layers";
import { materialLibrary, materialLines, materialNames } from "./materials";

const TAB_STORAGE_KEY = "reactor-slice-active-tab";
const SETUPS_URL = "/api/setups";

const TAB_LABELS: Record<TabKey, string> = {
  overview: "Zones overview",
  fuel: "Fuel setup",
  designer: "Layer designer",
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
  return params.has("layers") || NUMERIC_KEYS.some((key) => params.has(key));
}

/** Restore numeric fields, dims, reload fraction, and layers from the page address. */
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
  const [saveName, setSaveName] = useState("");
  const [choice, setChoice] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);

  const savedNames = useMemo(() => Object.keys(saved).sort((a, b) => a.localeCompare(b)), [saved]);

  // -- Saved setups: load once on mount ------------------------------------
  useEffect(() => {
    let cancelled = false;
    fetchSetups()
      .then((all) => {
        if (cancelled) return;
        setSaved(all);
        const names = Object.keys(all);
        const cfg = boot.cfg;
        if (cfg && all[cfg]) {
          const target = all[cfg];
          if (boot.hasUrlState) {
            setSetup((prev) => ({ ...prev, layers: hydratePlaceholders(prev.layers, target) }));
          } else {
            setSetup(target);
          }
          setLoadedCfg(cfg);
          setChoice(cfg);
        } else if (cfg) {
          setLoadedCfg(null);
        } else if (names.length === 1) {
          const only = all[names[0]];
          setSetup((prev) => ({ ...prev, layers: hydratePlaceholders(prev.layers, only) }));
          setLoadedCfg(names[0]);
          setChoice(names[0]);
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
  // Both TPV faces count. 1 W/cm² over 1 m² is 10 kW.
  const slicePower = 2 * setup.tpv_density * 10 * oppositeArea * columns;
  const nSlices = layerCm === null ? null : setup.stack_m / (layerCm / 100);
  const stackPower = nSlices === null ? null : slicePower * nSlices;
  const thermalPower = stackPower === null ? null : stackPower / (setup.tpv_eff_pct / 100);

  // -- Fuel / materials -----------------------------------------------------
  const { specs, mixed } = useMemo(() => materialLibrary(setup.enrichment_pct), [setup.enrichment_pct]);
  const materialOptions = useMemo(() => materialNames(specs, mixed), [specs, mixed]);
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
    params.set("tpv_density", setup.tpv_density.toFixed(2));
    params.set("tpv_eff_pct", setup.tpv_eff_pct.toFixed(0));
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

  const currentSetup = (): Setup => normalizeSetup(setupFromState(setup, groups));

  const onSave = async () => {
    const name = saveName.trim() || choice;
    if (!name) {
      setNotice({ kind: "danger", text: "Enter a configuration name." });
      return;
    }
    try {
      const persisted = await putSetups({ ...saved, [name]: currentSetup() });
      setSaved(persisted);
      setChoice(name);
      setNotice({ kind: "success", text: `Saved ${name}.` });
    } catch (error) {
      setNotice({ kind: "danger", text: error instanceof Error ? error.message : String(error) });
    }
  };

  const onLoad = () => {
    const target = saved[choice];
    if (!choice || !target) {
      setNotice({ kind: "danger", text: "Choose a saved configuration." });
      return;
    }
    setSetup(target);
    setLoadedCfg(choice);
    setNotice({ kind: "success", text: `Loaded ${choice}.` });
  };

  const onDelete = async () => {
    if (!choice || !saved[choice]) return;
    if (!window.confirm(`Delete ${choice} from the save folder?`)) return;
    const next = { ...saved };
    delete next[choice];
    try {
      const persisted = await putSetups(next);
      setSaved(persisted);
      if (loadedCfg === choice) setLoadedCfg(null);
      setNotice({ kind: "success", text: `Deleted ${choice}.` });
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
  const overviewTab = (
    <>
      <Row className="g-3">
        <Col lg={8}>
          <ZoneChart layout={layout} showDims={setup.dims} columns={columns} />
          {mergeReflector && (
            <div className="small text-secondary mt-2">
              Reflector and shield moderator use the same materials, so the reflector ({setup.refl.toFixed(2)} m) is
              folded into the shield moderator ({setup.a.toFixed(2)} m → {(setup.a + setup.refl).toFixed(2)} m) and
              omitted as a separate core sector.
            </div>
          )}
        </Col>
        <Col lg={4}>
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
        </Col>
      </Row>
      <div className="mt-3">
        <ColumnsView rOuter={layout.rOuter} stackM={setup.stack_m} columns={columns} />
      </div>
    </>
  );

  const fuelTab = (
    <Row className="g-3">
      <Col md={6}>
        <div className="controls">
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
      <Col md={6}>
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
        <LayerChart groups={groups} layerCm={layerCm} specs={specs} mixed={mixed} only={FUEL_ONLY} />
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

  const designerTab = (
    <Row className="g-3">
      <Col lg={7}>
        <div className="small text-secondary mb-2">
          {LAYER_MATCH_NOTE} That thickness is the slice pitch. The top row is the bottom of the bar.
        </div>
        {layerCm === null && (
          <Alert variant="warning">
            <Alert.Heading className="h6">Layers must have the same thickness</Alert.Heading>
            {thicknessWarning(layerTotals)}
          </Alert>
        )}
        {editorGroups.map(([id, title]) => (
          <div key={id}>
            <LayerEditor
              title={title}
              rows={groups[id]}
              materialOptions={materialOptions}
              onChange={(rows) => setGroupRows(id, rows)}
            />
            <div className="mb-3 px-1">
              {materialLines(groups[id], specs, mixed).map((line) => (
                <div key={line} className="small text-secondary">
                  {line}
                </div>
              ))}
            </div>
          </div>
        ))}
      </Col>
      <Col lg={5}>
        <LayerChart groups={groups} layerCm={layerCm} specs={specs} mixed={mixed} />
      </Col>
    </Row>
  );

  const tabContent: Record<TabKey, React.ReactNode> = {
    overview: overviewTab,
    fuel: fuelTab,
    designer: designerTab,
  };

  return (
    <Container fluid className="py-3">
      <Row className="g-3">
        <Col lg={4} xl={3} className="controls">
          <h1 className="h5 mb-2">Hollow disk zone calculator</h1>
          {renderSlider("a", "shield moderator thickness (m)", fixed(1))}
          {renderSlider("abs", "shield absorber thickness (m)", fixed(2))}
          {renderSlider("refl", "reflector thickness (m)", fixed(1))}
          {renderSlider("b_pct", "b (%)", fixed(0, "%"))}
          {renderSlider("w", "w (rim width)", fixed(1))}
          {renderSlider("ratio_pct", "fuel / TPV", fixed(0, "%"))}
          {renderSlider("tpv_density", "TPV power density (W/cm²)", fixed(2))}
          {renderSlider("tpv_eff_pct", "TPV efficiency", fixed(0, "%"))}
          {layerCm === null ? (
            <Alert variant="warning" className="py-2 px-3 small my-2">
              <div className="fw-semibold">Layers must have the same thickness</div>
              {thicknessWarning(layerTotals)}
            </Alert>
          ) : (
            <div className="small text-secondary my-1">Layer thickness {layerCm.toFixed(2)} cm</div>
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

          <hr className="my-3" />

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Configuration name</Form.Label>
            <Form.Control size="sm" value={saveName} onChange={(event) => setSaveName(event.target.value)} />
          </Form.Group>
          <Button size="sm" variant="primary" className="w-100 mb-3" onClick={() => void onSave()}>
            Save
          </Button>

          {savedNames.length ? (
            <>
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Saved configurations</Form.Label>
                <div className="d-flex gap-2">
                  <Form.Select size="sm" value={choice} onChange={(event) => setChoice(event.target.value)}>
                    {savedNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </Form.Select>
                  <Button size="sm" variant="outline-danger" title="Delete this configuration" onClick={() => void onDelete()}>
                    Delete
                  </Button>
                </div>
              </Form.Group>
              <Button size="sm" variant="outline-primary" className="w-100" onClick={onLoad}>
                Load
              </Button>
            </>
          ) : (
            <div className="small text-secondary">No saved configurations yet.</div>
          )}
          {notice && (
            <Alert
              variant={notice.kind}
              dismissible
              className="py-2 px-3 small mt-2 mb-0"
              onClose={() => setNotice(null)}
            >
              {notice.text}
            </Alert>
          )}
          <div className="small text-secondary mt-2">Configurations are stored in the save folder.</div>
        </Col>

        <Col lg={8} xl={9}>
          <Tabs
            activeKey={tab}
            onSelect={(key) => {
              if (isTabKey(key)) setTab(key);
            }}
            mountOnEnter
            unmountOnExit
            className="mb-0"
          >
            {TAB_KEYS.map((key) => (
              <Tab key={key} eventKey={key} title={TAB_LABELS[key]} className="pt-3">
                {tabContent[key]}
              </Tab>
            ))}
          </Tabs>
        </Col>
      </Row>
    </Container>
  );
};

const App: React.FC = () => (
  <Routes>
    <Route path="/" element={<Explorer />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);

export default App;
