"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { ModelLimitations, ModelSummary, type ModelCard } from "@/components/ModelReport";
import { Badge, DataTypeTag, ErrorState, Loading, PageHeader, Spinner } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFarm } from "@/lib/farm";
import { useAsync } from "@/lib/useAsync";

const FACTORS = ["temperature", "water", "growing_season", "rainfall", "soil_ph", "soil_texture_drainage", "nutrients", "salinity"];

export default function ResearchPage() {
  const { user } = useAuth();
  const { farm } = useFarm();
  const allowed = user && ["researcher", "admin"].includes(user.role);
  const assumptions = useAsync(() => api.get<any>("/api/research/model-assumptions"), [], !!allowed);
  const datasets = useAsync(() => api.get<any>("/api/research/datasets"), [], !!allowed);
  const agg = useAsync(() => api.get<any>("/api/research/aggregate"), [], !!allowed);
  const ml = useAsync(() => api.get<ModelCard>("/api/predict/models"), [], !!allowed);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);
  const [sens, setSens] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!allowed) return <ErrorState message="The researcher portal is available to researcher accounts." />;
  if (assumptions.loading) return <Loading />;
  if (assumptions.error) return <ErrorState message={assumptions.error} />;
  const a = assumptions.data;
  const w = weights ?? a.suitability.weights;

  const runSens = async () => {
    if (!farm) return;
    setBusy(true); setErr(null);
    try { setSens(await api.post("/api/research/suitability-sensitivity", { farm_id: farm.id, weights: w })); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Researcher portal" intro="Machine-learning model evaluation, model assumptions, sensitivity analysis and data exports." />
      {err && <ErrorState message={err} />}

      {ml.data && (
        <section className="panel panel-pad space-y-8">
          <div>
            <h2 className="section-title">Machine-learning models</h2>
            <p className="mt-1 text-sm text-ink-soft">
              Each model was trained on 80% of its records with 5-fold stratified cross-validation, and scored once on the
              remaining 20%. Trained {new Date(ml.data.trained_at).toLocaleString()}.
            </p>
          </div>
          <ModelSummary m={ml.data.crop_model} title="Crop prediction model (soil and season)" />
          <ModelSummary m={ml.data.soil_model} title="Detailed soil test model" />
          <ModelLimitations card={ml.data} />
        </section>
      )}

      <section className="panel panel-pad">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="section-title">Suitability weight sensitivity</h2>
          <span className="text-sm text-ink-soft">Farm: {farm?.farm_name ?? "none selected"}</span>
        </div>
        <p className="mt-1 text-sm text-ink-soft">Change factor weights and compare scores with the defaults for the selected farm.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          {FACTORS.map((f) => (
            <div key={f}>
              <label className="label text-xs capitalize" htmlFor={`f-${f}`}>{f.replace(/_/g, " ")}</label>
              <input id={`f-${f}`} type="number" step="0.05" min={0} className="input" value={w[f]}
                     onChange={(e) => setWeights({ ...w, [f]: Number(e.target.value) })} />
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <button className="btn-primary" disabled={busy || !farm} onClick={runSens}>{busy && <Spinner />} Run comparison</button>
          {weights && <button className="btn-ghost" onClick={() => { setWeights(null); setSens(null); }}>Reset to defaults</button>}
        </div>
        {sens && (
          <div className="mt-4 max-h-96 overflow-auto rounded-xl border border-line">
            <table className="table-base">
              <thead className="sticky top-0 bg-white"><tr><th>Crop</th><th>Season</th><th>Default</th><th>Custom</th><th>Change</th><th>Class change</th></tr></thead>
              <tbody>
                {sens.rows.sort((x: any, y: any) => Math.abs(y.delta ?? 0) - Math.abs(x.delta ?? 0)).map((r: any) => (
                  <tr key={r.crop + r.season}>
                    <td>{r.crop}</td><td>{r.season}</td><td>{r.default_score ?? "–"}</td><td>{r.custom_score ?? "–"}</td>
                    <td className={r.delta > 0 ? "text-leaf-600" : r.delta < 0 ? "text-risk" : ""}>{r.delta ?? "–"}</td>
                    <td>{r.default_class !== r.custom_class ? <Badge tone="orange">{r.default_class} → {r.custom_class}</Badge> : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel panel-pad">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="section-title">Export observations</h2>
          {farm && (
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => downloadFile(`/api/research/farms/${farm.id}/export?format=csv`, `agrinova-farm${farm.id}-observations.csv`)}><Download className="h-4 w-4" /> CSV</button>
              <button className="btn-secondary" onClick={() => downloadFile(`/api/research/farms/${farm.id}/export?format=json`, `agrinova-farm${farm.id}-observations.json`)}><Download className="h-4 w-4" /> JSON</button>
            </div>
          )}
        </div>
        <p className="mt-1 text-sm text-ink-soft">Every stored value with its record, unit, date, resolution, quality flag, data type and demonstration flag, for farms you are authorised to view.</p>
      </section>

      <section className="panel panel-pad">
        <h2 className="section-title">Model assumptions</h2>
        <div className="mt-3 grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold">Soil organic carbon</h3>
            <dl className="mt-2 grid grid-cols-2 gap-1 text-sm">
              {Object.entries(a.organic_carbon).filter(([, v]) => typeof v !== "object").map(([k, v]) => (
                <div key={k} className="contents"><dt className="text-ink-soft">{k.replace(/_/g, " ")}</dt><dd>{String(v)}</dd></div>
              ))}
            </dl>
          </div>
          <div>
            <h3 className="text-sm font-semibold">Water balance</h3>
            <dl className="mt-2 space-y-1 text-sm">
              {Object.entries(a.water_balance).map(([k, v]) => (
                <div key={k}><dt className="inline text-ink-soft">{k.replace(/_/g, " ")}: </dt><dd className="inline">{Array.isArray(v) ? v.join(", ") : String(v)}</dd></div>
              ))}
            </dl>
            <h3 className="mt-4 text-sm font-semibold">Shared pest and disease host groups</h3>
            <ul className="mt-1 space-y-1 text-sm text-ink-soft">
              {Object.entries<string[]>(a.rotation_rules.shared_host_groups).map(([g, crops]) => <li key={g}><strong className="text-ink">{g}:</strong> {crops.join(", ")}</li>)}
            </ul>
          </div>
        </div>
      </section>

      <section>
        <h2 className="section-title mb-3">Record catalogue</h2>
        {datasets.data && (
          <div className="overflow-x-auto rounded-panel border border-line bg-white">
            <table className="table-base min-w-[640px]">
              <thead><tr><th>Record</th><th>Resolution</th><th>Frequency</th><th>Type</th><th>Status</th></tr></thead>
              <tbody>
                {datasets.data.datasets.map((d: any) => (
                  <tr key={d.key}>
                    <td className="font-semibold">{d.display_name}</td>
                    <td className="text-xs">{d.display_resolution}</td>
                    <td className="text-xs text-ink-soft">{d.temporal_resolution}</td>
                    <td><DataTypeTag type={d.data_type} /></td>
                    <td><Badge tone={d.integration === "integrated" ? "green" : "grey"}>{d.integration === "integrated" ? "In use" : "Planned"}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel panel-pad">
        <h2 className="section-title">Aggregated indicators</h2>
        {agg.data && (
          <>
            {agg.data.groups.length ? (
              <table className="table-base mt-3">
                <thead><tr><th>Country</th><th>Farms</th><th>Irrigated share</th><th>Median area (ha)</th></tr></thead>
                <tbody>{agg.data.groups.map((g: any) => <tr key={g.country}><td>{g.country}</td><td>{g.farm_count}</td><td>{Math.round(g.irrigated_share * 100)}%</td><td>{g.median_area_ha}</td></tr>)}</tbody>
              </table>
            ) : <p className="mt-2 text-sm text-ink-soft">Not enough farms yet to show anonymised groups.</p>}
            <p className="mt-2 text-xs text-ink-faint">{agg.data.note}</p>
          </>
        )}
      </section>
    </div>
  );
}
