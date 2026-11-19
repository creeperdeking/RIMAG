import React, { useEffect, useRef, useState } from "react";
import { Alert, Button, Col, Form, Row, Spinner } from "react-bootstrap";

type Basis = "xy" | "xz" | "yz";

type SuggestedView = {
  width: number;
  height: number;
  origin: [number, number, number];
};

type GeometryStatus = {
  ready: boolean;
  hasGeometry: boolean;
  hasMaterials: boolean;
  hasDefaults?: boolean;
  fingerprint?: string;
  suggested?: Partial<Record<Basis, SuggestedView>> | null;
};

type PlotView = {
  basis: Basis;
  origin: [number, number, number];
  width: number;
  height: number;
  pixels: number;
};

type DragRect = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
};

type CacheEntry = {
  url: string;
  fingerprint: string;
};

type ImageTool = "zoom" | "ruler";

const DEFAULT_PIXELS = 600;
const MIN_DRAG_PX = 10;
const MIN_RULER_PX = 4;

function suggestedForBasis(status: GeometryStatus | null, basis: Basis): SuggestedView | null {
  const view = status?.suggested?.[basis];
  if (!view) return null;
  if (!(view.width > 0 && view.height > 0)) return null;
  return view;
}

function axesForBasis(basis: Basis): { u: 0 | 1 | 2; v: 0 | 1 | 2 } {
  if (basis === "xy") return { u: 0, v: 1 };
  if (basis === "xz") return { u: 0, v: 2 };
  return { u: 1, v: 2 };
}

function roundCoord(value: number): number {
  return Number(value.toPrecision(9));
}

function viewKey(view: PlotView): string {
  return JSON.stringify({
    basis: view.basis,
    origin: view.origin.map(roundCoord),
    width: roundCoord(view.width),
    height: roundCoord(view.height),
    pixels: view.pixels,
  });
}

function viewsEqual(a: PlotView, b: PlotView): boolean {
  return viewKey(a) === viewKey(b);
}

/** Image fraction (u right, v down) → world cm. OpenMC: top of image = +v. */
function worldFromImageFraction(
  view: PlotView,
  u: number,
  v: number,
): [number, number, number] {
  const { u: ui, v: vi } = axesForBasis(view.basis);
  const point: [number, number, number] = [...view.origin];
  point[ui] = view.origin[ui] + (u - 0.5) * view.width;
  point[vi] = view.origin[vi] + (0.5 - v) * view.height;
  return point;
}

function formatWorldPoint(point: [number, number, number]): string {
  const fmt = (value: number) => {
    const abs = Math.abs(value);
    if (abs !== 0 && (abs < 1e-3 || abs >= 1e5)) return value.toExponential(4);
    return value.toPrecision(6);
  };
  return `(${fmt(point[0])}, ${fmt(point[1])}, ${fmt(point[2])}) cm`;
}

function distanceCm(a: [number, number, number], b: [number, number, number]): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function formatLength(cm: number): string {
  if (!Number.isFinite(cm)) return "—";
  const abs = Math.abs(cm);
  if (abs !== 0 && abs < 0.1) return `${(cm * 10).toPrecision(4)} mm`;
  if (abs < 100) return `${cm.toPrecision(4)} cm`;
  return `${(cm / 100).toPrecision(4)} m`;
}

/** Pixel line on the displayed image → world length in the plot plane. */
function measureLengthCm(view: PlotView, line: DragRect, imageWidthPx: number, imageHeightPx: number): number | null {
  if (imageWidthPx < 1 || imageHeightPx < 1) return null;
  const a = worldFromImageFraction(view, line.x0 / imageWidthPx, line.y0 / imageHeightPx);
  const b = worldFromImageFraction(view, line.x1 / imageWidthPx, line.y1 / imageHeightPx);
  return distanceCm(a, b);
}

