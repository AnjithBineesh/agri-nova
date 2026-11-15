"use client";

import { InfoTip } from "./ui";

export const C = {
  rain: "#2f6fa8",
  rain2: "#8db4d8",
  temp: "#b8620f",
  tmax: "#b3372f",
  tmin: "#2f6fa8",
  leaf: "#3d8b4f",
  leaf2: "#9cc79f",
  soil: "#8a6a3d",
  grid: "#e6ebe6",
  axis: "#7d8b82",
  series: ["#0f3b2c", "#2f6fa8", "#b8620f", "#7a4fa3", "#3d8b4f", "#b3372f"],
};

export const axisProps = { stroke: C.axis, fontSize: 11, tickLine: false, axisLine: { stroke: C.grid } } as const;

export function ChartPanel({
  title, tip, source, children, empty, height = 260, footer,
}: {
  title: string;
  tip?: string;
  source?: React.ReactNode;
  children: React.ReactNode;
  empty?: string | null;
  height?: number;
  footer?: React.ReactNode;
}) {
  return (
    <section className="panel panel-pad">
      <div className="flex items-start justify-between gap-3">
        <h3 className="flex items-center text-base font-semibold">{title}{tip && <InfoTip text={tip} />}</h3>
      </div>
      {source && <div className="mt-0.5 text-xs text-ink-faint">{source}</div>}
      <div className="mt-4" style={{ height }}>
        {empty ? (
          <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-line bg-paper px-6 text-center text-sm text-ink-soft">
            {empty}
          </div>
        ) : children}
      </div>
      {footer && <div className="mt-3 text-xs text-ink-faint">{footer}</div>}
    </section>
  );
}

export function TooltipBox({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line bg-white px-3 py-2 text-xs shadow-sm">
      <div className="mb-1 font-semibold text-ink">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-ink-soft">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          {p.name}: <span className="font-medium text-ink">{p.value == null ? "missing" : Array.isArray(p.value) ? p.value.map((v: number) => v.toFixed(2)).join(" – ") : Number(p.value).toFixed(p.value < 2 ? 2 : 1)}{unit ? ` ${unit}` : ""}</span>
        </div>
      ))}
    </div>
  );
}
