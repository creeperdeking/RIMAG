import React, { useEffect, useMemo, useRef, useState } from "react";
import { ZONE_COLORS } from "../constants";
import {
  absorberFront,
  centerCuts,
  type Point,
  type ZoneLayout,
} from "../geometry";

function sectorOutline(rIn: number, rOut: number, startDeg: number, endDeg: number, n = 96): Point[] {
  let end = endDeg;
  if (end < startDeg) end += 360;
  const points: Point[] = [];
  for (let i = 0; i < n; i += 1) {
    const deg = startDeg + ((end - startDeg) * i) / (n - 1);
    const rad = (deg * Math.PI) / 180;
    points.push([rOut * Math.cos(rad), rOut * Math.sin(rad)]);
  }
  for (let i = n - 1; i >= 0; i -= 1) {
    const deg = startDeg + ((end - startDeg) * i) / (n - 1);
    const rad = (deg * Math.PI) / 180;
    points.push([rIn * Math.cos(rad), rIn * Math.sin(rad)]);
  }
  return points;
}

function rotatePoints(points: Point[], rotDeg: number): Point[] {
  const th = (rotDeg * Math.PI) / 180;
  const c = Math.cos(th);
  const s = Math.sin(th);
  return points.map(([x, y]) => [c * x - s * y, s * x + c * y]);
}

function translate(points: Point[], cx: number, cy: number): Point[] {
  return points.map(([x, y]) => [x + cx, y + cy]);
}

function toPath(points: Point[]): string {
  if (!points.length) return "";
  return `${points.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ")} Z`;
}

function centerShieldCut(r: number, yLine: number, n = 120): { points: Point[]; chord: [Point, Point] | null } {
  if (yLine <= -r + 1e-9) {
    const points: Point[] = [];
    for (let i = 0; i < n; i += 1) {
      const t = (2 * Math.PI * i) / (n - 1);
      points.push([r * Math.cos(t), r * Math.sin(t)]);
    }
    return { points, chord: null };
  }
  const y = Math.min(yLine, r - 1e-9);
  const halfX = Math.sqrt(Math.max(r * r - y * y, 0));
  let right = (Math.atan2(y, halfX) * 180) / Math.PI;
  let left = (Math.atan2(y, -halfX) * 180) / Math.PI;
  if (left < right) left += 360;
  const points: Point[] = [];
  for (let i = 0; i < n; i += 1) {
    const deg = right + ((left - right) * i) / (n - 1);
    const rad = (deg * Math.PI) / 180;
    points.push([r * Math.cos(rad), r * Math.sin(rad)]);
  }
  return { points, chord: [[halfX, y], [-halfX, y]] };
}

export function columnPoses(n: number, rOuter: number): Array<[number, number, number]> {
  const apart = 2 * rOuter;
  if (n <= 1) return [[0, 0, 0]];
  if (n === 2) return [[0, apart / 2, 180], [0, -apart / 2, 0]];
  const radius = apart / Math.sqrt(3);
  const poses: Array<[number, number, number]> = [];
  for (let k = 0; k < 3; k += 1) {
    const theta = -90 + k * 120;
    poses.push([
      radius * Math.cos((theta * Math.PI) / 180),
      radius * Math.sin((theta * Math.PI) / 180),
      theta + 90,
    ]);
  }
  return poses;
}

function polar(r: number, deg: number): Point {
  const rad = (deg * Math.PI) / 180;
  return [r * Math.cos(rad), r * Math.sin(rad)];
}

type Props = {
  layout: ZoneLayout;
  showDims: boolean;
  columns: number;
};

