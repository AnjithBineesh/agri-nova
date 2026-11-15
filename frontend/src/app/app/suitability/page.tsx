"use client";

import Link from "next/link";
import { useState } from "react";
import { NextStep, Badge, DemoBanner, ErrorState, InfoTip, Loading, NeedsClimate, NoFarm, Notice, PageHeader, ScoreBar, TERMS } from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { CLASS_LABEL } from "@/lib/format";
import type { SuitabilityResult } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const FACTOR_LABEL: Record<string, string> = {
  temperature: "Temperature", water: "Seasonal water", growing_season: "Season length", rainfall: "Annual rainfall",
  soil_ph: "Soil pH", soil_texture_drainage: "Texture & drainage", nutrients: "Nutrients", salinity: "Salinity",
};
const CLASS_TONE: Record<string, string> = { suitable: "green", moderately_suitable: "orange", unsuitable: "red", insufficient_data: "grey" };

function Row({ r }: { r: SuitabilityResult & { ai_match?: { probability: number; rank: number; of: number } } }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-line first:border-t-0">
      <button className="grid w-full grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 text-left hover:bg-leaf-50/50 md:grid-cols-[1.3fr_0.8fr_0.7fr_1.6fr_9rem]"
              onClick={() => setOpen(!open)} aria-expanded={open}>
        <span><span className="font-semibold">{r.crop_name}</span><span className="ml-2 text-xs text-ink-faint">{r.family}</span></span>
        <span className="flex items-center gap-2">
          <span className="w-9 text-right font-display font-bold">{r.score?.toFixed(0) ?? "–"}</span>
          <span className="hidden w-20 md:block"><ScoreBar value={r.class === "unsuitable" ? Math.min(r.score ?? 0, 40) : r.score} /></span>
        </span>
        <span className="hidden text-sm md:block">
          {r.ai_match ? <span title={`AI model rank ${r.ai_match.rank} of ${r.ai_match.of}`}>
            <span className="font-semibold text-forest">{(r.ai_match.probability * 100).toFixed(r.ai_match.probability < 0.1 ? 1 : 0)}%</span>
            <span className="ml-1 text-xs text-ink-faint">#{r.ai_match.rank}</span>
          </span> : <span className="text-ink-faint">–</span>}
        </span>
        <span className="hidden text-sm text-ink-soft md:block">
          {r.critical_constraints[0] ?? r.limitations[0]?.split(". ")[0] ?? r.reasons[0]?.split(". ")[0]}
        </span>
        <span className="justify-self-end"><Badge tone={CLASS_TONE[r.class]}>{CLASS_LABEL[r.class]}</Badge></span>
      </button>
      {open && (
        <div className="border-t border-line bg-paper/60 px-4 py-4 text-sm">
          {r.critical_constraints.length > 0 && (
            <div className="mb-3 rounded-xl bg-risk-100 px-3 py-2 text-risk">
              <strong>Critical constraint:</strong> {r.critical_constraints.join("; ")}. This overrides the score.
            </div>
          )}
          <table className="table-base">
            <thead><tr><th>Factor</th><th>Weight</th><th>Score</th><th>Explanation</th></tr></thead>
            <tbody>
              {r.factors.map((f) => (
                <tr key={f.name}>
                  <td className="whitespace-nowrap font-medium">{FACTOR_LABEL[f.name] ?? f.name}</td>
                  <td className="text-ink-soft">{Math.round(f.weight * 100)}%</td>
                  <td className="w-28">{f.available ? <div className="flex items-center gap-2"><span className="w-8">{((f.score ?? 0) * 100).toFixed(0)}</span><ScoreBar value={(f.score ?? 0) * 100} /></div> : <Badge>No data</Badge>}</td>
                  <td className="text-ink-soft">{f.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-ink-faint">Data completeness {Math.round(r.data_completeness * 100)}%. Factors without data are excluded and the remaining weights rescaled.</p>
        </div>
      )}
    </div>
  );
}

export default function SuitabilityPage() {
  const { farm, farms, loading: fl } = useFarm();
  const fid = farm?.id;
  const [scenario, setScenario] = useState<string>("baseline");
  const res = useAsync(() => api.post<any>("/api/crops/suitability", { farm_id: fid, scenario: { preset: scenario } }), [fid, scenario], !!fid);
  const [filter, setFilter] = useState("all");

  if (fl) return <Loading />;
  if (!farms.length) return <NoFarm />;
  const data = res.data;
  const noClimate = data && data.data_gaps.some((g: string) => g.startsWith("No weather data"));

  return (
    <div className="space-y-6">
      <PageHeader tag="Plan" title="Crop" accent="suitability" intro="How well each crop matches this farm's temperatures, water, seasons and soil, with the reasons behind every score."
                  actions={
                    <select className="input w-auto" value={scenario} onChange={(e) => setScenario(e.target.value)} aria-label="Climate scenario">
                      <option value="baseline">Recent climate</option>
                      <option value="warmer">+1.5 °C warmer</option>
                      <option value="drier">20% less rainfall</option>
                      <option value="hot_dry">+2 °C and 20% less rainfall</option>
                    </select>} />
      {res.loading ? <Loading label="Assessing crops" /> : res.error ? <ErrorState message={res.error} onRetry={res.reload} /> : noClimate ? <NeedsClimate farmId={fid} /> : data && (
        <>
          <DemoBanner show={data.is_demo_basis} />
          {data.data_gaps.length > 0 && <Notice tone="warn">Missing data: {data.data_gaps.join("; ")}.</Notice>}
          <p className="text-sm text-ink-soft">Seasons: {data.seasons.map((s: any) => s.label).join(", ")} ({data.seasons_source}).
            <InfoTip text={TERMS.suitability} /></p>
          <Notice>
            <span className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <strong>AI match</strong> shows how strongly the crop prediction model picks each crop for the season and where it ranks among all the crops the model knows.{" "}
                {data.ai_match?.available === false ? data.ai_match.message : "It complements the rule-based score; it doesn't replace it."}
              </span>
              <Link href="/app/predict" className="font-semibold underline underline-offset-2">Open crop prediction</Link>
            </span>
          </Notice>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter">
            {["all", "suitable", "moderately_suitable", "unsuitable"].map((k) => (
              <button key={k} className={filter === k ? "btn-primary py-1.5" : "btn-secondary py-1.5"} onClick={() => setFilter(k)}>
                {k === "all" ? "All crops" : CLASS_LABEL[k]}
              </button>
            ))}
          </div>
          {data.seasons.map((s: any) => {
            const rows = (data.results as SuitabilityResult[]).filter((r) => r.season === s.name && (filter === "all" || r.class === filter));
            return (
              <section key={s.name}>
                <h2 className="section-title mb-2">{s.label}</h2>
                <div className="overflow-hidden rounded-panel border border-line bg-white">
                  <div className="hidden grid-cols-[1.3fr_0.8fr_0.7fr_1.6fr_9rem] gap-3 border-b border-line bg-paper/60 px-4 py-2 text-xs font-semibold text-ink-faint md:grid">
                    <span>Crop</span><span>Suitability score</span><span>AI match</span><span>Main reason</span><span className="text-right">Class</span>
                  </div>
                  {rows.length ? rows.map((r) => <Row key={r.crop + r.season} r={r} />) : <p className="px-4 py-6 text-sm text-ink-soft">No crops in this group for this season.</p>}
                </div>
              </section>
            );
          })}
          <p className="text-xs text-ink-faint">{data.methodology.description} Suitable ≥ {data.methodology.thresholds.suitable}, moderately suitable ≥ {data.methodology.thresholds.moderately_suitable}.</p>
          <NextStep href="/app/planner" title="Plan your crop rotation" body="Turn suitable crops into rotations and compare their trade-offs." />
        </>
      )}
    </div>
  );
}
