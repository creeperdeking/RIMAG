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
        viewBox={`${-pad} ${-pad} ${width + pad * 2} ${diameter + pad * 2}`}
        className="compact-section-svg"
      >
        <path d={path} fill={wallColor} stroke="#d4d4d4" strokeWidth={0.4} />
        {centers.map((center) => (
          <g key={center}>
            {usable > 0 && (
              <circle cx={center} cy={radius} r={usable} fill={matrixColor} stroke="none" />
            )}
            {particles.map(([x, y, particleR, kernelR], index) => (
              <g key={`${center}-${index}`}>
                <circle
                  cx={center + x}
                  cy={radius + y}
                  r={particleR}
                  fill="#a8a29e"
                  stroke="#57534e"
                  strokeWidth={0.15}
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
                strokeWidth={0.35}
                strokeDasharray="1.2 1"
              />
            )}
          </g>
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