const ZoneChart: React.FC<Props> = ({ layout, showDims, columns }) => {
  const { paths, lines, dots, dot, labels, reach, legend } = useMemo(() => {
    const fuelHalf = (layout.fuelAngle * 180) / Math.PI / 2;
    const oppHalf = (layout.oppositeAngle * 180) / Math.PI / 2;
    const ri = layout.rInner;
    const ro = layout.rOuter;
    let box = ro * 1.3;
    for (const [px, py] of columnPoses(columns, ro)) {
      box = Math.max(box, Math.hypot(px, py) + ro * 1.2);
    }
    // Coordinates are metres. A raw stroke of 1.5 would be 1.5 m wide and cover the rim.
    const hairline = box * 0.0035;
    const zoneEdge = box * 0.004;
    const dash = `${box * 0.018} ${box * 0.012}`;
    const dot = box * 0.012;

    const drawn: Array<{ d: string; fill: string; stroke?: string; strokeWidth?: number; key: string }> = [];
    const strokeLines: Array<{ x1: number; y1: number; x2: number; y2: number; color: string; width: number; dash?: string; key: string }> = [];
    const dots: Array<{ x: number; y: number; key: string }> = [];
    const dimLabels: Array<{ x: number; y: number; text: string; key: string }> = [];
    const legendItems: Array<{ name: string; color: string }> = [];
    const seen = new Set<string>();

    const addLegend = (name: string, color: string) => {
      if (seen.has(name)) return;
      seen.add(name);
      legendItems.push({ name, color });
    };

    columnPoses(columns, ro).forEach(([cx, cy, rot], diskIndex) => {
      const fuel: [number, number] = [90 - fuelHalf + rot, 90 + fuelHalf + rot];
      const opposite: [number, number] = [270 - oppHalf + rot, 270 + oppHalf + rot];
      const reflDeg = (layout.reflectorAngle * 180) / Math.PI;
      const shieldDeg = (layout.gapAngle * 180) / Math.PI;
      const absDeg = (layout.absorberAngle * 180) / Math.PI;
      const reflLeft: [number, number] = [fuel[1], fuel[1] + reflDeg];
      const shieldLeft: [number, number] = [reflLeft[1], reflLeft[1] + shieldDeg];
      const absLeft: [number, number] = [shieldLeft[1], shieldLeft[1] + absDeg];
      const reflRight: [number, number] = [fuel[0] - reflDeg, fuel[0]];
      const shieldRight: [number, number] = [reflRight[0] - shieldDeg, reflRight[0]];
      const absRight: [number, number] = [shieldRight[0] - absDeg, shieldRight[0]];

      const edges = centerCuts(layout);
      const cuts: Array<[keyof typeof ZONE_COLORS, string, number]> = [["gap", "Shield moderator", edges.moderatorY]];
      if (edges.reflectorY != null) cuts.push(["reflector", "Reflector", edges.reflectorY]);
      for (const [colorKey, name, yLine] of cuts) {
        const { points, chord } = centerShieldCut(ri, yLine);
        const moved = translate(rotatePoints(points, rot), cx, cy);
        drawn.push({
          d: toPath(moved),
          fill: ZONE_COLORS[colorKey],
          key: `cut-${diskIndex}-${colorKey}`,
        });
        addLegend(name, ZONE_COLORS[colorKey]);
        if (chord) {
          const [[x0, y0], [x1, y1]] = translate(rotatePoints(chord, rot), cx, cy);
          strokeLines.push({
            x1: x0,
            y1: y0,
            x2: x1,
            y2: y1,
            color: "#1e293b",
            width: hairline,
            key: `chord-${diskIndex}-${colorKey}`,
          });
        }
      }

      const zones: Array<{ span: [number, number]; color: string; name: string; angle: number }> = [
        { span: fuel, color: ZONE_COLORS.fuel, name: "Fuel", angle: layout.fuelAngle },
        { span: opposite, color: ZONE_COLORS.opposite, name: "TPV", angle: layout.oppositeAngle },
        { span: reflLeft, color: ZONE_COLORS.reflector, name: "Reflector", angle: layout.reflectorAngle },
        { span: reflRight, color: ZONE_COLORS.reflector, name: "Reflector", angle: layout.reflectorAngle },
        { span: shieldLeft, color: ZONE_COLORS.gap, name: "Shield moderator", angle: layout.gapAngle },
        { span: shieldRight, color: ZONE_COLORS.gap, name: "Shield moderator", angle: layout.gapAngle },
        { span: absLeft, color: ZONE_COLORS.absorber, name: "Shield absorber", angle: layout.absorberAngle },
        { span: absRight, color: ZONE_COLORS.absorber, name: "Shield absorber", angle: layout.absorberAngle },
      ];
      zones.forEach((zone, index) => {
        if (zone.angle <= 1e-9) return;
        const pts = translate(sectorOutline(ri, ro, zone.span[0], zone.span[1]), cx, cy);
        drawn.push({
          d: toPath(pts),
          fill: zone.color,
          stroke: "white",
          strokeWidth: zoneEdge,
          key: `zone-${diskIndex}-${index}`,
        });
        addLegend(zone.name, zone.color);
      });

      for (const r of [ri, ro]) {
        const circle: Point[] = [];
        for (let i = 0; i <= 360; i += 1) {
          const rad = (i * Math.PI) / 180;
          circle.push([cx + r * Math.cos(rad), cy + r * Math.sin(rad)]);
        }
        drawn.push({
          d: toPath(circle),
          fill: "none",
          stroke: "#1e293b",
          strokeWidth: hairline,
          key: `circle-${diskIndex}-${r}`,
        });
      }

      const front = absorberFront(layout);
      if (front) {
        const closed = [...front, front[0]];
        const pts = translate(rotatePoints(closed, rot), cx, cy);
        drawn.push({
          d: toPath(pts),
          fill: ZONE_COLORS.absorber,
          stroke: "#1e293b",
          strokeWidth: hairline,
          key: `absfront-${diskIndex}`,
        });
      }

      if (showDims) {
        let dimSpans: Array<{ span: [number, number]; label: string; length: number }> = [
          { span: shieldLeft, label: "shield moderator thickness", length: layout.a },
          { span: shieldRight, label: "shield moderator thickness", length: layout.a },
        ];
        if (layout.absorberAngle > 1e-9) {
          dimSpans.push(
            { span: absLeft, label: "shield absorber thickness", length: layout.absorber },
            { span: absRight, label: "shield absorber thickness", length: layout.absorber },
          );
        }
        if (layout.reflectorAngle > 1e-9) {
          dimSpans = [
            { span: reflLeft, label: "reflector thickness", length: layout.reflector },
            { span: reflRight, label: "reflector thickness", length: layout.reflector },
            ...dimSpans,
          ];
        }
        dimSpans.forEach((dim, index) => {
          const [x0, y0] = polar(ri, dim.span[0]);
          const [x1, y1] = polar(ri, dim.span[1]);
          strokeLines.push({
            x1: x0 + cx,
            y1: y0 + cy,
            x2: x1 + cx,
            y2: y1 + cy,
            color: "#dc2626",
            width: hairline * 1.4,
            dash,
            key: `dim-${diskIndex}-${index}`,
          });
          dots.push({ x: x0 + cx, y: y0 + cy, key: `dot-a-${diskIndex}-${index}` });
          dots.push({ x: x1 + cx, y: y1 + cy, key: `dot-b-${diskIndex}-${index}` });
          if (diskIndex === 0 && index % 2 === 0) addLegend(dim.label, "#dc2626");
        });
      }
    });

    if (showDims && columns === 1) {
      const yAfterRefl = ri - layout.reflector;
      const yAfterShield = yAfterRefl - layout.a;
      const dx = -ri * 0.08;
      const dimParts: Array<[number, number, string]> = [];
      if (layout.reflector > 1e-9) dimParts.push([ri, yAfterRefl, "refl"]);
      dimParts.push([yAfterRefl, yAfterShield, "mod"]);
      if (layout.absorber > 1e-9) {
        const yAbsFar = Math.min(ri, -ri + layout.absorber);
        dimParts.push([-ri, yAbsFar, "abs"]);
        const yGap = centerCuts(layout).moderatorY;
        if (yGap > yAbsFar + 1e-6) dimParts.push([yAbsFar, yGap, "b"]);
      } else {
        dimParts.push([yAfterShield, -ri, "b"]);
      }
      dimParts.forEach(([yFrom, yTo, label], index) => {
        if (Math.abs(yFrom - yTo) < 1e-9) return;
        strokeLines.push({
          x1: dx,
          y1: yFrom,
          x2: dx,
          y2: yTo,
          color: "#334155",
          width: hairline,
          key: `vdim-${index}`,
        });
        dimLabels.push({
          x: dx - ri * 0.12,
          y: (yFrom + yTo) / 2,
          text: label,
          key: `vlbl-${index}`,
        });
      });
      const xDim = ro * 1.12;
      strokeLines.push({ x1: xDim, y1: -ro, x2: xDim, y2: -ri, color: "#334155", width: hairline, key: "w-dim" });
      dimLabels.push({ x: xDim + ro * 0.08, y: -(ri + ro) / 2, text: "w", key: "w-lbl" });
      for (const y of [-ri, -ro]) {
        strokeLines.push({
          x1: 0,
          y1: y,
          x2: xDim,
          y2: y,
          color: "#334155",
          width: hairline,
          dash,
          key: `w-guide-${y}`,
        });
      }
    }

    return { paths: drawn, lines: strokeLines, dots, dot, labels: dimLabels, reach: box, legend: legendItems };
  }, [layout, showDims, columns]);

  const home = useMemo(
    () => ({ x: -reach, y: -reach, w: reach * 2, h: reach * 2 }),
    [reach],
  );
  const [frame, setFrame] = useState<typeof home | null>(null);
  const [panning, setPanning] = useState(false);
  const view = frame ?? home;
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; frame: typeof home } | null>(null);

  useEffect(() => {
    setFrame(null);
  }, [home]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const px = (event.clientX - rect.left) / rect.width;
      const py = (event.clientY - rect.top) / rect.height;
      const factor = Math.exp(event.deltaY * 0.0012);
      setFrame((current) => {
        const base = current ?? home;
        const w = Math.min(home.w * 12, Math.max(home.w * 0.08, base.w * factor));
        const h = base.h * (w / base.w);
        const cx = base.x + px * base.w;
        const cy = base.y + py * base.h;
        return { x: cx - px * w, y: cy - py * h, w, h };
      });
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [home]);

  const zoomAboutCenter = (factor: number) => {
    setFrame((current) => {
      const base = current ?? home;
      const w = Math.min(home.w * 12, Math.max(home.w * 0.08, base.w * factor));
      const h = base.h * (w / base.w);
      const cx = base.x + base.w / 2;
      const cy = base.y + base.h / 2;
      return { x: cx - w / 2, y: cy - h / 2, w, h };
    });
  };

  return (
    <div className="zone-chart border rounded p-2 bg-white">
      <div className="zone-chart-tools">
        <button type="button" title="Zoom in" onClick={() => zoomAboutCenter(0.8)}>
          +
        </button>
        <button type="button" title="Zoom out" onClick={() => zoomAboutCenter(1.25)}>
          −
        </button>
        <button type="button" title="Reset view" onClick={() => setFrame(null)}>
          ⌂
        </button>
      </div>
      <svg
        ref={svgRef}
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        className={panning ? "zone-chart-svg is-panning" : "zone-chart-svg"}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          drag.current = { x: event.clientX, y: event.clientY, frame: view };
          setPanning(true);
          try {
            event.currentTarget.setPointerCapture(event.pointerId);
          } catch {
            /* Pointer capture is unavailable for this event. Drag still tracks the move. */
          }
        }}
        onPointerMove={(event) => {
          const start = drag.current;
          const rect = event.currentTarget.getBoundingClientRect();
          if (!start || rect.width <= 0 || rect.height <= 0) return;
          const dx = ((event.clientX - start.x) / rect.width) * start.frame.w;
          const dy = ((event.clientY - start.y) / rect.height) * start.frame.h;
          setFrame({
            x: start.frame.x - dx,
            y: start.frame.y - dy,
            w: start.frame.w,
            h: start.frame.h,
          });
        }}
        onPointerUp={() => {
          drag.current = null;
          setPanning(false);
        }}
        onPointerCancel={() => {
          drag.current = null;
          setPanning(false);
        }}
        onDoubleClick={() => setFrame(null)}
      >
        <rect x={view.x} y={view.y} width={view.w} height={view.h} fill="white" />
        {/* Math y is up; SVG y is down. Flip so fuel sits the same way as the Python chart. */}
        <g transform="scale(1,-1)">
          {paths.map((path) => (
            <path
              key={path.key}
              d={path.d}
              fill={path.fill}
              stroke={path.stroke ?? "none"}
              strokeWidth={path.strokeWidth ?? 0}
              strokeLinejoin="round"
            />
          ))}
          {lines.map((line) => (
            <line
              key={line.key}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke={line.color}
              strokeWidth={line.width}
              strokeDasharray={line.dash}
              strokeLinecap="round"
            />
          ))}
          {dots.map((mark) => (
            <circle key={mark.key} cx={mark.x} cy={mark.y} r={dot} fill="#dc2626" />
          ))}
          {labels.map((label) => (
            <g key={label.key} transform={`translate(${label.x},${label.y}) scale(1,-1)`}>
              <text
                fill="#334155"
                fontSize={reach * 0.045}
                fontStyle="italic"
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {label.text}
              </text>
            </g>
          ))}
        </g>
      </svg>
      <div className="d-flex flex-wrap gap-3 justify-content-center mt-2 small text-secondary">
        {legend.map((item) => (
          <span key={item.name} className="line-chart-key">
            <i style={{ background: item.color }} />
            {item.name}
          </span>
        ))}
      </div>
    </div>
  );
};

export default ZoneChart;
