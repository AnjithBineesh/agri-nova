"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, BrainCircuit, ChevronDown, Sprout, Wand2 } from "lucide-react";
import { ModelLimitations, ModelSummary, type ModelCard, type ModelInfo } from "@/components/ModelReport";
import { Badge, DemoBanner, ErrorState, Loading, Notice, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { useAsync } from "@/lib/useAsync";

type Check = { feature: string; label: string; unit: string; value: number; typical_low: number; typical_high: number; status: string };
type Pred = { rank: number; crop: string; name: string; probability: number; crop_db_slug: string | null;
              matching_conditions: number; total_conditions: number; checks: Check[]; summary: string };
type Result = { model: string; algorithm: string; predictions: Pred[]; confidence: "high" | "moderate" | "low";
                out_of_range: { feature: string; message: string }[]; advice: string };
type FarmSeason = { name: string; label: string; inputs: Record<string, number | null>; sources: Record<string, string>; complete: boolean };
type FarmInputs = { seasons: FarmSeason[]; notes: string[]; is_demo_basis: boolean };

const MODELS = {
  crop: { key: "crop_model", endpoint: "/api/predict/crop", tab: "Soil and season", sub: "7 values: N, P, K, pH, temperature, humidity, rainfall" },
  soil: { key: "soil_model", endpoint: "/api/predict/soil", tab: "Detailed soil test", sub: "11 soil values including micronutrients" },
} as const;
type ModelId = keyof typeof MODELS;

const CONF_TONE = { high: "green", moderate: "blue", low: "orange" } as const;

/** A track spanning the range the model learned from, the crop's typical band, and a marker for the user's value. */
function RangeTrack({ c, min, max }: { c: Check; min: number; max: number }) {
  const span = Math.max(max - min, 1e-9);
  const pos = (v: number) => `${Math.min(100, Math.max(0, ((v - min) / span) * 100))}%`;
  const off = c.status !== "typical";
  return (
    <div className="grid grid-cols-[minmax(0,9.5rem)_1fr_5.5rem] items-center gap-3 text-sm">
      <span className="truncate text-ink-soft">{c.label}</span>
      <span className="relative h-5" aria-hidden>
        <span className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-paper" />
        <span className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full bg-leaf/30"
              style={{ left: pos(c.typical_low), width: `calc(${pos(c.typical_high)} - ${pos(c.typical_low)})` }} />
        <span className={`absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full ${off ? "bg-warn" : "bg-forest"}`}
              style={{ left: pos(c.value) }} />
      </span>
      <span className={`text-right tabular-nums ${off ? "font-semibold text-warn" : "text-ink-soft"}`}>
        {c.value}{off ? (c.status === "above" ? " ↑" : " ↓") : ""}
      </span>
      <span className="sr-only">
        Your value {c.value}; typical for this crop {c.typical_low} to {c.typical_high} ({c.status}).
      </span>
    </div>
  );
}

function PredictionCard({ p, info, open, onToggle }: { p: Pred; info?: ModelInfo; open: boolean; onToggle: () => void }) {
  const ranges = Object.fromEntries((info?.features ?? []).map((f) => [f.key, f]));
  return (
    <li className={`rounded-2xl border transition-colors ${open ? "border-forest/30 bg-white" : "border-line bg-white hover:border-forest/20"}`}>
      <button className="flex w-full items-center gap-4 px-4 py-3 text-left" onClick={onToggle} aria-expanded={open}>
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${p.rank === 1 ? "bg-lime text-forest" : "bg-paper text-ink-soft"}`}>
          {p.rank}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="truncate font-bold">{p.name}</span>
            <span className="tabular-nums font-semibold text-forest">{(p.probability * 100).toFixed(p.probability < 0.1 ? 1 : 0)}%</span>
          </span>
          <span className="mt-1.5 block h-1.5 rounded-full bg-paper">
            <span className="block h-1.5 rounded-full bg-forest" style={{ width: `${Math.max(1.5, p.probability * 100)}%` }} />
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-ink-faint transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-line px-4 pb-4 pt-3">
          <p className="text-sm text-ink-soft">{p.summary}</p>
          <div className="mt-3 space-y-1.5">
            {p.checks.map((c) => (
              <RangeTrack key={c.feature} c={c} min={ranges[c.feature]?.min ?? Math.min(c.value, c.typical_low)}
                          max={ranges[c.feature]?.max ?? Math.max(c.value, c.typical_high)} />
            ))}
          </div>
          <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-faint">
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-5 rounded-full bg-leaf/30" /> Typical for {p.name.toLowerCase()} (middle 80% of records)</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-3 w-1 rounded-full bg-forest" /> Your value</span>
          </p>
          {p.crop_db_slug && (
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href="/app/suitability" className="btn-secondary py-1.5 text-sm">Check suitability</Link>
              <Link href="/app/planner" className="btn-secondary py-1.5 text-sm">Plan a rotation <ArrowUpRight className="h-3.5 w-3.5" /></Link>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function PredictPage() {
  const { farm } = useFarm();
  const fid = farm?.id;
  const card = useAsync(() => api.get<ModelCard>("/api/predict/models"), []);
  const farmIn = useAsync(() => api.get<FarmInputs>(`/api/predict/farm/${fid}/inputs`), [fid], !!fid);
  const [model, setModel] = useState<ModelId>("crop");
  const [values, setValues] = useState<Record<ModelId, Record<string, string>>>({ crop: {}, soil: {} });
  const [sources, setSources] = useState<Record<string, string>>({});
  const [season, setSeason] = useState<string | null>(null);
  const [result, setResult] = useState<Record<ModelId, Result | null>>({ crop: null, soil: null });
  const [open, setOpen] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showModel, setShowModel] = useState(false);

  const info: ModelInfo | undefined = card.data?.[MODELS[model].key];
  const v = values[model];
  const missing = (info?.features ?? []).filter((f) => v[f.key] === undefined || v[f.key] === "");

  const fill = (s: FarmSeason) => {
    setSeason(s.name);
    const crop: Record<string, string> = {};
    for (const [k, val] of Object.entries(s.inputs)) crop[k] = val == null ? "" : String(val);
    const soil = { ...values.soil };
    for (const k of ["N", "P", "K", "ph"]) if (s.inputs[k] != null) soil[k] = String(s.inputs[k]);
    setValues({ crop, soil });
    setSources(s.sources);
    setResult({ crop: null, soil: null });
  };

  // Pre-fill from the first complete season of the selected farm.
  useEffect(() => {
    const first = farmIn.data?.seasons.find((s) => s.complete);
    if (first && !season) fill(first);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [farmIn.data]);

  const useTypical = () => {
    if (!info) return;
    const next = { ...v };
    for (const f of missing) next[f.key] = String(f.median);
    setValues({ ...values, [model]: next });
  };

  const run = async () => {
    setBusy(true); setErr(null);
    try {
      const body = Object.fromEntries(Object.entries(v).filter(([, x]) => x !== "").map(([k, x]) => [k, Number(x)]));
      const r = await api.post<Result>(MODELS[model].endpoint, { ...body, top_k: model === "crop" ? 6 : 5 });
      setResult({ ...result, [model]: r }); setOpen(0);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const res = result[model];
  const bySeason = useMemo(() => farmIn.data?.seasons ?? [], [farmIn.data]);

  if (card.loading) return <Loading label="Loading the prediction model" />;
  if (card.error) return <ErrorState message={card.error} onRetry={card.reload} />;

  return (
    <div className="space-y-6">
      <PageHeader
        tag="AI model"
        title="Crop"
        accent="prediction"
        intro="Enter your soil and season conditions, or take them from your farm, and the model ranks the crops whose recorded growing conditions are most like yours."
      />
      <DemoBanner show={!!farmIn.data?.is_demo_basis && !!season} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
        {/* Inputs */}
        <section className="panel panel-pad h-fit">
          <div role="tablist" aria-label="Prediction model" className="grid grid-cols-2 gap-1 rounded-full bg-paper p-1 text-sm">
            {(Object.keys(MODELS) as ModelId[]).map((m) => (
              <button key={m} role="tab" aria-selected={model === m} onClick={() => { setModel(m); setOpen(0); }}
                      className={`rounded-full px-3 py-2 font-semibold transition-colors ${model === m ? "bg-white text-forest shadow-soft" : "text-ink-soft hover:text-ink"}`}>
                {MODELS[m].tab}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-faint">{MODELS[model].sub}</p>

          {farm && model === "crop" && (
            <div className="mt-5">
              <p className="text-sm font-semibold">Fill from {farm.farm_name}</p>
              {farmIn.loading ? <Loading label="Reading your farm" /> : (
                <>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {bySeason.map((s) => (
                      <button key={s.name} onClick={() => fill(s)}
                              className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${season === s.name ? "border-forest bg-forest text-white" : "border-line bg-white hover:border-forest/40"}`}>
                        {s.label}{!s.complete && <span className="ml-1 opacity-70">(partial)</span>}
                      </button>
                    ))}
                  </div>
                  {farmIn.data?.notes.map((n) => <p key={n} className="mt-2 text-xs text-warn">{n}</p>)}
                </>
              )}
            </div>
          )}
          {farm && model === "soil" && (
            <p className="mt-5 text-xs text-ink-soft">
              N, P, K and pH are copied from your soil test when you fill the main tab. Add the micronutrients from your lab report.
            </p>
          )}

          <form className="mt-5 grid grid-cols-2 gap-x-3 gap-y-4" onSubmit={(e) => { e.preventDefault(); run(); }}>
            {(info?.features ?? []).map((f) => (
              <div key={f.key}>
                <label className="label text-xs" htmlFor={`in-${f.key}`}>{f.label}</label>
                <div className="relative">
                  <input id={`in-${f.key}`} type="number" inputMode="decimal" step="any" min={0} required
                         className="input pr-14" value={v[f.key] ?? ""} placeholder={String(f.median)}
                         onChange={(e) => { setValues({ ...values, [model]: { ...v, [f.key]: e.target.value } }); setSeason(null); }} />
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-ink-faint">
                    {f.unit === "soil test value" ? "" : f.unit === "mm per month" ? "mm/mo" : f.unit}
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-tight text-ink-faint">
                  {model === "crop" && sources[f.key] && sources[f.key] !== "missing" && season
                    ? `From your ${sources[f.key]}` : `Model range ${f.min}–${f.max}`}
                </p>
              </div>
            ))}
            <div className="col-span-2 mt-1 flex flex-wrap items-center gap-2">
              <button className="btn-primary" disabled={busy || missing.length > 0} type="submit">
                {busy ? <Spinner /> : <BrainCircuit className="h-4 w-4" />} Predict crops
              </button>
              {missing.length > 0 && (
                <button type="button" className="btn-ghost text-sm" onClick={useTypical}>
                  <Wand2 className="h-4 w-4" /> Fill {missing.length} empty with typical values
                </button>
              )}
            </div>
            {model === "crop" && (
              <p className="col-span-2 text-[11px] leading-snug text-ink-faint">
                Rainfall is the average monthly rainfall during the growing season. N, P and K are soil-test values; values from your farm are converted to kg/ha.
              </p>
            )}
          </form>
        </section>

        {/* Results */}
        <section className="space-y-4">
          {err && <ErrorState message={err} />}
          {!res && !err && (
            <div className="panel flex min-h-[320px] flex-col items-center justify-center gap-3 p-8 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-lime text-forest"><Sprout className="h-5 w-5" /></span>
              <h2 className="section-title">Your ranked crops will appear here</h2>
              <p className="max-w-sm text-sm text-ink-soft">
                {missing.length ? `Fill in the ${missing.length} remaining value${missing.length > 1 ? "s" : ""}, then select Predict crops.` : "Select Predict crops to run the model."}
              </p>
            </div>
          )}
          {res && (
            <div className="panel panel-pad">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="section-title">Best matches{season && model === "crop" ? ` for ${bySeason.find((s) => s.name === season)?.label}` : ""}</h2>
                  <p className="text-xs text-ink-faint">{res.model}, {res.algorithm.toLowerCase()}. Select a crop to see why.</p>
                </div>
                <Badge tone={CONF_TONE[res.confidence]}>{res.confidence[0].toUpperCase() + res.confidence.slice(1)} confidence</Badge>
              </div>
              <p className="mt-3 text-sm text-ink-soft">{res.advice}</p>
              {res.out_of_range.length > 0 && (
                <div className="mt-3"><Notice tone="warn">
                  <span className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                      <strong>Some values are outside what the model learned from</strong>, so treat this ranking with care.
                      <ul className="mt-1 list-disc pl-4">{res.out_of_range.map((w) => <li key={w.feature}>{w.message}</li>)}</ul>
                    </span>
                  </span>
                </Notice></div>
              )}
              <ol className="mt-4 space-y-2">
                {res.predictions.map((p, i) => (
                  <PredictionCard key={p.crop} p={p} info={info} open={open === i} onToggle={() => setOpen(open === i ? -1 : i)} />
                ))}
              </ol>
              <p className="mt-4 text-xs text-ink-faint">
                Probabilities show how closely your conditions resemble each crop&apos;s recorded conditions. They don&apos;t include
                prices, labour, pests or water rights.
              </p>
            </div>
          )}
        </section>
      </div>

      {/* How the model works */}
      {card.data && (
        <section className="panel">
          <button className="flex w-full items-center justify-between gap-4 p-5 text-left sm:p-6" onClick={() => setShowModel(!showModel)} aria-expanded={showModel}>
            <span>
              <span className="section-title block">How the model works</span>
              <span className="mt-0.5 block text-sm text-ink-soft">
                {info?.selected_algorithm}, {((info?.test_split.accuracy ?? 0) * 100).toFixed(1)}% accurate on {info?.test_split.rows} records it never saw during training.
              </span>
            </span>
            <ChevronDown className={`h-5 w-5 shrink-0 text-ink-faint transition-transform ${showModel ? "rotate-180" : ""}`} />
          </button>
          {showModel && info && (
            <div className="space-y-8 border-t border-line p-5 sm:p-6">
              <ModelSummary m={info} title={model === "crop" ? "Soil and season model" : "Detailed soil test model"} />
              <ModelLimitations card={card.data} />
              <p className="text-xs text-ink-faint">Trained {new Date(card.data.trained_at).toLocaleDateString()}.</p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
