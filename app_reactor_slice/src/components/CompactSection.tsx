import React, { useMemo } from "react";
import { trisoParticleLayout, type MaterialSpec, type MixedSpec } from "../geometry";
import { materialFact } from "../materials";

type Props = {
  diameterMm: number;
  wallMarginMm: number;
  spacingMm: number;
  packingPct: number;
  hmParticlePct: number;
  specs: Record<string, MaterialSpec>;
  mixed: Record<string, MixedSpec>;
};

const CompactSection: React.FC<Props> = ({
  diameterMm,
  wallMarginMm,
  spacingMm,
  packingPct,
  hmParticlePct,
  specs,
  mixed,
}) => {
  const drawing = useMemo(() => {
    const graphite = materialFact("Graphite", specs, mixed);
    const uranium = materialFact("Uranium Dioxide", specs, mixed);
    let wallColor = "#292524";
    let matrixColor = "#78716c";
    if (graphite && graphite.color !== "black") {
      matrixColor = graphite.color;
      wallColor = graphite.color;
    }
    const uraniumColor = uranium?.color ?? "green";
    const diameter = diameterMm;
    const spacing = Math.max(spacingMm, 0);
    const margin = Math.max(wallMarginMm, 0);
    const pitch = diameter + spacing;
    const radius = diameter / 2;
    const usable = Math.max(radius - margin, 0);
    const particles = trisoParticleLayout(diameter, margin, packingPct, hmParticlePct);
    const left = radius;
    const right = radius + pitch;
    const width = diameter + pitch;
    const steps = 64;
    const outline: Array<[number, number]> = [];
    for (let i = 0; i < steps; i += 1) {
      const angle = Math.PI / 2 + (Math.PI * i) / (steps - 1);
      outline.push([left + radius * Math.cos(angle), radius + radius * Math.sin(angle)]);
    }
    for (let i = 0; i < steps; i += 1) {
      const angle = -Math.PI / 2 + (Math.PI * i) / (steps - 1);
      outline.push([right + radius * Math.cos(angle), radius + radius * Math.sin(angle)]);
    }
    outline.push([left, diameter]);
    const pad = Math.max(diameter * 0.08, 0.4);
    return {
      wallColor,
      matrixColor,
      uraniumColor,
      diameter,
      radius,
      usable,
      particles,
      centers: [left, right] as const,
      outline,
      pad,
      width,
    };
  }, [diameterMm, wallMarginMm, spacingMm, packingPct, hmParticlePct, specs, mixed]);

  const { wallColor, matrixColor, uraniumColor, diameter, radius, usable, particles, centers, outline, pad, width } =
    drawing;
  const path = outline.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(" ") + " Z";

  return (
    <div className="border rounded p-2 bg-white">
      <div className="fw-semibold mb-1">Compact cross section</div>
      <svg
        viewBox={`${-pad * 2.6} ${-pad} ${width + pad * 3.6} ${diameter + pad * 2.4}`}
        className="compact-section-svg"
      >
        <path d={path} fill={wallColor} stroke="#d4d4d4" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        {centers.map((center) => (
          <g key={center}>
            {usable > 0 && <circle cx={center} cy={radius} r={usable} fill={matrixColor} stroke="none" />}
            {particles.map(([x, y, particleR, kernelR], index) => (
              <g key={`${center}-${index}`}>
                <circle
                  cx={center + x}
                  cy={radius + y}
                  r={particleR}
                  fill="#a8a29e"
                  stroke="#57534e"
                  strokeWidth={0.6}
                  vectorEffect="non-scaling-stroke"
                />
                {kernelR > 0 && (
                  <circle cx={center + x} cy={radius + y} r={kernelR} fill={uraniumColor} stroke="none" />
                )}
              </g>
            ))}
            {usable > 0 && (
              <circle
                cx={center}
                cy={radius}
                r={usable}
                fill="none"
                stroke="#fbbf24"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                vectorEffect="non-scaling-stroke"
              />
            )}
          </g>
        ))}
        {Array.from({ length: Math.floor(diameter / 2) + 1 }, (_, i) => i * 2).map((mm) => (
          <text
            key={`y-${mm}`}
            x={-pad * 0.35}
            y={diameter - mm}
            textAnchor="end"
            dominantBaseline="middle"
            fontSize={pad * 0.55}
            fill="#4d615b"
          >
            {mm}
          </text>
        ))}
        <text x={-pad * 2.05} y={diameter / 2} textAnchor="middle" fontSize={pad * 0.5} fill="#4d615b" transform={`rotate(-90 ${-pad * 2.05} ${diameter / 2})`}>
          mm
        </text>
        {Array.from({ length: Math.floor(width / 5) + 1 }, (_, i) => i * 5).map((mm) => (
          <text
            key={`x-${mm}`}
            x={mm}
            y={diameter + pad * 0.7}
            textAnchor="middle"
            fontSize={pad * 0.55}
            fill="#4d615b"
          >
            {mm}
          </text>
        ))}
      </svg>
      <div className="d-flex flex-wrap gap-3 small text-secondary mt-1">
        <span className="line-chart-key">
          <i style={{ background: matrixColor }} />
          Graphite
        </span>
        <span className="line-chart-key">
          <i style={{ background: uraniumColor }} />
          Uranium dioxide
        </span>
      </div>
    </div>
  );
};

export default CompactSection;
