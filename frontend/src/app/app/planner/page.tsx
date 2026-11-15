"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Bookmark, BookmarkCheck, ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from "lucide-react";
import { OBJECTIVES, PrioritySliders, type Weights } from "@/components/PrioritySliders";
import { RotationRibbon } from "@/components/RotationRibbon";
import { NextStep, Badge, DemoBanner, ErrorState, InfoTip, Loading, NeedsClimate, NoFarm, Notice, PageHeader, ScoreBar, Spinner, TERMS } from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { fmt, seasonText, signed } from "@/lib/format";
import type { Crop, RotationSlot, Strategy } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const DEFAULT_W: Weights = { soil_health: 30, water_conservation: 25, climate_resilience: 20, economic_potential: 10, crop_diversity: 15 };

function fromSaved(r: any): Strategy {
  return {
    id: r.id, key: r.strategy_key, name: r.strategy_name, rank: r.scores.rank, rotation: r.explanation.rotation,
    crop_sequence: r.crop_sequence, mean_suitability: r.suitability_score, harvested_seasons: NaN, cycle_seasons: NaN,
    objectives: r.scores.objectives, priority_score: r.scores.priority_score, rules: r.explanation.rules,
    simulation_summary: r.scores.simulation_summary, stress_summary: r.scores.stress_summary,
    explanation: r.explanation, saved: r.saved,
  } as Strategy & { saved?: boolean };
}

