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
  /** When set, only draw these group ids (plus disk when present). */
  only?: string[];
};

type Segment = { name: string; cm: number; color: string; detail: string };

const LayerChart: React.FC<Props> = ({ groups, layerCm, specs, mixed, only }) => {
  const { columns, maxCm } = useMemo(() => {
    const cols: Array<{ title: string; segments: Segment[] }> = [];
    let tallest = 0;
    for (const [groupId, title, colors] of LAYER_GROUPS) {
      if (only && !only.includes(groupId)) continue;
      const stacked = [...(groups[groupId] ?? []), ...(groups.disk ?? [])] as LayerRow[];
      const segments: Segment[] = stacked.map((layer, i) => {
        const fact = materialFact(layer.name, specs, mixed);
        const color = fact?.color ?? LAYER_FALLBACK_COLORS[layer.name] ?? colors[i % colors.length];
        let detail = "";
        if (fact?.composition) {
          detail = fact.composition;
          if (fact.density != null) detail += ` · ${Number(fact.density.toPrecision(4))} g/cm³`;
        }
        return { name: layer.name, cm: layer.cm, color, detail };
      });
      const total = segments.reduce((sum, seg) => sum + seg.cm, 0);
      tallest = Math.max(tallest, total);
      cols.push({ title, segments });
    }
    return { columns: cols, maxCm: Math.max(tallest, 0.1) };
  }, [groups, specs, mixed, only]);

  const height = 420;
  const barWidth = 56;
  const gap = 28;
  const left = 48;
  const bottom = 56;
  const top = 28;
  const plotH = height - top - bottom;
  const width = left + columns.length * (barWidth + gap);

  return (
    <div className="border rounded p-2 bg-white">
      <div className="fw-semibold mb-1">
        {layerCm != null ? `Layer thickness ${layerCm.toFixed(2)} cm` : "Layers do not match"}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="layer-chart-svg">
        {columns.map((col, colIndex) => {
          const x = left + colIndex * (barWidth + gap);
          let y = top + plotH;
          return (
            <g key={col.title}>
              {col.segments.map((seg, segIndex) => {
                const h = (seg.cm / maxCm) * plotH;
                y -= h;
                return (
                  <g key={`${col.title}-${segIndex}`}>
                    <title>{`${seg.name}${seg.detail ? `\n${seg.detail}` : ""}\n${seg.cm.toFixed(3)} cm`}</title>
                    <rect x={x} y={y} width={barWidth} height={Math.max(h, 0.5)} fill={seg.color} stroke="#fff" />
                  </g>
                );
              })}
              <text
                x={x + barWidth / 2}
                y={height - 18}
                textAnchor="middle"
                fontSize={11}
                fill="#4d615b"
              >
                {col.title.replace(" layer", "")}
              </text>
            </g>
          );
        })}
        <line x1={left - 8} y1={top} x2={left - 8} y2={top + plotH} stroke="#94a3b8" />
        <text x={12} y={top + 4} fontSize={11} fill="#4d615b">
          cm
        </text>
        <text x={left - 12} y={top + plotH} textAnchor="end" fontSize={11} fill="#4d615b">
          0
        </text>
        <text x={left - 12} y={top + 4} textAnchor="end" fontSize={11} fill="#4d615b">
          {maxCm.toFixed(2)}
        </text>
      </svg>
    </div>
  );
};

export default LayerChart;
