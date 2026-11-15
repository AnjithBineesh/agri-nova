"use client";

import { useEffect, useMemo, useState } from "react";
import { WeatherThisYear } from "@/components/WeatherThisYear";
import { FlaskConical, RefreshCw } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from "recharts";
import { C, ChartPanel, TooltipBox, axisProps } from "@/components/ChartPanel";
import {
  Badge, DataTypeTag, DemoBanner, ErrorState, Loading, NextStep, NoFarm, Notice, PageHeader, Spinner, Stat, TERMS,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { MONTHS, STATUS_LABEL, fmt } from "@/lib/format";
import type { DatasetStatus, EarthOverview } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const STATUS_TONE: Record<string, string> = {
  complete: "green", pending: "blue", processing: "blue", failed: "red", not_configured: "orange",
  not_integrated: "grey", not_requested: "grey", no_data: "orange", demonstration: "orange",
};

type Series = { date: string; value: number | null; product?: string; quality?: string; is_demo?: boolean }[];

export default function EarthPage() {
  const { farm, farms, loading: farmsLoading } = useFarm();
  const fid = farm?.id;
  const overview = useAsync(() => api.get<EarthOverview>(`/api/farms/${fid}/earth-data`), [fid], !!fid);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [rainSource, setRainSource] = useState<"both" | "imerg" | "power">("both");
  const range = `${start ? `start=${start}&` : ""}${end ? `end=${end}` : ""}`;
  const ready = !!fid && !!overview.data;
  const rain = useAsync(() => api.get<any>(`/api/farms/${fid}/earth-data/rainfall?${range}`), [fid, range, overview.data], ready);
  const temp = useAsync(() => api.get<any>(`/api/farms/${fid}/earth-data/temperature?${range}`), [fid, range, overview.data], ready);
  const sm = useAsync(() => api.get<any>(`/api/farms/${fid}/earth-data/soil-moisture?${range}`), [fid, range, overview.data], ready);
  const veg = useAsync(() => api.get<any>(`/api/farms/${fid}/earth-data/vegetation?${range}`), [fid, range, overview.data], ready);

  const datasets = overview.data?.datasets ?? [];
  const status = (k: string) => datasets.find((d) => d.key === k);
  const anyPending = datasets.some((d) => ["pending", "processing"].includes(d.status));

  useEffect(() => {
    if (!anyPending) return;
    const t = setInterval(() => overview.reload(), 30000);
    return () => clearInterval(t);
  }, [anyPending, overview]);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setActionError(null);
    try {
      await fn();
      await overview.reload();
    } catch (e: any) {
      setActionError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const profile = overview.data?.profile;
  const monthlyRain = useMemo(() => {
    const m = new Map<string, any>();
    for (const r of rain.data?.gpm_imerg_monthly ?? []) m.set(r.month, { ...(m.get(r.month) ?? { month: r.month }), imerg: r.value });
    for (const r of rain.data?.nasa_power_monthly ?? []) m.set(r.month, { ...(m.get(r.month) ?? { month: r.month }), power: r.value });
    return Array.from(m.values()).sort((a, b) => a.month.localeCompare(b.month));
  }, [rain.data]);
  const tempSeries = useMemo(() => {
    const at = temp.data?.air_temperature;
    if (!at) return [];
    const m = new Map<string, any>();
    (["T2M", "T2M_MAX", "T2M_MIN"] as const).forEach((k) => (at[k] as Series).forEach((r) => {
      m.set(r.date.slice(0, 7), { ...(m.get(r.date.slice(0, 7)) ?? { month: r.date.slice(0, 7) }), [k]: r.value });
    }));
    return Array.from(m.values()).sort((a, b) => a.month.localeCompare(b.month));
  }, [temp.data]);
  const smSeries = useMemo(() => {
    const m = new Map<string, any>();
    ((sm.data?.surface ?? []) as Series).forEach((r) => m.set(r.date, { ...(m.get(r.date) ?? { date: r.date }), surface: r.value }));
    ((sm.data?.rootzone ?? []) as Series).forEach((r) => m.set(r.date, { ...(m.get(r.date) ?? { date: r.date }), rootzone: r.value }));
    return Array.from(m.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [sm.data]);
  const ndviSeries = useMemo(() => {
    const m = new Map<string, any>();
    const add = (key: string, s?: Series) => (s ?? []).forEach((r) => m.set(r.date, { ...(m.get(r.date) ?? { date: r.date }), [key]: r.value }));
    add("modis", veg.data?.modis_ndvi);
    add("landsat", veg.data?.landsat_ndvi);
    add("sentinel2", veg.data?.sentinel2_ndvi);
    return Array.from(m.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [veg.data]);
  const etSeries = useMemo(() => {
    const pts = ((veg.data?.evapotranspiration ?? []) as Series).map((r) => ({ date: r.date, et: r.value }));
    return pts;
  }, [veg.data]);

  if (farmsLoading) return <Loading />;
  if (!farms.length) return <NoFarm />;
  if (overview.loading && !overview.data) return <Loading label="Loading field conditions" />;
  if (overview.error) return <ErrorState message={overview.error} onRetry={overview.reload} />;
  if (!overview.data || !profile) return null;

  const power = status("nasa_power");
  const neverFetched = datasets.filter((d) => d.integration === "integrated").every((d) => d.status === "not_requested");
  const coreFailed = !profile.has_climate && power && ["failed", "not_configured", "no_data"].includes(power.status);
  const hottest = profile.has_climate ? Math.max(...profile.monthly.map((m) => m.t_max ?? -99)) : null;
  const coldest = profile.has_climate ? Math.min(...profile.monthly.map((m) => m.t_min ?? 99)) : null;
  const et0Annual = profile.has_climate ? profile.monthly.reduce((a, m) => a + (m.et0_mm ?? 0), 0) : null;
  const tMean = profile.has_climate ? profile.monthly.reduce((a, m) => a + (m.t_mean ?? 0), 0) / 12 : null;
  const surf = profile.soil_moisture?.surface;
  const root = profile.soil_moisture?.rootzone;
  const lstLast = (temp.data?.land_surface_temperature ?? []).slice(-1)[0];
  const etLast = etSeries.slice(-1)[0];
  const climatology = profile.monthly.map((m) => ({ month: MONTHS[m.month - 1], rain: m.precip_mm, et0: m.et0_mm }));
  const statusMsg = (k: string) => {
    const s = status(k);
    if (!s) return "Not available";
    if (s.status === "complete" || s.status === "demonstration") return null;
    return `${STATUS_LABEL[s.status] ?? s.status}${s.display_message ? `: ${s.display_message}` : ""}`;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        tag="Weather, rainfall and soil moisture"
        title="Field"
        accent="conditions"
        intro={`The weather, rainfall, soil moisture and crop growth recorded for ${farm!.farm_name} (${farm!.latitude.toFixed(3)}, ${farm!.longitude.toFixed(3)}).`}
        actions={<>
          {farm!.can_edit && (
            <button className="btn-primary" disabled={!!busy} onClick={() => act("refresh", () => api.post(`/api/farms/${fid}/earth-data/refresh`, {}))}>
              {busy === "refresh" ? <Spinner /> : <RefreshCw className="h-4 w-4" />} {neverFetched ? "Retrieve weather data" : "Refresh data"}
            </button>
          )}
        </>}
      />
      <DemoBanner show={profile.is_demo} />
      {actionError && <ErrorState message={actionError} />}
      {busy === "refresh" && <Notice>Requesting weather, rainfall and field records for this farm. This can take up to a minute.</Notice>}
      {neverFetched && !busy && (
        <Notice>No records have been retrieved for this farm yet. Select <strong>Retrieve weather data</strong> to request them.</Notice>
      )}
      {coreFailed && (
        <Notice tone="warn">
          <p><strong>Weather data could not be retrieved.</strong> {power?.display_message}</p>
          <p className="mt-1">Agri Nova does not substitute estimated values. Check the server’s internet access and try again.</p>
          {overview.data.demo_enabled && farm!.can_edit && (
            <button className="btn-secondary mt-3" disabled={!!busy} onClick={() => act("demo", () => api.post(`/api/farms/${fid}/earth-data/demo`))}>
              {busy === "demo" ? <Spinner /> : <FlaskConical className="h-4 w-4" />} Load labelled demonstration dataset
            </button>
          )}
        </Notice>
      )}
      {profile.is_demo && farm!.can_edit && (
        <button className="btn-ghost text-sm" onClick={() => act("cleardemo", () => api.del(`/api/farms/${fid}/earth-data/demo`))}>
          Remove demonstration data
        </button>
      )}
      {anyPending && <Notice>Some field records are still being processed. This page checks for results every 30 seconds.</Notice>}

      <WeatherThisYear farmId={fid!} refreshKey={overview.data} />

      <h2 className="section-title pt-2">Long-term conditions</h2>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Annual rainfall" value={fmt(profile.annual_precip_mean)} unit="mm" accent="orbit"
              note={profile.sources.rainfall ? `${profile.sources.rainfall.dataset}${profile.annual_precip_cv ? `, varies ±${Math.round(profile.annual_precip_cv * 100)}% yearly` : ""}` : "No rainfall data"} />
        <Stat label="Average temperature" value={fmt(tMean, 1)} unit="°C"
              note={profile.temp_trend_c_per_decade != null ? `Trend ${profile.temp_trend_c_per_decade > 0 ? "+" : ""}${profile.temp_trend_c_per_decade} °C per decade` : profile.sources.climate?.dataset ?? "No climate data"} />
        <Stat label="Hottest month (avg max)" value={fmt(hottest, 1)} unit="°C" accent="warn" note={`Coldest month avg min ${fmt(coldest, 1)} °C`} />
        <Stat label="Reference evapotranspiration" value={fmt(et0Annual)} unit="mm/yr" tip={TERMS.et0}
              note={profile.monthly[0]?.et0_method ?? "Needs climate data"} />
        <Stat label="Surface soil moisture" value={fmt(surf?.latest, 2)} unit="m³/m³" accent="orbit" tip={TERMS.soilMoisture}
              note={surf ? `${surf.latest_date}, ${surf.resolution} area average` : statusMsg("smap") ?? "No data"} />
        <Stat label="Root-zone moisture" value={fmt(root?.latest, 2)} unit="m³/m³" tip={TERMS.rootzone}
              note={root ? `Model estimate, ${root.latest_date}` : "No data"} />
        <Stat label="Vegetation (NDVI)" value={fmt(profile.vegetation?.ndvi_latest, 2)} accent="leaf" tip={TERMS.ndvi}
              note={profile.vegetation?.ndvi_latest_date ? `${profile.vegetation.ndvi_latest_date}, ${profile.vegetation.resolution}` : "No cloud-free observation"} />
        <Stat label="Land surface temp / ET" value={lstLast ? fmt(lstLast.value, 1) : etLast ? fmt(etLast.et, 1) : "–"} unit={lstLast ? "°C" : etLast ? "mm/day" : ""} tip={TERMS.lst}
              note={lstLast ? `Observed ${lstLast.date}` : statusMsg("ecostress") ?? "No observation yet"} />
      </section>
      {profile.terrain?.elevation_m != null && (
        <p className="text-sm text-ink-soft">
          Terrain (30 m): elevation {fmt(profile.terrain.elevation_m)} m{profile.terrain.slope_deg != null ? `, slope ${fmt(profile.terrain.slope_deg, 1)}°` : ""}.
        </p>
      )}
      <p className="text-xs text-ink-faint">{overview.data.spatial_note}</p>

      <section className="panel flex flex-wrap items-end gap-4 px-5 py-4">
        <div>
          <label className="label" htmlFor="start">From</label>
          <input id="start" type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="end">To</label>
          <input id="end" type="date" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="rsrc">Rainfall dataset</label>
          <select id="rsrc" className="input" value={rainSource} onChange={(e) => setRainSource(e.target.value as any)}>
            <option value="both">Both rainfall records</option>
            <option value="imerg">Observed rainfall only</option>
            <option value="power">Weather record only</option>
          </select>
        </div>
        {(start || end) && <button className="btn-ghost" onClick={() => { setStart(""); setEnd(""); }}>Clear dates</button>}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartPanel title="Monthly rainfall" source="Observed daily rainfall summed by month, and the farm weather record (regional estimate)"
                    empty={monthlyRain.length ? null : statusMsg("gpm_imerg") ?? "No rainfall records in this period"}>
          <ResponsiveContainer>
            <BarChart data={monthlyRain}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="month" {...axisProps} minTickGap={24} />
              <YAxis {...axisProps} unit=" mm" width={56} />
              <Tooltip content={<TooltipBox unit="mm" />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {rainSource !== "power" && <Bar dataKey="imerg" name="Observed rainfall" fill={C.rain} />}
              {rainSource !== "imerg" && <Bar dataKey="power" name="Weather record" fill={C.rain2} />}
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Temperature history" source="Monthly means from the farm weather record (about 50 km regional average)"
                    empty={tempSeries.length ? null : statusMsg("nasa_power") ?? "No temperature records in this period"}>
          <ResponsiveContainer>
            <LineChart data={tempSeries}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="month" {...axisProps} minTickGap={24} />
              <YAxis {...axisProps} unit="°" width={40} />
              <Tooltip content={<TooltipBox unit="°C" />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line dataKey="T2M_MAX" name="Max" stroke={C.tmax} dot={false} strokeWidth={1.5} />
              <Line dataKey="T2M" name="Mean" stroke={C.temp} dot={false} strokeWidth={2} />
              <Line dataKey="T2M_MIN" name="Min" stroke={C.tmin} dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Soil moisture trend" tip={TERMS.soilMoisture} source="Surface (observed) and root zone (model estimate), 9 km area average"
                    empty={smSeries.length ? null : statusMsg("smap") ?? "No soil moisture records in this period"}>
          <ResponsiveContainer>
            <ComposedChart data={smSeries}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="date" {...axisProps} minTickGap={40} />
              <YAxis {...axisProps} width={44} domain={[0, "auto"]} />
              <Tooltip content={<TooltipBox unit="m³/m³" />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line dataKey="rootzone" name="Root zone 0–100 cm (model)" stroke={C.soil} dot={false} strokeWidth={1.5} connectNulls />
              <Scatter dataKey="surface" name="Surface ~0–5 cm (observed)" fill={C.rain} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Vegetation (NDVI) seasonal trend" tip={TERMS.ndvi} source="250 m 16-day composites, and 30 m cloud-masked observations from two sources clear-sky observations"
                    empty={ndviSeries.length ? null : statusMsg("modis") ?? "No cloud-free vegetation observations"}>
          <ResponsiveContainer>
            <ComposedChart data={ndviSeries}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="date" {...axisProps} minTickGap={40} />
              <YAxis {...axisProps} width={36} domain={[0, 1]} />
              <Tooltip content={<TooltipBox />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line dataKey="modis" name="250 m composite" stroke={C.leaf} strokeWidth={2} dot={false} connectNulls />
              <Scatter dataKey="landsat" name="30 m source A" fill={C.series[0]} />
              <Scatter dataKey="sentinel2" name="30 m source B" fill={C.series[3]} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Water demand: rainfall vs reference evapotranspiration" tip={TERMS.et0}
                    source="Monthly climatology: rainfall and FAO-56 ET0 computed from the farm weather record"
                    empty={profile.has_climate ? null : statusMsg("nasa_power") ?? "Needs climate data"}>
          <ResponsiveContainer>
            <BarChart data={climatology}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="month" {...axisProps} />
              <YAxis {...axisProps} unit=" mm" width={56} />
              <Tooltip content={<TooltipBox unit="mm" />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="rain" name="Rainfall" fill={C.rain} />
              <Bar dataKey="et0" name="Reference ET0" fill={C.temp} />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>

        <ChartPanel title="Evapotranspiration" tip={TERMS.et} source="70 m, irregular observation dates"
                    empty={etSeries.length ? null : statusMsg("ecostress") ?? "No evapotranspiration observations"}>
          <ResponsiveContainer>
            <ComposedChart data={etSeries}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="date" {...axisProps} minTickGap={40} />
              <YAxis {...axisProps} unit=" mm" width={50} />
              <Tooltip content={<TooltipBox unit="mm/day" />} />
              <Scatter dataKey="et" name="ET" fill={C.leaf} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartPanel>

        <div className="lg:col-span-2">
          <ChartPanel title="Historical climate comparison" source="Annual totals and means by year; years with missing months are left blank"
                      empty={profile.annual.length ? null : "Needs weather records"}>
            <ResponsiveContainer>
              <ComposedChart data={profile.annual}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="year" {...axisProps} />
                <YAxis yAxisId="r" {...axisProps} unit=" mm" width={60} />
                <YAxis yAxisId="t" orientation="right" {...axisProps} unit="°" width={40} domain={["auto", "auto"]} />
                <Tooltip content={<TooltipBox />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="r" dataKey="precip_mm" name="Annual rainfall (mm)" fill={C.rain} />
                <Line yAxisId="t" dataKey="t_mean" name="Mean temperature (°C)" stroke={C.temp} strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartPanel>
        </div>
      </div>

      <DatasetTable datasets={datasets} />
      {profile.has_climate && <NextStep href="/app/soil" title="Add your soil test" body="Soil pH, organic carbon and nutrients make crop advice much more precise." />}
    </div>
  );
}

function DatasetTable({ datasets }: { datasets: DatasetStatus[] }) {
  return (
    <section>
      <h2 className="section-title mb-3">Records for this farm</h2>
      <div className="overflow-x-auto rounded-panel border border-line bg-white">
        <table className="table-base min-w-[900px]">
          <thead>
            <tr><th>Record</th><th>Status</th><th>Data type</th><th>Detail</th><th>Period retrieved</th><th>Notes</th></tr>
          </thead>
          <tbody>
            {datasets.map((d) => (
              <tr key={d.key}>
                <td>
                  <span className="font-semibold text-forest">{d.display_name}</span>
                </td>
                <td><Badge tone={STATUS_TONE[d.status]}>{STATUS_LABEL[d.status] ?? d.status}</Badge></td>
                <td><DataTypeTag type={d.is_demo ? "demonstration" : d.data_type} /></td>
                <td className="whitespace-nowrap text-ink-soft">{d.display_resolution}<div className="text-xs text-ink-faint">{d.temporal_resolution}</div></td>
                <td className="whitespace-nowrap text-ink-soft">
                  {d.coverage_start ? <>{d.coverage_start} to {d.coverage_end}<div className="text-xs text-ink-faint">{d.record_count.toLocaleString()} values, last observation {d.coverage_end}</div></> : "–"}
                </td>
                <td className="max-w-sm text-xs text-ink-soft">{d.display_message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
