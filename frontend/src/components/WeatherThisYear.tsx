"use client";

import { useMemo } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CloudRain, Droplets, Sun, Thermometer } from "lucide-react";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { C, TooltipBox, axisProps } from "./ChartPanel";
import { Badge, Loading } from "./ui";

/** Year-to-date daily weather for the farm, compared with its 10-year normal. */
export function WeatherThisYear({ farmId, refreshKey, compact = false }: { farmId: number; refreshKey?: unknown; compact?: boolean }) {
  const w = useAsync(() => api.get<any>(`/api/farms/${farmId}/earth-data/weather`), [farmId, refreshKey]);
  const chart = useMemo(() => {
    // Weekly aggregation keeps the chart readable on phones.
    const days: any[] = w.data?.days ?? [];
    const weeks: any[] = [];
    for (let i = 0; i < days.length; i += 7) {
      const chunk = days.slice(i, i + 7);
      const vals = (k: string) => chunk.map((d) => d[k]).filter((v) => v != null) as number[];
      const avg = (k: string) => (vals(k).length ? vals(k).reduce((a, b) => a + b, 0) / vals(k).length : null);
      weeks.push({
        week: chunk[0].date.slice(5), rain: vals("precip").length ? vals("precip").reduce((a, b) => a + b, 0) : null,
        tmax: avg("tmax"), tmin: avg("tmin"),
      });
    }
    return weeks;
  }, [w.data]);

  if (w.loading) return <Loading label="Loading this year's weather" />;
  if (!w.data?.available) {
    return compact ? null : (
      <div className="rounded-panel border border-dashed border-line bg-white p-6 text-sm text-ink-soft">
        No daily weather for this year yet. Retrieve weather data on the Field conditions page to fill this section.
      </div>
    );
  }
  const d = w.data;
  const anomaly = d.temp_anomaly_c;
  const cards = [
    { icon: CloudRain, label: `Rain since 1 Jan ${d.year}`, value: `${fmt(d.rain_total_mm)} mm`,
      note: d.rain_normal_mm ? `Normal for this period ≈ ${fmt(d.rain_normal_mm)} mm` : `${d.wet_days} wet days`, tone: "text-orbit" },
    { icon: Thermometer, label: "Average temperature", value: `${fmt(d.mean_temp_c, 1)} °C`,
      note: anomaly != null ? `${anomaly > 0 ? "+" : ""}${anomaly} °C vs normal` : "No normal available", tone: "text-ink" },
    { icon: Sun, label: `Days above ${d.heat_threshold_c} °C`, value: String(d.hot_days),
      note: d.hottest ? `Hottest ${d.hottest.value} °C on ${d.hottest.date}` : "", tone: d.hot_days ? "text-warn" : "text-ink" },
    { icon: Droplets, label: "Longest dry spell", value: `${d.longest_dry_spell_days} days`, note: `Days with under 1 mm of rain`, tone: "text-ink" },
  ];
  const tone = d.rain_percent_of_normal == null ? "grey" : d.rain_percent_of_normal < 80 ? "orange" : d.rain_percent_of_normal > 120 ? "blue" : "green";

  return (
    <section className={compact ? "" : "panel panel-pad"}>
      {!compact && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="section-title">This year’s weather</h2>
            <p className="text-xs text-ink-faint">Daily record, {d.first_day} to {d.last_day}{d.days_pending ? `. The last ${d.days_pending} day(s) are not available yet.` : "."}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {d.is_demo && <Badge tone="orange">Demonstration data</Badge>}
            <Badge tone={tone}>{d.rain_note}</Badge>
          </div>
        </div>
      )}
      <div className={`grid gap-3 ${compact ? "grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
        {cards.map((c) => (
          <div key={c.label} className={`rounded-2xl p-4 ${compact ? "bg-white/90" : "bg-paper"}`}>
            <div className="flex items-center gap-2 text-xs font-semibold text-ink-soft"><c.icon className="h-4 w-4" /> {c.label}</div>
            <div className={`mt-2 text-2xl font-bold ${c.tone}`}>{c.value}</div>
            {!compact && <div className="mt-1 text-xs text-ink-faint">{c.note}</div>}
          </div>
        ))}
      </div>
      {!compact && (
        <>
          <div className="mt-6 h-[260px]">
            <ResponsiveContainer>
              <ComposedChart data={chart}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="week" {...axisProps} minTickGap={20} />
                <YAxis yAxisId="r" {...axisProps} unit=" mm" width={56} />
                <YAxis yAxisId="t" orientation="right" {...axisProps} unit="°" width={36} />
                <Tooltip content={<TooltipBox />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="r" dataKey="rain" name="Weekly rain (mm)" fill={C.rain} radius={[4, 4, 0, 0]} />
                <Line yAxisId="t" dataKey="tmax" name="Avg max (°C)" stroke={C.tmax} dot={false} strokeWidth={2} connectNulls />
                <Line yAxisId="t" dataKey="tmin" name="Avg min (°C)" stroke={C.tmin} dot={false} strokeWidth={2} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-ink-faint">{d.note}</p>
        </>
      )}
    </section>
  );
}