/** Map an image-fraction rectangle to a new OpenMC plot view (OpenMC: top = +v). */
function viewFromImageSelection(
  current: PlotView,
  u0: number,
  v0: number,
  u1: number,
  v1: number,
): PlotView | null {
  const left = Math.min(u0, u1);
  const right = Math.max(u0, u1);
  const top = Math.min(v0, v1);
  const bottom = Math.max(v0, v1);
  if (right - left < 1e-6 || bottom - top < 1e-6) return null;

  const { u: ui, v: vi } = axesForBasis(current.basis);
  const worldLeft = current.origin[ui] + (left - 0.5) * current.width;
  const worldRight = current.origin[ui] + (right - 0.5) * current.width;
  const worldTop = current.origin[vi] + (0.5 - top) * current.height;
  const worldBottom = current.origin[vi] + (0.5 - bottom) * current.height;

  const newWidth = worldRight - worldLeft;
  const newHeight = worldTop - worldBottom;
  if (newWidth <= 0 || newHeight <= 0) return null;

  const origin: [number, number, number] = [...current.origin];
  origin[ui] = (worldLeft + worldRight) / 2;
  origin[vi] = (worldTop + worldBottom) / 2;

  return {
    ...current,
    origin,
    width: newWidth,
    height: newHeight,
  };
}

