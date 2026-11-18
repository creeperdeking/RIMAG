import React, { useMemo } from "react";
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
  const { paths, lines, labels, reach, legend } = useMemo(() => {
    const fuelHalf = (layout.fuelAngle * 180) / Math.PI / 2;
    const oppHalf = (layout.oppositeAngle * 180) / Math.PI / 2;
    const ri = layout.rInner;
    const ro = layout.rOuter;
    const drawn: Array<{ d: string; fill: string; stroke?: string; strokeWidth?: number; key: string }> = [];
    const strokeLines: Array<{ x1: number; y1: number; x2: number; y2: number; color: string; dash?: string; key: string }> = [];
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
          strokeWidth: 1.5,
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
          strokeWidth: 1.5,
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
          strokeWidth: 1.5,
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
            dash: "4 3",
            key: `dim-${diskIndex}-${index}`,
          });
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
      strokeLines.push({ x1: xDim, y1: -ro, x2: xDim, y2: -ri, color: "#334155", key: "w-dim" });
      dimLabels.push({ x: xDim + ro * 0.08, y: -(ri + ro) / 2, text: "w", key: "w-lbl" });
      for (const y of [-ri, -ro]) {
        strokeLines.push({
          x1: 0,
          y1: y,
          x2: xDim,
          y2: y,
          color: "#334155",
          dash: "3 3",
          key: `w-guide-${y}`,
        });
      }
    }

    let box = ro * 1.3;
    for (const [cx, cy] of columnPoses(columns, ro)) {
      box = Math.max(box, Math.hypot(cx, cy) + ro * 1.2);
    }
    return { paths: drawn, lines: strokeLines, labels: dimLabels, reach: box, legend: legendItems };
  }, [layout, showDims, columns]);

  return (
    <div className="zone-chart border rounded p-2 bg-white">
      <svg viewBox={`${-reach} ${-reach} ${reach * 2} ${reach * 2}`} className="zone-chart-svg">
        {paths.map((path) => (
          <path
            key={path.key}
            d={path.d}
            fill={path.fill}
            stroke={path.stroke ?? "none"}
            strokeWidth={path.strokeWidth ?? 0}
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
            strokeWidth={1.5}
            strokeDasharray={line.dash}
          />
        ))}
        {labels.map((label) => (
          <text
            key={label.key}
            x={label.x}
            y={label.y}
            fill="#334155"
            fontSize={reach * 0.045}
            fontStyle="italic"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {label.text}
          </text>
        ))}
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