export default function PlannerPage() {
  const { farm, farms, loading: fl } = useFarm();
  const fid = farm?.id;
  const crops = useAsync(() => api.get<{ crops: Crop[] }>("/api/crops"), []);
  const previous = useAsync(() => api.get<any>(`/api/rotations/farm/${fid}`), [fid], !!fid);
  const [mode, setMode] = useState<"automatic" | "custom">("automatic");
  const [weights, setWeights] = useState<Weights>(DEFAULT_W);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [needsClimate, setNeedsClimate] = useState(false);
  const [showEcon, setShowEcon] = useState(false);
  const [econ, setEcon] = useState<Record<string, { price_per_t: string; cost_per_ha: string; yield: string }>>({});
  const [custom, setCustom] = useState<RotationSlot[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [saved, setSaved] = useState<Record<number, boolean>>({});

  const cropMap = useMemo(() => Object.fromEntries((crops.data?.crops ?? []).map((c) => [c.slug, c])), [crops.data]);
  const families = useMemo(() => Object.fromEntries((crops.data?.crops ?? []).map((c) => [c.slug, c.crop_family])), [crops.data]);

  useEffect(() => {
    setResult(null);
    setCustom(null);
    setNeedsClimate(false);
  }, [fid]);

  useEffect(() => {
    if (!result && previous.data?.latest?.length) {
      const strategies = previous.data.latest.map(fromSaved);
      setResult({ strategies, priority_weights: previous.data.latest[0].priority_weights, fromHistory: true, seasons: farm?.growing_seasons ?? [] });
      setSaved(Object.fromEntries(previous.data.latest.map((r: any) => [r.id, r.saved])));
    }
  }, [previous.data, result, farm]);

  if (fl) return <Loading />;
  if (!farms.length) return <NoFarm />;

  const seasons = result?.seasons?.length ? result.seasons : farm?.growing_seasons?.length ? farm.growing_seasons : [{ name: "Season 1", start_month: 6, end_month: 10 }, { name: "Season 2", start_month: 11, end_month: 3 }];
  const cycle = Math.min(6, seasons.length * 2);
  const econRows = Object.entries(econ).filter(([, v]) => v.price_per_t !== "" && v.cost_per_ha !== "");

  const generate = async (customRotation = custom) => {
    setBusy(true); setErr(null); setNeedsClimate(false);
    const economics = Object.fromEntries(econRows.map(([k, v]) => [k, { price_per_t: Number(v.price_per_t), cost_per_ha: Number(v.cost_per_ha) }]));
    const yields = Object.fromEntries(Object.entries(econ).filter(([, v]) => v.yield !== "").map(([k, v]) => [k, Number(v.yield)]));
    try {
      const r = await api.post<any>("/api/rotations/generate", {
        farm_id: fid, mode, priorities: mode === "custom" ? weights : undefined, horizon_years: 5, economics, yields,
        custom_rotation: customRotation?.filter((s) => s.crop) ?? undefined,
      });
      setResult(r);
      if (mode === "automatic") setWeights(r.priority_weights);
      setSaved({});
      setOpen(null);
    } catch (e: any) {
      if (e.status === 409) setNeedsClimate(true);
      else setErr(e.message);
    } finally { setBusy(false); }
  };

  const toggleSave = async (id: number) => {
    const r = await api.post<any>(`/api/rotations/${id}/save`);
    setSaved((s) => ({ ...s, [id]: r.saved }));
  };

  const strategies: Strategy[] = result?.strategies ?? [];
  const ranked = [...strategies].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

  return (
    <div className="space-y-6">
      <PageHeader tag="Plan" title="Crop rotation" accent="planner"
                  intro="Alternative crop sequences for this farm, each tested over five years. Set what matters most to you and compare the trade-offs." />
      {err && <ErrorState message={err} />}
      {needsClimate && <NeedsClimate farmId={fid} />}

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <aside className="space-y-4">
          <section className="panel panel-pad">
            <h2 className="section-title">Your priorities</h2>
            <div className="mt-3 grid grid-cols-2 gap-1 rounded-xl bg-paper p-1 text-sm" role="radiogroup" aria-label="Priority mode">
              {(["automatic", "custom"] as const).map((m) => (
                <button key={m} role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                        className={`rounded px-3 py-1.5 font-medium ${mode === m ? "bg-white text-forest shadow-sm" : "text-ink-soft"}`}>
                  {m === "automatic" ? "Automatic" : "Custom"}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-ink-soft">
              {mode === "automatic" ? "Agri Nova sets weights from your farm's conditions and explains why." : "Move the sliders. The weights always add up to 100%."}
            </p>
            <div className="mt-4">
              <PrioritySliders weights={weights} onChange={setWeights} disabled={mode === "automatic"} econAvailable={econRows.length > 0} />
            </div>
            {result?.weights_explanation && mode === "automatic" && (
              <ul className="mt-4 space-y-1 border-t border-line pt-3 text-xs text-ink-soft">
                {result.weights_explanation.map((w: string) => <li key={w}>{w}</li>)}
              </ul>
            )}
          </section>

          <section className="panel">
            <button className="flex w-full items-center justify-between px-5 py-4 text-left" onClick={() => setShowEcon(!showEcon)} aria-expanded={showEcon}>
              <span><span className="section-title">Local prices and yields</span><span className="block text-xs text-ink-soft">Optional. Enables the economic comparison.</span></span>
              {showEcon ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            {showEcon && (
              <div className="space-y-3 border-t border-line px-5 py-4">
                <p className="text-xs text-ink-soft">Use your own figures in one currency. Economics are only calculated when every crop in a rotation has a price and cost.</p>
                {Object.entries(econ).map(([slug, v]) => (
                  <div key={slug} className="rounded-xl border border-line p-2">
                    <div className="flex items-center justify-between text-sm font-medium">{cropMap[slug]?.crop_name}
                      <button className="text-ink-faint hover:text-risk" aria-label="Remove" onClick={() => setEcon(({ [slug]: _, ...rest }) => rest)}><Trash2 className="h-3.5 w-3.5" /></button></div>
                    <div className="mt-1 grid grid-cols-3 gap-1">
                      {(["price_per_t", "cost_per_ha", "yield"] as const).map((k) => (
                        <input key={k} className="input px-2 py-1 text-xs" inputMode="decimal" placeholder={{ price_per_t: "Price / t", cost_per_ha: "Cost / ha", yield: "Yield t/ha" }[k]}
                               aria-label={`${cropMap[slug]?.crop_name} ${k}`} value={v[k]} onChange={(e) => setEcon({ ...econ, [slug]: { ...v, [k]: e.target.value } })} />
                      ))}
                    </div>
                  </div>
                ))}
                <select className="input" value="" aria-label="Add crop prices" onChange={(e) => e.target.value && setEcon({ ...econ, [e.target.value]: { price_per_t: "", cost_per_ha: "", yield: "" } })}>
                  <option value="">Add a crop…</option>
                  {(crops.data?.crops ?? []).filter((c) => !econ[c.slug]).map((c) => <option key={c.slug} value={c.slug}>{c.crop_name}</option>)}
                </select>
              </div>
            )}
          </section>

          <section className="panel panel-pad">
            <div className="flex items-center justify-between">
              <h2 className="section-title">Custom rotation</h2>
              {!custom && <button className="btn-secondary py-1" onClick={() => setCustom(Array.from({ length: cycle }, () => ({ crop: "", span: 1 })))}><Plus className="h-4 w-4" /> Build</button>}
            </div>
            {!custom ? <p className="mt-1 text-xs text-ink-soft">Add your own sequence to compare it with the generated strategies.</p> : (
              <div className="mt-3 space-y-2">
                {custom.map((slot, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-24 shrink-0 truncate text-xs text-ink-soft">{seasons[i % seasons.length].name}</span>
                    <select className="input py-1.5" value={slot.crop} aria-label={`Crop for slot ${i + 1}`}
                            onChange={(e) => setCustom(custom.map((s, j) => j === i ? { ...s, crop: e.target.value } : s))}>
                      <option value="">Choose…</option>
                      <option value="fallow">Fallow</option>
                      {(crops.data?.crops ?? []).map((c) => <option key={c.slug} value={c.slug}>{c.crop_name}</option>)}
                    </select>
                  </div>
                ))}
                <div className="flex gap-2 pt-1">
                  <button className="btn-ghost py-1 text-xs" onClick={() => setCustom(null)}>Remove custom rotation</button>
                </div>
              </div>
            )}
          </section>

          <button className="btn-primary w-full py-3" disabled={busy || (custom !== null && custom.some((s) => !s.crop))} onClick={() => generate()}>
            {busy && <Spinner />} {result ? "Regenerate strategies" : "Generate rotation strategies"}
          </button>
          {custom && custom.some((s) => !s.crop) && <p className="text-xs text-ink-faint">Choose a crop or fallow for every slot of the custom rotation.</p>}
        </aside>

        <div className="min-w-0 space-y-4">
          {busy && <Loading label="Generating and simulating rotations" />}
          {!result && !busy && !needsClimate && (
            <section className="panel panel-pad">
              <h2 className="section-title">No strategies yet</h2>
              <p className="mt-1 max-w-prose text-sm text-ink-soft">
                Generate strategies to see at least three alternative sequences for {seasons.map(seasonText).join(" and ")}: your existing practice,
                a soil-health rotation, a water-conscious rotation, a climate-resilient rotation and one balanced for your priorities.
              </p>
            </section>
          )}
          {result && !busy && (
            <>
              <DemoBanner show={!!result.is_demo_basis || strategies.some((s) => s.explanation?.limitations?.some((l: string) => l.includes("DEMONSTRATION")))} />
              {result.fromHistory && <Notice>Showing your most recent strategies. Regenerate after changing priorities, soil data or prices.</Notice>}
              {result.seasons_source && <p className="text-xs text-ink-faint">Seasons: {result.seasons.map(seasonText).join(", ")} ({result.seasons_source}). Each rotation cycle covers {result.cycle_seasons} seasons and is repeated over five years.</p>}
              <ol className="space-y-3">
                {ranked.map((s) => {
                  const ex = s.explanation;
                  const isOpen = open === s.key;
                  const sm = s.simulation_summary;
                  return (
                    <li key={s.key} className="panel">
                      <div className="p-5">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              {s.rank && <span className="font-display text-sm font-bold text-leaf">#{s.rank}</span>}
                              <h3 className="text-lg font-semibold">{s.name}</h3>
                              {s.key === "existing" && <Badge>Baseline</Badge>}
                            </div>
                            <p className="mt-0.5 text-sm text-ink-soft">{ex.reason}</p>
                          </div>
                          <div className="shrink-0 text-right">
                            <div className="font-display text-2xl font-bold">{fmt(s.priority_score)}</div>
                            <div className="text-xs text-ink-faint">priority match<InfoTip text="How well this rotation matches your current weights (0–100). It is not a universal measure of the best rotation." /></div>
                          </div>
                        </div>
                        <div className="mt-4">
                          <RotationRibbon items={s.crop_sequence} families={families} />
                        </div>
                        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                          <div><dt className="text-xs text-ink-soft">Irrigation need / year</dt><dd className="font-semibold text-orbit">{fmt(ex.water.average_annual_irrigation_need_mm)} mm</dd></div>
                          <div><dt className="text-xs text-ink-soft">Soil carbon, 5 yr<InfoTip text={TERMS.soc} /></dt><dd className="font-semibold">{signed(sm.soc_change_t_ha?.central, 2)} t C/ha</dd></div>
                          <div><dt className="text-xs text-ink-soft">N balance, 5 yr<InfoTip text={TERMS.nbalance} /></dt><dd className={`font-semibold ${sm.n_balance_cum_kg_ha < 0 ? "text-warn" : "text-leaf-600"}`}>{signed(sm.n_balance_cum_kg_ha)} kg/ha</dd></div>
                          <div><dt className="text-xs text-ink-soft">Crop families</dt><dd className="font-semibold">{sm.family_count}</dd></div>
                        </dl>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button className="btn-secondary py-1.5" onClick={() => setOpen(isOpen ? null : s.key)} aria-expanded={isOpen}>
                            {isOpen ? "Hide details" : "Why and trade-offs"}
                          </button>
                          {s.id && <Link className="btn-secondary py-1.5" href={`/app/simulator?strategy=${s.id}`}>Simulate</Link>}
                          <button className="btn-ghost py-1.5" onClick={() => setCustom(s.rotation.map((r) => ({ ...r })))}>
                            <Pencil className="h-4 w-4" /> Edit as custom
                          </button>
                          {s.id && farm?.can_edit && (
                            <button className="btn-ghost py-1.5" onClick={() => toggleSave(s.id!)}>
                              {saved[s.id] ? <BookmarkCheck className="h-4 w-4 text-leaf" /> : <Bookmark className="h-4 w-4" />} {saved[s.id] ? "Saved" : "Save strategy"}
                            </button>
                          )}
                        </div>
                      </div>
                      {isOpen && (
                        <div className="grid gap-5 border-t border-line bg-paper/60 p-5 text-sm md:grid-cols-2">
                          <div>
                            <h4 className="font-semibold">Objective scores</h4>
                            <div className="mt-2 space-y-2">
                              {OBJECTIVES.map((o) => {
                                const v = s.objectives[o.key];
                                return (
                                  <div key={o.key} className="grid grid-cols-[10rem_1fr_2.5rem] items-center gap-2 text-xs">
                                    <span className="text-ink-soft">{o.label}</span>
                                    {v == null ? <span className="text-ink-faint">Not assessed</span> : <ScoreBar value={v * 100} tone="bg-forest" />}
                                    <span className="text-right tabular-nums">{v == null ? "–" : Math.round(v * 100)}</span>
                                  </div>
                                );
                              })}
                            </div>
                            <h4 className="mt-4 font-semibold">Water</h4>
                            <p className="mt-1 text-ink-soft">About {fmt(ex.water.average_annual_crop_water_mm)} mm of crop water use per year; {Math.round((ex.water.rainfed_supply_fraction ?? 0) * 100)}% met by rain and stored soil water; unmet deficit over five years {fmt(ex.water.unmet_deficit_mm)} mm.</p>
                            <h4 className="mt-4 font-semibold">Economics</h4>
                            <p className="mt-1 text-ink-soft">{ex.economics}</p>
                          </div>
                          <div className="space-y-4">
                            {[["Soil health", ex.soil_health], ["Nutrients", ex.nutrients], ["Climate risks", ex.climate_risks], ["Rotation warnings", ex.rotation_warnings], ["Limitations and assumptions", ex.limitations]].map(([t, items]) =>
                              (items as string[])?.length ? (
                                <div key={t as string}>
                                  <h4 className="font-semibold">{t as string}</h4>
                                  <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-soft">{(items as string[]).map((x) => <li key={x}>{x}</li>)}</ul>
                                </div>
                              ) : null)}
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ol>

              <section className="panel panel-pad">
                <h2 className="section-title">Trade-offs at a glance</h2>
                <div className="mt-3 overflow-x-auto">
                  <table className="table-base min-w-[720px]">
                    <thead>
                      <tr><th>Strategy</th>{OBJECTIVES.map((o) => <th key={o.key}>{o.label.split(" ")[0]}</th>)}<th>Irrigation / yr</th><th>Soil C</th><th>N balance</th></tr>
                    </thead>
                    <tbody>
                      {ranked.map((s) => (
                        <tr key={s.key}>
                          <td className="font-medium">{s.name}</td>
                          {OBJECTIVES.map((o) => <td key={o.key} className="tabular-nums">{s.objectives[o.key] == null ? "–" : Math.round((s.objectives[o.key] as number) * 100)}</td>)}
                          <td>{fmt(s.explanation.water.average_annual_irrigation_need_mm)} mm</td>
                          <td>{signed(s.simulation_summary.soc_change_t_ha?.central, 2)}</td>
                          <td>{signed(s.simulation_summary.n_balance_cum_kg_ha)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 text-xs text-ink-faint">{result.note ?? "The highest-ranked rotation reflects your priorities; it is not universally best."} Consult local extension officers before major changes.</p>
              </section>
              <NextStep href="/app/simulator" title="Simulate five years" body="Compare how soil carbon, nitrogen and water change season by season." />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
