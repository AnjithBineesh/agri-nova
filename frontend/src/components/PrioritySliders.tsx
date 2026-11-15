"use client";

export const OBJECTIVES = [
  { key: "soil_health", label: "Soil health improvement", hint: "Legumes, residue carbon, nutrient balance, family breaks" },
  { key: "water_conservation", label: "Water conservation", hint: "Less irrigation, more of the demand met by rain" },
  { key: "climate_resilience", label: "Climate resilience", hint: "Stays within limits under +1.5 °C and 15% less rain" },
  { key: "economic_potential", label: "Economic potential", hint: "Needs your local prices and costs" },
  { key: "crop_diversity", label: "Crop diversity", hint: "Number and balance of crop families" },
] as const;

export type Weights = Record<string, number>;

/** Change one weight and rescale the others so the total stays exactly 100. */
export function rebalance(w: Weights, key: string, value: number): Weights {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const others = OBJECTIVES.map((o) => o.key).filter((k) => k !== key);
  const rest = others.reduce((a, k) => a + (w[k] ?? 0), 0);
  const remaining = 100 - v;
  const out: Weights = { [key]: v };
  let assigned = 0;
  others.forEach((k, i) => {
    const share = i === others.length - 1 ? remaining - assigned
      : Math.round(rest > 0 ? ((w[k] ?? 0) / rest) * remaining : remaining / others.length);
    out[k] = Math.max(0, share);
    assigned += out[k];
  });
  const total = Object.values(out).reduce((a, b) => a + b, 0);
  if (total !== 100) {
    const fix = others.find((k) => out[k] + (100 - total) >= 0) ?? key;
    out[fix] += 100 - total;
  }
  return out;
}

export function PrioritySliders({ weights, onChange, disabled, econAvailable }: {
  weights: Weights; onChange: (w: Weights) => void; disabled?: boolean; econAvailable: boolean;
}) {
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-4">
      {OBJECTIVES.map((o) => (
        <div key={o.key}>
          <div className="flex items-baseline justify-between text-sm">
            <label htmlFor={`w-${o.key}`} className="font-medium">{o.label}</label>
            <span className="font-display font-bold tabular-nums">{weights[o.key] ?? 0}%</span>
          </div>
          <input id={`w-${o.key}`} type="range" min={0} max={100} step={1} disabled={disabled}
                 value={weights[o.key] ?? 0} onChange={(e) => onChange(rebalance(weights, o.key, Number(e.target.value)))}
                 className="w-full accent-forest disabled:opacity-60" aria-describedby={`h-${o.key}`} />
          <p id={`h-${o.key}`} className="text-xs text-ink-faint">
            {o.hint}{o.key === "economic_potential" && !econAvailable && (weights[o.key] ?? 0) > 0 ? ". Without prices this weight is redistributed." : ""}
          </p>
        </div>
      ))}
      <p className="text-xs text-ink-soft">Total {total}%</p>
    </div>
  );
}
