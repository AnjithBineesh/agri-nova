"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { C, ChartPanel, TooltipBox, axisProps } from "@/components/ChartPanel";
import { RotationRibbon } from "@/components/RotationRibbon";
import { NextStep, Badge, DemoBanner, ErrorState, Loading, NeedsClimate, NoFarm, Notice, PageHeader, Spinner, TERMS } from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { fmt, signed } from "@/lib/format";
import type { Crop, Simulation } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const PRESETS = [
  { key: "baseline", label: "Recent climate", t: 0, r: 1 },
  { key: "warmer", label: "+1.5 °C", t: 1.5, r: 1 },
  { key: "drier", label: "20% drier", t: 0, r: 0.8 },
  { key: "hot_dry", label: "+2 °C, 20% drier", t: 2, r: 0.8 },
  { key: "wetter", label: "20% wetter", t: 0, r: 1.2 },
];
const VCLASS: Record<string, string> = { low: "#9cc79f", moderate: "#e6b56a", high: "#c96a5f" };

function SimulatorInner() {
  const { farm, farms, loading: fl } = useFarm();
  const params = useSearchParams();
  const fid = farm?.id;
  const recs = useAsync(() => api.get<any>(`/api/rotations/farm/${fid}`), [fid], !!fid);
  const crops = useAsync(() => api.get<{ crops: Crop[] }>("/api/crops"), []);
  const families = useMemo(() => Object.fromEntries((crops.data?.crops ?? []).map((c) => [c.slug, c.crop_family])), [crops.data]);
  const names = useMemo(() => Object.fromEntries((crops.data?.crops ?? []).map((c) => [c.slug, c.crop_name])), [crops.data]);
  const options = useMemo(() => {
    const all = [...(recs.data?.latest ?? []), ...(recs.data?.saved ?? [])];
    const seen = new Set<number>();
    return all.filter((r: any) => !seen.has(r.id) && seen.add(r.id));
  }, [recs.data]);
  const [selected, setSelected] = useState<number[]>([]);
  const [temp, setTemp] = useState(0);
  const [rain, setRain] = useState(1);
  const [irr, setIrr] = useState<string>("farm");
  const [cap, setCap] = useState("");
  const [years, setYears] = useState(5);
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!options.length || selected.length) return;
    const want = Number(params.get("strategy"));
    const existing = options.find((o: any) => o.strategy_key === "existing");
    const ranked = [...options].filter((o: any) => o.strategy_key !== "existing").sort((a: any, b: any) => (a.scores.rank ?? 99) - (b.scores.rank ?? 99));
    const init = [want && options.some((o: any) => o.id === want) ? want : ranked[0]?.id, existing?.id, ranked[1]?.id]
      .filter((x, i, arr) => x && arr.indexOf(x) === i).slice(0, 3) as number[];
    setSelected(init);
  }, [options, params, selected.length]);

  useEffect(() => { setRes(null); setSelected([]); }, [fid]);

  if (fl) return <Loading />;
  if (!farms.length) return <NoFarm />;

  const scenario = {
    temp_delta_c: temp, rain_factor: rain,
    irrigation_type: irr === "farm" ? undefined : irr,
    irrigation_capacity_mm: irr !== "farm" && irr !== "none" && cap ? Number(cap) : undefined,
  };

  const run = async () => {
    setBusy(true); setErr(null); setSavedMsg(null);
    try {
      const rotations = selected.map((id) => ({ name: options.find((o: any) => o.id === id)!.strategy_name, strategy_id: id }));
      setRes(await api.post<any>("/api/simulations/compare", { farm_id: fid, rotations, scenario, horizon_years: years }));
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const saveFirst = async () => {
    try {
      const r = await api.post<any>("/api/simulations", { farm_id: fid, strategy_id: selected[0], planning_horizon: years === 1 ? "seasonal" : "five_year", scenario });
      setSavedMsg(`Simulation saved (reference #${r.id}).`);
    } catch (e: any) { setErr(e.message); }
  };

  if (recs.loading) return <Loading />;
  if (!options.length) {
    return (
      <div className="space-y-6">
        <PageHeader title="Five-year simulator" />
        <section className="panel panel-pad">
          <h2 className="section-title">Generate rotation strategies first</h2>
          <p className="mt-1 text-sm text-ink-soft">The simulator compares rotation strategies from the planner season by season.</p>
          <Link href="/app/planner" className="btn-primary mt-4">Open rotation planner</Link>
        </section>
      </div>
    );
  }

  const sims: Record<string, Simulation> = res?.simulations ?? {};
  const simNames = Object.keys(sims);
  const seriesData = (fn: (s: any) => any, includeStart?: (sim: Simulation) => any) => {
    const n = Math.max(0, ...simNames.map((k) => sims[k].seasons.length));
    const rows: any[] = [];
    if (includeStart) {
      const r: any = { label: "Start" };
      simNames.forEach((k) => Object.assign(r, includeStart(sims[k]) ? { [k]: includeStart(sims[k]).c, [`${k}__band`]: includeStart(sims[k]).band } : {}));
      rows.push(r);
    }
    for (let i = 0; i < n; i++) {
      const anyS = sims[simNames[0]].seasons[i];
      const r: any = { label: `Y${anyS.year} ${anyS.season.split(" ")[0]}` };
      simNames.forEach((k) => {
        const s = sims[k].seasons[i];
        if (s && !s.continuation) Object.assign(r, fn(s) ? Object.fromEntries(Object.entries(fn(s)).map(([kk, v]) => [kk === "c" ? k : `${k}__${kk}`, v])) : {});
      });
      rows.push(r);
    }
    return rows;
  };
  const socData = res ? seriesData((s) => s.soc_t_ha ? { c: s.soc_t_ha.central, band: [s.soc_t_ha.low, s.soc_t_ha.high] } : null,
    (sim) => ({ c: sim.summary.soc_initial_t_ha, band: [sim.summary.soc_initial_t_ha, sim.summary.soc_initial_t_ha] })) : [];
  const nData = res ? seriesData((s) => ({ c: s.n_balance_cum })) : [];
  const waterData = res ? seriesData((s) => ({ c: s.water?.irrigation_need_mm ?? 0 })) : [];
  const divData = res ? seriesData((s) => ({ c: s.family_count })) : [];

  return (
    <div className="space-y-6">
      <PageHeader tag="Plan" title="Five-year" accent="simulator"
                  intro="Each season's soil carbon, nutrient balance and water demand carry into the next. Compare strategies under today's climate or a changed one." />
      {err && <ErrorState message={err} />}
      {err?.includes("Climate data") && <NeedsClimate farmId={fid} />}

      <section className="panel panel-pad">
        <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h2 className="section-title">Strategies to compare</h2>
            <p className="text-xs text-ink-soft">Choose up to three.</p>
            <div className="mt-3 space-y-2">
              {options.map((o: any) => {
                const on = selected.includes(o.id);
                return (
                  <label key={o.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2 text-sm ${on ? "border-forest bg-leaf-50" : "border-line"}`}>
                    <input type="checkbox" className="mt-1 accent-forest" checked={on} disabled={!on && selected.length >= 3}
                           onChange={() => setSelected(on ? selected.filter((x) => x !== o.id) : [...selected, o.id])} />
                    <span className="min-w-0">
                      <span className="font-medium">{o.strategy_name}</span>{o.saved && <Badge tone="green">Saved</Badge>}
                      <span className="block truncate text-xs text-ink-soft">{o.explanation.sequence_text}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
          <div className="space-y-4">
            <h2 className="section-title">Scenario</h2>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button key={p.key} className={temp === p.t && rain === p.r ? "btn-primary py-1 text-xs" : "btn-secondary py-1 text-xs"}
                        onClick={() => { setTemp(p.t); setRain(p.r); }}>{p.label}</button>
              ))}
            </div>
            <div>
              <div className="flex justify-between text-sm"><label htmlFor="t">Temperature change</label><span className="font-semibold">{temp > 0 ? "+" : ""}{temp.toFixed(1)} °C</span></div>
              <input id="t" type="range" min={-1} max={3} step={0.5} value={temp} onChange={(e) => setTemp(Number(e.target.value))} className="w-full accent-forest" />
            </div>
            <div>
              <div className="flex justify-between text-sm"><label htmlFor="r">Rainfall</label><span className="font-semibold">{Math.round(rain * 100)}% of recent average</span></div>
              <input id="r" type="range" min={0.6} max={1.3} step={0.05} value={rain} onChange={(e) => setRain(Number(e.target.value))} className="w-full accent-forest" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label" htmlFor="irr">Water availability</label>
                <select id="irr" className="input" value={irr} onChange={(e) => setIrr(e.target.value)}>
                  <option value="farm">As in farm profile ({farm?.irrigation_type})</option>
                  <option value="none">Rainfed only</option>
                  <option value="supplemental">Supplemental irrigation</option>
                  <option value="full">Full irrigation</option>
                </select>
              </div>
              <div>
                <label className="label" htmlFor="cap">mm per season</label>
                <input id="cap" className="input" inputMode="decimal" disabled={irr === "farm" || irr === "none"} value={cap} onChange={(e) => setCap(e.target.value)} placeholder="Optional" />
              </div>
            </div>
            <div className="flex items-end justify-between gap-3">
              <div>
                <span className="label">Planning horizon</span>
                <div className="flex gap-1.5">
                  <button className={years === 1 ? "btn-primary py-1.5" : "btn-secondary py-1.5"} onClick={() => setYears(1)}>Next year</button>
                  <button className={years === 5 ? "btn-primary py-1.5" : "btn-secondary py-1.5"} onClick={() => setYears(5)}>Five years</button>
                </div>
              </div>
              <button className="btn-leaf px-6 py-2.5" disabled={busy || !selected.length} onClick={run}>{busy && <Spinner />} Run simulation</button>
            </div>
          </div>
        </div>
      </section>

      {busy && <Loading label="Simulating seasons" />}
      {res && !busy && (
        <>
          <DemoBanner show={res.is_demo_basis} />
          <Notice>Simulated outcomes are comparative indications under the stated assumptions, not forecasts. They do not guarantee yields or soil improvement.</Notice>

          <section className="panel panel-pad">
            <h2 className="section-title">Rotation timeline</h2>
            <div className="mt-4 space-y-4">
              {simNames.map((k) => (
                <div key={k}>
                  <div className="mb-1 text-sm font-medium">{k}</div>
                  <RotationRibbon families={families}
                    items={sims[k].seasons.filter((s) => !s.continuation).map((s) => ({ crop: s.crop, crop_name: s.crop === "fallow" ? "Fallow" : names[s.crop] ?? s.crop_name, span: s.span ?? 1, season: `Year ${s.year}` }))} />
                  <div className="mt-1 flex w-full gap-px" aria-label="Climate vulnerability by season">
                    {sims[k].seasons.filter((s) => !s.continuation).map((s) => (
                      <div key={s.index} className="h-1.5" style={{ flex: s.span ?? 1, background: s.crop === "fallow" ? "#e3e7e3" : VCLASS[s.climate_vulnerability_class ?? "low"] }}
                           title={`${s.crop_name}: climate vulnerability ${s.climate_vulnerability_class}`} />
                    ))}
                  </div>
                </div>
              ))}
              <p className="text-xs text-ink-faint">The thin bar under each rotation shows climate vulnerability per season: green low, amber moderate, red high.</p>
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <ChartPanel title="Soil organic carbon projection" tip={TERMS.soc} source="Topsoil 0–30 cm, t C/ha. Shaded band shows the parameter uncertainty range."
                        footer={Object.values(sims)[0]?.assumptions.organic_carbon}>
              <ResponsiveContainer>
                <ComposedChart data={socData}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="label" {...axisProps} minTickGap={16} />
                  <YAxis {...axisProps} width={44} domain={["auto", "auto"]} />
                  <Tooltip content={<TooltipBox unit="t C/ha" />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {simNames.map((k, i) => <Area key={`${k}b`} dataKey={`${k}__band`} name={`${k} range`} stroke="none" fill={C.series[i]} fillOpacity={0.12} legendType="none" connectNulls />)}
                  {simNames.map((k, i) => <Line key={k} dataKey={k} name={k} stroke={C.series[i]} strokeWidth={2} dot={false} connectNulls />)}
                </ComposedChart>
              </ResponsiveContainer>
            </ChartPanel>
            <ChartPanel title="Nutrient balance" tip={TERMS.nbalance} source="Cumulative nitrogen balance before fertiliser, kg N/ha">
              <ResponsiveContainer>
                <LineChart data={nData}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="label" {...axisProps} minTickGap={16} />
                  <YAxis {...axisProps} width={50} />
                  <Tooltip content={<TooltipBox unit="kg N/ha" />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {simNames.map((k, i) => <Line key={k} dataKey={k} name={k} stroke={C.series[i]} strokeWidth={2} dot={{ r: 2 }} connectNulls />)}
                </LineChart>
              </ResponsiveContainer>
            </ChartPanel>
            <ChartPanel title="Seasonal water demand" source="Net irrigation need per season after effective rainfall and stored soil water, mm">
              <ResponsiveContainer>
                <BarChart data={waterData}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="label" {...axisProps} minTickGap={16} />
                  <YAxis {...axisProps} width={44} />
                  <Tooltip content={<TooltipBox unit="mm" />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {simNames.map((k, i) => <Bar key={k} dataKey={k} name={k} fill={C.series[i]} />)}
                </BarChart>
              </ResponsiveContainer>
            </ChartPanel>
            <ChartPanel title="Crop diversity" source="Number of different crop families grown so far">
              <ResponsiveContainer>
                <LineChart data={divData}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="label" {...axisProps} minTickGap={16} />
                  <YAxis {...axisProps} width={30} allowDecimals={false} />
                  <Tooltip content={<TooltipBox />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {simNames.map((k, i) => <Line key={k} type="stepAfter" dataKey={k} name={k} stroke={C.series[i]} strokeWidth={2} dot={false} connectNulls />)}
                </LineChart>
              </ResponsiveContainer>
            </ChartPanel>
          </div>

          <section className="panel panel-pad">
            <h2 className="section-title">Climate risk and erosion comparison</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="table-base min-w-[640px]">
                <thead><tr><th>Strategy</th><th>Mean vulnerability</th><th>High-vulnerability seasons</th><th>Seasons with a critical constraint</th><th>High erosion-risk seasons</th><th>Unmet water deficit</th></tr></thead>
                <tbody>
                  {simNames.map((k) => {
                    const s = sims[k].summary;
                    return (
                      <tr key={k}>
                        <td className="font-medium">{k}</td>
                        <td>{fmt(s.mean_climate_vulnerability, 2)}</td>
                        <td>{s.high_vulnerability_seasons}</td>
                        <td>{s.critical_seasons ? <Badge tone="red">{s.critical_seasons}</Badge> : 0}</td>
                        <td>{s.high_erosion_seasons}</td>
                        <td>{fmt(s.total_unmet_deficit_mm)} mm</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-ink-faint">{TERMS.vulnerability} {TERMS.erosion}</p>
          </section>

          <section className="panel panel-pad">
            <h2 className="section-title">Indicator comparison</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="table-base min-w-[640px]">
                <thead><tr><th>Indicator</th>{simNames.map((k) => <th key={k}>{k}</th>)}</tr></thead>
                <tbody>
                  {res.comparison.table.map((row: any) => (
                    <tr key={row.indicator}>
                      <td>{row.label}<span className="block text-xs text-ink-faint">{row.better} is better</span></td>
                      {simNames.map((k) => (
                        <td key={k} className={row.best?.includes(k) ? "font-semibold text-leaf-600" : ""}>
                          {row.values[k] == null ? "Not assessed" : row.indicator === "soc_change" ? signed(row.values[k], 2) : row.indicator === "n_balance" ? signed(row.values[k]) : fmt(row.values[k], row.indicator === "vulnerability" ? 2 : 0)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-soft">{res.comparison.tradeoffs.map((t: string) => <li key={t}>{t}</li>)}</ul>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {farm?.can_edit && <button className="btn-secondary" onClick={saveFirst}>Save simulation of “{simNames[0]}”</button>}
              {savedMsg && <span className="text-sm text-leaf-600">{savedMsg}</span>}
            </div>
          </section>

          <details className="panel panel-pad">
            <summary className="cursor-pointer section-title">Model assumptions and limitations</summary>
            <dl className="mt-3 space-y-2 text-sm">
              {Object.entries(Object.values(sims)[0]?.assumptions ?? {}).map(([k, v]) => (
                <div key={k}><dt className="font-medium capitalize">{k.replace(/_/g, " ")}</dt><dd className="text-ink-soft">{v}</dd></div>
              ))}
            </dl>
          </details>
          <NextStep href="/app/reports" title="Download your farm report" body="Take the results to your extension officer or agronomist." />
        </>
      )}
    </div>
  );
}

export default function SimulatorPage() {
  return <Suspense><SimulatorInner /></Suspense>;
}
