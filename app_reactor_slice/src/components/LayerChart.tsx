import React, { useMemo } from "react";
import { LAYER_FALLBACK_COLORS, LAYER_GROUPS } from "../constants";
import type { LayerRow, MaterialSpec, MixedSpec } from "../geometry";
import type { Groups } from "../layers";
import { materialFact } from "../materials";

type Props = {
  groups: Groups;
  layerCm: number | null;
  specs: Record<string, MaterialSpec>;
  mixed: Record<string, MixedSpec>;
  /** When set, only draw these group ids. */
  only?: string[];
  /** The designer stacks the shared disk on every bar. The fuel preview does not. */
  includeDisk?: boolean;
  title?: string;
};

type Segment = { name: string; cm: number; color: string; detail: string };

const LayerChart: React.FC<Props> = ({ groups, layerCm, specs, mixed, only, includeDisk = true, title }) => {
  const { columns, maxCm, legend } = useMemo(() => {
    const cols: Array<{ title: string; segments: Segment[] }> = [];
    const seen = new Map<string, string>();
    let tallest = 0;
    for (const [groupId, groupTitle, colors] of LAYER_GROUPS) {
      if (only && !only.includes(groupId)) continue;
      const stacked = [
        ...(groups[groupId] ?? []),
        ...(includeDisk ? (groups.disk ?? []) : []),
      ] as LayerRow[];
      const segments: Segment[] = stacked.map((layer, i) => {
        const fact = materialFact(layer.name, specs, mixed);
        let color = fact?.color ?? LAYER_FALLBACK_COLORS[layer.name] ?? colors[i % colors.length];
        // Library graphite is black. The fuel preview uses the same mid gray as the compact.
        if (!includeDisk && layer.name === "Graphite" && (color === "black" || !color)) {
          color = "#78716c";
        }
        let detail = "";
        if (fact?.composition) {
          detail = fact.composition;
          if (fact.density != null) detail += ` · ${Number(fact.density.toPrecision(4))} g/cm³`;
        }
        if (!seen.has(layer.name)) seen.set(layer.name, color);
        return { name: layer.name, cm: layer.cm, color, detail };
      });
      const total = segments.reduce((sum, seg) => sum + seg.cm, 0);
      tallest = Math.max(tallest, total);
      cols.push({ title: groupTitle, segments });
    }
    return {
      columns: cols,
      maxCm: Math.max(tallest, 0.1),
      legend: [...seen.entries()].map(([name, color]) => ({ name, color })),
    };
  }, [groups, specs, mixed, only, includeDisk]);

  const preview = !includeDisk && columns.length === 1;
  const height = includeDisk ? 420 : 220;
  const barWidth = preview ? 168 : columns.length === 1 ? 160 : 56;
  const gap = 28;
  const left = 56;
  const bottom = preview ? 28 : 48;
  const top = 8;
  const plotH = height - top - bottom;
  const width = preview ? 520 : left + Math.max(columns.length, 1) * (barWidth + gap) + 24;
  const heading =
    title ?? (layerCm != null ? `Layer thickness ${layerCm.toFixed(2)} cm` : "Layers do not match");
  const tickCount = 5;

  return (
    <div className="border rounded p-2 bg-white">
      <div className="fw-semibold mb-1">{heading}</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="layer-chart-svg">
        {Array.from({ length: tickCount + 1 }, (_, i) => {
          const value = (maxCm * i) / tickCount;
          const y = top + plotH - (i / tickCount) * plotH;
          return (
            <g key={value}>
              <line x1={left - 6} y1={y} x2={left} y2={y} stroke="#94a3b8" />
              <text x={left - 10} y={y} textAnchor="end" dominantBaseline="middle" fontSize={11} fill="#4d615b">
                {value.toFixed(2)}
              </text>
            </g>
          );
        })}
        <line x1={left} y1={top} x2={left} y2={top + plotH} stroke="#94a3b8" />
        <text
          x={16}
          y={top + plotH / 2}
          transform={`rotate(-90 16 ${top + plotH / 2})`}
          textAnchor="middle"
          fontSize={11}
          fill="#4d615b"
        >
          cm
        </text>
        {columns.map((col, colIndex) => {
          const x = left + 24 + colIndex * (barWidth + gap);
          let y = top + plotH;
          return (
            <g key={col.title}>
              {col.segments.map((seg, segIndex) => {
                const h = (seg.cm / maxCm) * plotH;
                y -= h;
                return (
                  <g key={`${col.title}-${segIndex}`}>
                    <title>{`${seg.name}${seg.detail ? `\n${seg.detail}` : ""}\n${seg.cm.toFixed(3)} cm`}</title>
                    <rect x={x} y={y} width={barWidth} height={Math.max(h, 0)} fill={seg.color} />
                  </g>
                );
              })}
              <text x={x + barWidth / 2} y={height - 16} textAnchor="middle" fontSize={12} fill="#4d615b">
                {col.title}
              </text>
            </g>
          );
        })}
      </svg>
      {includeDisk ? null : (
        <div className="d-flex flex-wrap gap-3 small text-secondary mt-1">
          {legend.map((item) => (
            <span key={item.name} className="line-chart-key">
              <i style={{ background: item.color }} />
              {item.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default LayerChart;