const VisualisationTab: React.FC = () => {
  const [status, setStatus] = useState<GeometryStatus | null>(null);
  const [basis, setBasis] = useState<Basis>("xy");
  const [origin, setOrigin] = useState<[number, number, number]>([0, 0, 0]);
  const [width, setWidth] = useState(100);
  const [height, setHeight] = useState(100);
  const [pixels, setPixels] = useState(DEFAULT_PIXELS);
  const [autoSized, setAutoSized] = useState(true);
  const [plotting, setPlotting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [renderedView, setRenderedView] = useState<PlotView | null>(null);
  const [history, setHistory] = useState<PlotView[]>([]);
  const [drag, setDrag] = useState<DragRect | null>(null);
  const [measure, setMeasure] = useState<DragRect | null>(null);
  const [tool, setTool] = useState<ImageTool>("zoom");
  const [displaySize, setDisplaySize] = useState({ w: 0, h: 0 });
  const [cacheHint, setCacheHint] = useState<string | null>(null);
  const [hoverPoint, setHoverPoint] = useState<[number, number, number] | null>(null);

  const imgRef = useRef<HTMLImageElement | null>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const renderedViewRef = useRef<PlotView | null>(null);
  const cacheRef = useRef<Map<string, CacheEntry>>(new Map());
  const fingerprintRef = useRef<string | null>(null);

  useEffect(() => {
    renderedViewRef.current = renderedView;
  }, [renderedView]);

  const clearImageCache = () => {
    for (const entry of cacheRef.current.values()) {
      URL.revokeObjectURL(entry.url);
    }
    cacheRef.current.clear();
  };

  /** Drop cached PNGs when exported geometry/materials change. */
  const syncFingerprint = (fingerprint: string | undefined) => {
    if (!fingerprint) return;
    if (fingerprintRef.current && fingerprintRef.current !== fingerprint) {
      clearImageCache();
      setHistory([]);
      setRenderedView(null);
      setImageUrl(null);
      setCacheHint(null);
    }
    fingerprintRef.current = fingerprint;
  };

  const formView = (): PlotView => ({
    basis,
    origin,
    width,
    height,
    pixels,
  });

  const applyViewToForm = (view: PlotView) => {
    setBasis(view.basis);
    setOrigin([...view.origin]);
    setWidth(view.width);
    setHeight(view.height);
    setPixels(view.pixels);
  };

  const applySuggested = (nextBasis: Basis, fromStatus: GeometryStatus | null = status) => {
    const suggested = suggestedForBasis(fromStatus, nextBasis);
    if (!suggested) return false;
    setBasis(nextBasis);
    setOrigin([...suggested.origin]);
    setWidth(suggested.width);
    setHeight(suggested.height);
    setAutoSized(true);
    return true;
  };

  const showView = (view: PlotView, url: string, recordHistory: boolean, fromCache: boolean) => {
    const previous = renderedViewRef.current;
    if (recordHistory && previous && !viewsEqual(previous, view)) {
      setHistory((stack) => [...stack, previous]);
    }
    setRenderedView(view);
    applyViewToForm(view);
    setImageUrl(url);
    setMeasure(null);
    setDrag(null);
    setCacheHint(fromCache ? "Cached image (same view + geometry)." : null);
  };

  const setImageTool = (next: ImageTool) => {
    setTool(next);
    setDrag(null);
    dragStartRef.current = null;
    if (next !== "ruler") setMeasure(null);
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/geometry/status");
        const payload = (await response.json()) as GeometryStatus;
        if (!cancelled) {
          syncFingerprint(payload.fingerprint);
          setStatus(payload);
          applySuggested("xy", payload);
        }
      } catch (err) {
        if (!cancelled) {
          setStatus({ ready: false, hasGeometry: false, hasMaterials: false });
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    })();
    return () => {
      cancelled = true;
      clearImageCache();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount/unmount only
  }, []);

  const setOriginAxis = (index: 0 | 1 | 2, value: string) => {
    const next = Number(value);
    if (!Number.isFinite(next)) return;
    setOrigin((prev) => {
      const copy: [number, number, number] = [...prev];
      copy[index] = next;
      return copy;
    });
  };

  const runPlot = async (view: PlotView, recordHistory: boolean) => {
    setError(null);
    setDrag(null);
    setMeasure(null);

    // Refresh fingerprint before cache lookup (sim may have rewritten XMLs).
    try {
      const statusResponse = await fetch("/api/geometry/status");
      if (statusResponse.ok) {
        const payload = (await statusResponse.json()) as GeometryStatus;
        syncFingerprint(payload.fingerprint);
        setStatus(payload);
      }
    } catch {
      // continue; plot endpoint will fail clearly if geometry is gone
    }

    const fingerprint = fingerprintRef.current;
    const key = viewKey(view);
    const cached = fingerprint ? cacheRef.current.get(key) : undefined;
    if (cached && cached.fingerprint === fingerprint) {
      showView(view, cached.url, recordHistory, true);
      return;
    }

    setPlotting(true);
    setCacheHint(null);
    try {
      const response = await fetch("/api/geometry/plot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          basis: view.basis,
          origin: view.origin,
          width: view.width,
          height: view.height,
          pixels: view.pixels,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(payload.error || `Plot failed (${response.status})`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      const refreshed = await fetch("/api/geometry/status");
      let nextFingerprint = fingerprint;
      if (refreshed.ok) {
        const payload = (await refreshed.json()) as GeometryStatus;
        syncFingerprint(payload.fingerprint);
        setStatus(payload);
        nextFingerprint = payload.fingerprint ?? fingerprint;
      }

      if (nextFingerprint) {
        const old = cacheRef.current.get(key);
        if (old && old.url !== url) URL.revokeObjectURL(old.url);
        cacheRef.current.set(key, { url, fingerprint: nextFingerprint });
      }

      showView(view, url, recordHistory, false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPlotting(false);
    }
  };

  const onPlot = () => void runPlot(formView(), true);

  const onBack = () => {
    if (history.length === 0 || plotting) return;
    const previous = history[history.length - 1];
    setHistory((stack) => stack.slice(0, -1));
    void runPlot(previous, false);
  };

  const clientToImageFraction = (clientX: number, clientY: number) => {
    const img = imgRef.current;
    if (!img) return null;
    const rect = img.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    const u = (clientX - rect.left) / rect.width;
    const v = (clientY - rect.top) / rect.height;
    return {
      u: Math.min(1, Math.max(0, u)),
      v: Math.min(1, Math.max(0, v)),
      x: clientX - rect.left,
      y: clientY - rect.top,
    };
  };

  const onPointerDown = (event: React.PointerEvent) => {
    if (plotting || !renderedView || !imageUrl) return;
    updateHover(event.clientX, event.clientY);
    if (event.button !== 0) return;
    const hit = clientToImageFraction(event.clientX, event.clientY);
    if (!hit) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStartRef.current = { x: hit.x, y: hit.y };
    setDrag({ x0: hit.x, y0: hit.y, x1: hit.x, y1: hit.y });
  };

  const updateHover = (clientX: number, clientY: number) => {
    if (!renderedView) {
      setHoverPoint(null);
      return;
    }
    const hit = clientToImageFraction(clientX, clientY);
    if (!hit) {
      setHoverPoint(null);
      return;
    }
    setHoverPoint(worldFromImageFraction(renderedView, hit.u, hit.v));
  };

  const onPointerMove = (event: React.PointerEvent) => {
    updateHover(event.clientX, event.clientY);
    if (!dragStartRef.current) return;
    const hit = clientToImageFraction(event.clientX, event.clientY);
    if (!hit) return;
    setDrag({
      x0: dragStartRef.current.x,
      y0: dragStartRef.current.y,
      x1: hit.x,
      y1: hit.y,
    });
  };

  const syncDisplaySize = () => {
    const img = imgRef.current;
    if (!img) return;
    const next = { w: img.clientWidth, h: img.clientHeight };
    setDisplaySize((prev) => (prev.w === next.w && prev.h === next.h ? prev : next));
  };

  const finishDrag = (event: React.PointerEvent) => {
    const start = dragStartRef.current;
    dragStartRef.current = null;
    setDrag(null);
    if (!start || !renderedView || plotting) return;

    const hit = clientToImageFraction(event.clientX, event.clientY);
    if (!hit) return;

    const img = imgRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    syncDisplaySize();

    if (tool === "ruler") {
      const line: DragRect = { x0: start.x, y0: start.y, x1: hit.x, y1: hit.y };
      const px = Math.hypot(line.x1 - line.x0, line.y1 - line.y0);
      if (px < MIN_RULER_PX) {
        setMeasure(null);
        return;
      }
      setMeasure(line);
      return;
    }

    if (Math.abs(hit.x - start.x) < MIN_DRAG_PX || Math.abs(hit.y - start.y) < MIN_DRAG_PX) {
      return;
    }

    const next = viewFromImageSelection(
      renderedView,
      start.x / rect.width,
      start.y / rect.height,
      hit.x / rect.width,
      hit.y / rect.height,
    );
    if (!next) return;
    void runPlot(next, true);
  };

  useEffect(() => {
    if (!imageUrl) {
      setDisplaySize({ w: 0, h: 0 });
      return;
    }
    syncDisplaySize();
    const onResize = () => syncDisplaySize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- size sync when the PNG changes
  }, [imageUrl]);

  const ready = status?.ready === true;
  const activeLine = tool === "ruler" ? drag ?? measure : null;
  const selectionStyle =
    tool === "zoom" && drag
      ? {
          left: Math.min(drag.x0, drag.x1),
          top: Math.min(drag.y0, drag.y1),
          width: Math.abs(drag.x1 - drag.x0),
          height: Math.abs(drag.y1 - drag.y0),
        }
      : null;

  const rulerLengthCm =
    tool === "ruler" && activeLine && renderedView && displaySize.w > 0 && displaySize.h > 0
      ? measureLengthCm(renderedView, activeLine, displaySize.w, displaySize.h)
      : null;

  return (
    <Row className="g-3">
      <Col lg={4}>
        <div className="border rounded p-3 bg-white">
          <h2 className="h6 mb-3">OpenMC slice</h2>
          <p className="small text-secondary mb-3">
            Plots the latest <code>runs/default</code> geometry with OpenMC (same engine as openmc-plotter). Width and
            height default to the reactor bounding box for the chosen plane (fixes blank xz/yz views when Z is only one
            pitch tall). Zoom mode: drag a rectangle. Ruler mode: drag between two points for a length in cm. Matching
            views reuse a cached PNG until geometry changes.
          </p>

          <Form.Group className="mb-3">
            <Form.Label className="small mb-1">Image tool</Form.Label>
            <div className="btn-group w-100">
              <Button
                size="sm"
                variant={tool === "zoom" ? "primary" : "outline-secondary"}
                disabled={plotting}
                onClick={() => setImageTool("zoom")}
              >
                Zoom
              </Button>
              <Button
                size="sm"
                variant={tool === "ruler" ? "primary" : "outline-secondary"}
                disabled={plotting}
                onClick={() => setImageTool("ruler")}
              >
                Ruler
              </Button>
            </div>
            {tool === "ruler" && (
              <div className="d-flex justify-content-between align-items-baseline gap-2 mt-1">
                <div className="small text-secondary">
                  {rulerLengthCm != null
                    ? `Length ${formatLength(rulerLengthCm)}`
                    : "Drag on the image to measure."}
                </div>
                <Button
                  size="sm"
                  variant="link"
                  className="p-0 small"
                  disabled={!measure && !drag}
                  onClick={() => {
                    setMeasure(null);
                    setDrag(null);
                    dragStartRef.current = null;
                  }}
                >
                  Clear
                </Button>
              </div>
            )}
          </Form.Group>

          {!status && <div className="small text-secondary mb-2">Checking geometry…</div>}
          {status && !ready && (
            <Alert variant="warning" className="py-2 px-3 small">
              No <code>geometry.xml</code> / <code>materials.xml</code> yet. Run a simulation (render mode is
              enough) first.
            </Alert>
          )}

          <Form.Group className="mb-2">
            <Form.Label className="small mb-1">Basis</Form.Label>
            <Form.Select
              size="sm"
              value={basis}
              disabled={plotting}
              onChange={(event) => {
                const next = event.target.value as Basis;
                if (!applySuggested(next)) setBasis(next);
              }}
            >
              <option value="xy">xy</option>
              <option value="xz">xz</option>
              <option value="yz">yz</option>
            </Form.Select>
          </Form.Group>

          <Form.Label className="small mb-1">Origin (cm)</Form.Label>
          <Row className="g-2 mb-2">
            {(["X", "Y", "Z"] as const).map((label, index) => (
              <Col key={label} xs={4}>
                <Form.Control
                  size="sm"
                  type="number"
                  step="any"
                  value={origin[index]}
                  disabled={plotting}
                  onChange={(event) => setOriginAxis(index as 0 | 1 | 2, event.target.value)}
                  aria-label={`Origin ${label}`}
                />
              </Col>
            ))}
          </Row>

          <Row className="g-2 mb-2">
            <Col xs={6}>
              <Form.Label className="small mb-1">Width (cm)</Form.Label>
              <Form.Control
                size="sm"
                type="number"
                min={1}
                step="any"
                value={Number(width.toPrecision(6))}
                disabled={plotting}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  if (Number.isFinite(next) && next > 0) {
                    setWidth(next);
                    setAutoSized(false);
                  }
                }}
              />
            </Col>
            <Col xs={6}>
              <Form.Label className="small mb-1">Height (cm)</Form.Label>
              <Form.Control
                size="sm"
                type="number"
                min={1}
                step="any"
                value={Number(height.toPrecision(6))}
                disabled={plotting}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  if (Number.isFinite(next) && next > 0) {
                    setHeight(next);
                    setAutoSized(false);
                  }
                }}
              />
            </Col>
          </Row>
          <div className="small text-secondary mb-2">
            {status?.hasDefaults
              ? autoSized
                ? "Sized to envelope the reactor for this plane."
                : "Custom size (not the full-reactor default)."
              : "No plot_defaults.json yet — run a simulation to enable auto sizing."}
          </div>

          <Form.Group className="mb-3">
            <Form.Label className="small mb-1">Pixels (max side)</Form.Label>
            <Form.Control
              size="sm"
              type="number"
              min={16}
              max={1000}
              value={pixels}
              disabled={plotting}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isFinite(next)) setPixels(Math.max(16, Math.min(1000, Math.round(next))));
              }}
            />
          </Form.Group>

          <div className="d-flex flex-wrap gap-2">
            <Button size="sm" disabled={!ready || plotting} onClick={onPlot}>
              {plotting ? (
                <>
                  <Spinner animation="border" size="sm" className="me-2" />
                  Plotting…
                </>
              ) : (
                "Plot"
              )}
            </Button>
            <Button
              size="sm"
              variant="outline-secondary"
              disabled={plotting || !status?.hasDefaults}
              onClick={() => applySuggested(basis)}
            >
              Fit reactor
            </Button>
            <Button
              size="sm"
              variant="outline-secondary"
              disabled={plotting || history.length === 0}
              onClick={onBack}
            >
              Back
            </Button>
          </div>

          {cacheHint && <div className="small text-secondary mt-2">{cacheHint}</div>}

          {error && (
            <Alert variant="danger" className="py-2 px-3 small mt-3 mb-0">
              {error}
            </Alert>
          )}
        </div>
      </Col>

      <Col lg={8}>
        <div
          className="border rounded p-3 bg-white d-flex align-items-center justify-content-center"
          style={{ minHeight: "50vh" }}
        >
          {imageUrl ? (
            <div className="w-100 d-flex flex-column align-items-center">
              <div
                className="position-relative user-select-none"
                style={{
                  cursor: plotting ? "wait" : tool === "ruler" ? "crosshair" : "zoom-in",
                  touchAction: "none",
                }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={finishDrag}
                onPointerLeave={() => setHoverPoint(null)}
                onPointerCancel={() => {
                  dragStartRef.current = null;
                  setDrag(null);
                  setHoverPoint(null);
                }}
              >
                <img
                  ref={imgRef}
                  src={imageUrl}
                  alt={`OpenMC ${basis} slice`}
                  className="img-fluid d-block"
                  draggable={false}
                  style={{ maxHeight: "70vh", objectFit: "contain" }}
                  onLoad={syncDisplaySize}
                />
                {selectionStyle && (
                  <div
                    className="position-absolute border border-2 border-primary"
                    style={{
                      ...selectionStyle,
                      backgroundColor: "rgba(13, 110, 253, 0.15)",
                      pointerEvents: "none",
                    }}
                  />
                )}
                {activeLine && displaySize.w > 0 && displaySize.h > 0 && (
                  <svg
                    className="position-absolute top-0 start-0"
                    width={displaySize.w}
                    height={displaySize.h}
                    viewBox={`0 0 ${displaySize.w} ${displaySize.h}`}
                    style={{ pointerEvents: "none" }}
                    aria-hidden
                  >
                    <line
                      x1={activeLine.x0}
                      y1={activeLine.y0}
                      x2={activeLine.x1}
                      y2={activeLine.y1}
                      stroke="#0d6efd"
                      strokeWidth={2}
                      strokeLinecap="round"
                    />
                    <circle cx={activeLine.x0} cy={activeLine.y0} r={4} fill="#fff" stroke="#0d6efd" strokeWidth={2} />
                    <circle cx={activeLine.x1} cy={activeLine.y1} r={4} fill="#fff" stroke="#0d6efd" strokeWidth={2} />
                    {rulerLengthCm != null && (
                      <g
                        transform={`translate(${(activeLine.x0 + activeLine.x1) / 2}, ${(activeLine.y0 + activeLine.y1) / 2})`}
                      >
                        <rect
                          x={-42}
                          y={-22}
                          width={84}
                          height={20}
                          rx={4}
                          fill="rgba(255,255,255,0.92)"
                          stroke="#0d6efd"
                          strokeWidth={1}
                        />
                        <text
                          textAnchor="middle"
                          y={-7}
                          fill="#0d6efd"
                          fontSize={12}
                          fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
                        >
                          {formatLength(rulerLengthCm)}
                        </text>
                      </g>
                    )}
                  </svg>
                )}
              </div>
              <div className="small font-monospace text-secondary mt-2">
                {hoverPoint
                  ? `x, y, z = ${formatWorldPoint(hoverPoint)}`
                  : tool === "ruler"
                    ? "Drag between two points to measure. Hover for x, y, z (cm)."
                    : "Move the mouse over the image for x, y, z (cm). Drag a rectangle to zoom."}
                {tool === "ruler" && rulerLengthCm != null ? ` · ${formatLength(rulerLengthCm)}` : ""}
              </div>
            </div>
          ) : (
            <div className="text-secondary small text-center px-3">
              {ready ? "Choose a view and click Plot." : "Waiting for exported OpenMC geometry."}
            </div>
          )}
        </div>
      </Col>
    </Row>
  );
};

export default VisualisationTab;
