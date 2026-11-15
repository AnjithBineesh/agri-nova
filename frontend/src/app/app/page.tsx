"use client";

import Link from "next/link";
import { ArrowUpRight, BarChart3, BrainCircuit, Check, CloudSun, FileText, FlaskConical, Layers, Repeat } from "lucide-react";
import { Photo } from "@/components/Photo";
import { RotationRibbon } from "@/components/RotationRibbon";
import { WeatherThisYear } from "@/components/WeatherThisYear";
import { DemoBanner, ErrorState, Loading, NoFarm, PageHeader, Stat, TERMS } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFarm } from "@/lib/farm";
import { fmt, seasonText, signed } from "@/lib/format";
import type { Crop, EarthOverview } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const ACTIONS = [
  { href: "/app/predict", icon: BrainCircuit, title: "Crop prediction", body: "AI picks for each season" },
  { href: "/app/soil", icon: Layers, title: "Soil analysis", body: "Enter or upload a soil test" },
  { href: "/app/earth", icon: CloudSun, title: "Field conditions", body: "Weather, rainfall, soil moisture" },
  { href: "/app/suitability", icon: BarChart3, title: "Crop suitability", body: "Which crops fit, and why" },
  { href: "/app/planner", icon: Repeat, title: "Rotation planner", body: "Compare crop sequences" },
  { href: "/app/simulator", icon: FlaskConical, title: "Simulator", body: "Five years, side by side" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const { farm, farms, loading } = useFarm();
  const fid = farm?.id;
  const earth = useAsync(() => api.get<EarthOverview>(`/api/farms/${fid}/earth-data`), [fid], !!fid);
  const soil = useAsync(() => api.get<any>(`/api/farms/${fid}/soil`), [fid], !!fid);
  const recs = useAsync(() => api.get<any>(`/api/rotations/farm/${fid}`), [fid], !!fid);
  const reports = useAsync(() => api.get<any>(`/api/reports/farm/${fid}`), [fid], !!fid);
  const ai = useAsync(() => api.get<any>(`/api/predict/farm/${fid}`), [fid], !!fid);
  const crops = useAsync(() => api.get<{ crops: Crop[] }>("/api/crops"), []);
  const families = Object.fromEntries((crops.data?.crops ?? []).map((c) => [c.slug, c.crop_family]));
  const first = user?.name.split(" ")[0];

  if (loading) return <Loading />;
  if (!farms.length) {
    return (
      <div className="space-y-6">
        <PageHeader title={`Welcome, ${first}.`} accent="Let’s start with your farm." intro="Add a farm and Agri Nova will predict the crops that suit it and plan your rotation strategy." />
        <NoFarm />
      </div>
    );
  }
  const p = earth.data?.profile;
  const top = (recs.data?.saved?.[0] ?? [...(recs.data?.latest ?? [])].sort((a: any, b: any) => (a.scores.rank ?? 99) - (b.scores.rank ?? 99))[0]);
  const steps = [
    { done: true, label: "Create the farm profile", href: `/app/farms/${fid}` },
    { done: !!p?.has_climate, label: "Retrieve weather data for the farm", href: "/app/earth" },
    { done: !!soil.data?.latest, label: "Add soil test values or a report", href: "/app/soil" },
    { done: !!ai.data?.seasons?.some((s: any) => s.result), label: "Get an AI crop prediction", href: "/app/predict" },
    { done: !!p?.has_climate, label: "Review crop suitability", href: "/app/suitability" },
    { done: !!recs.data?.latest?.length, label: "Generate and compare rotations", href: "/app/planner" },
    { done: !!recs.data?.saved?.length, label: "Save your preferred strategy", href: "/app/planner" },
    { done: !!reports.data?.reports?.length, label: "Download a farm report", href: "/app/reports" },
  ];
  const nextStep = steps.find((s) => !s.done);
  const tMean = p?.has_climate ? p.monthly.reduce((a, m) => a + (m.t_mean ?? 0), 0) / 12 : null;

  return (
    <div className="space-y-6">
      <section className="relative isolate overflow-hidden rounded-hero">
        <Photo name="heroWheat" className="absolute inset-0 -z-10" priority />
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-black/65 via-black/35 to-black/10" />
        <div className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[1fr_minmax(0,420px)] lg:items-end">
          <div>
            <span className="inline-flex rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white backdrop-blur">
              {[farm!.region, farm!.state, farm!.country].filter(Boolean).join(", ")}
            </span>
            <h1 className="mt-4 text-[34px] font-bold leading-tight text-white sm:text-[44px]">
              Good to see you, {first}. <span className="accent block">{farm!.farm_name}</span>
            </h1>
            <p className="mt-3 max-w-lg text-white/80">
              {farm!.area_ha ? `${fmt(farm!.area_ha, 1)} ha, ` : ""}
              {farm!.growing_seasons?.length ? farm!.growing_seasons.map(seasonText).join(", ") : "Seasons detected from rainfall"}
            </p>
            {nextStep && (
              <Link href={nextStep.href} className="btn-lime mt-6">Next: {nextStep.label.toLowerCase()} <ArrowUpRight className="h-4 w-4" /></Link>
            )}
          </div>
          {fid && <WeatherThisYear farmId={fid} compact refreshKey={earth.data} />}
        </div>
      </section>

      {earth.error && <ErrorState message={earth.error} onRetry={earth.reload} />}
      <DemoBanner show={!!p?.is_demo} />

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Quick actions">
        {ACTIONS.map((a) => (
          <Link key={a.href} href={a.href} className="group rounded-panel border border-line/80 bg-white p-4 shadow-soft transition-colors hover:border-forest/30">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-paper text-forest group-hover:bg-lime"><a.icon className="h-4 w-4" /></span>
            <span className="mt-3 block text-sm font-bold">{a.title}</span>
            <span className="block text-xs text-ink-faint">{a.body}</span>
          </Link>
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Annual rainfall" value={fmt(p?.annual_precip_mean)} unit="mm" accent="orbit" note={p?.sources?.rainfall?.dataset ?? "Not retrieved"} />
            <Stat label="Average temperature" value={fmt(tMean, 1)} unit="°C" note={p?.sources?.climate?.dataset ?? "Not retrieved"} />
            <Stat label="Surface soil moisture" value={fmt(p?.soil_moisture?.surface?.latest, 2)} unit="m³/m³" tip={TERMS.soilMoisture}
                  note={p?.soil_moisture?.surface ? `Area average, ${p.soil_moisture.surface.latest_date}` : "Not retrieved"} />
            <Stat label="Vegetation (NDVI)" value={fmt(p?.vegetation?.ndvi_latest, 2)} accent="leaf" tip={TERMS.ndvi}
                  note={p?.vegetation?.ndvi_latest_date ? `${p.vegetation.source_label ?? ""} resolution, ${p.vegetation.ndvi_latest_date}` : "Not retrieved"} />
          </section>

          <section className="panel panel-pad">
            <div className="flex items-center justify-between">
              <h2 className="section-title">AI crop prediction</h2>
              <Link href="/app/predict" className="text-sm font-semibold text-forest hover:underline">Open crop prediction</Link>
            </div>
            {ai.data?.seasons?.some((s: any) => s.result) ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {ai.data.seasons.filter((s: any) => s.result).map((s: any) => (
                  <div key={s.name} className="rounded-2xl bg-paper p-4">
                    <p className="text-xs font-semibold text-ink-faint">{s.label}</p>
                    <ol className="mt-2 space-y-1.5">
                      {s.result.predictions.slice(0, 3).map((c: any) => (
                        <li key={c.crop} className="flex items-center gap-3 text-sm">
                          <span className="w-28 shrink-0 font-semibold">{c.name}</span>
                          <span className="h-1.5 flex-1 rounded-full bg-white"><span className="block h-1.5 rounded-full bg-forest" style={{ width: `${Math.max(2, c.probability * 100)}%` }} /></span>
                          <span className="w-10 text-right tabular-nums text-ink-soft">{Math.round(c.probability * 100)}%</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-ink-soft">
                {ai.data?.notes?.length ? ai.data.notes.join(" ") : "Add a soil test and weather data to see which crops the model recommends."}{" "}
                You can also enter values by hand on the crop prediction page.
              </p>
            )}
          </section>

          <section className="panel panel-pad">
            <div className="flex items-center justify-between">
              <h2 className="section-title">{recs.data?.saved?.length ? "Your saved strategy" : "Top-ranked strategy"}</h2>
              <Link href="/app/planner" className="text-sm font-semibold text-forest hover:underline">Open planner</Link>
            </div>
            {top ? (
              <div className="mt-3">
                <p className="mb-3 text-sm text-ink-soft">{top.strategy_name}: {top.explanation.reason}</p>
                <RotationRibbon items={top.crop_sequence} families={families} />
                <p className="mt-3 text-sm text-ink-soft">
                  Over five years: soil carbon {signed(top.scores.simulation_summary.soc_change_t_ha?.central, 2)} t C/ha,
                  N balance {signed(top.scores.simulation_summary.n_balance_cum_kg_ha)} kg/ha before fertiliser,
                  about {fmt(top.explanation.water.average_annual_irrigation_need_mm)} mm irrigation need per year.
                </p>
              </div>
            ) : <p className="mt-2 text-sm text-ink-soft">No strategies yet. Generate them once weather data is available.</p>}
          </section>

          <section className="panel panel-pad">
            <div className="flex items-center justify-between">
              <h2 className="section-title">Soil</h2>
              <Link href="/app/soil" className="text-sm font-semibold text-forest hover:underline">Soil analysis</Link>
            </div>
            {soil.data?.assessment?.available ? (
              <div className="mt-2 text-sm text-ink-soft">
                {soil.data.assessment.limitations.length ? <>Possible limitations: <strong className="text-ink">{soil.data.assessment.limitations.join(", ")}</strong>.</> : "No major limitations in the values provided."}
                {" "}{soil.data.assessment.items.length} parameters assessed.
              </div>
            ) : <p className="mt-2 text-sm text-ink-soft">No soil information yet.</p>}
          </section>
        </div>

        <aside className="panel panel-pad h-fit">
          <h2 className="section-title">Your progress</h2>
          <p className="mt-1 text-xs text-ink-faint">{steps.filter((s) => s.done).length} of {steps.length} steps done</p>
          <div className="mt-3 h-1.5 rounded-full bg-paper"><div className="h-1.5 rounded-full bg-lime" style={{ width: `${(steps.filter((s) => s.done).length / steps.length) * 100}%` }} /></div>
          <ol className="mt-4 space-y-2.5">
            {steps.map((s, i) => (
              <li key={s.label}>
                <Link href={s.href} className="flex items-start gap-3 text-sm hover:text-forest">
                  <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${s.done ? "bg-forest text-lime" : "border border-line text-ink-faint"}`}>
                    {s.done ? <Check className="h-3 w-3" /> : i + 1}
                  </span>
                  <span className={s.done ? "text-ink-soft" : "font-semibold"}>{s.label}</span>
                </Link>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}
