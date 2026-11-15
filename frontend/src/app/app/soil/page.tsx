"use client";

import { useRef, useState } from "react";
import { Download, FileUp } from "lucide-react";
import { NextStep, Badge, ErrorState, Loading, NoFarm, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { TEXTURES } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

const FIELDS = [
  { key: "ph", label: "Soil pH", unit: null, step: "0.1" },
  { key: "electrical_conductivity", label: "Electrical conductivity", unit: "dS/m", step: "0.01" },
  { key: "organic_carbon", label: "Organic carbon", unit: "%", step: "0.01" },
  { key: "organic_matter", label: "Soil organic matter (if measured)", unit: "%", step: "0.01" },
  { key: "nitrogen", label: "Available nitrogen", unitKey: "nitrogen_unit", step: "1" },
  { key: "phosphorus", label: "Available phosphorus", unitKey: "phosphorus_unit", step: "0.1" },
  { key: "potassium", label: "Available potassium", unitKey: "potassium_unit", step: "1" },
  { key: "soil_depth_cm", label: "Soil depth", unit: "cm", step: "1" },
  { key: "water_holding_capacity", label: "Available water capacity", unit: "mm per m", step: "1" },
] as const;

const STATUS_STYLE: Record<string, string> = {
  good: "border-l-leaf", caution: "border-l-warn", constraint: "border-l-risk", info: "border-l-orbit", unknown: "border-l-line",
};

type SoilForm = Record<string, any>;
const EMPTY: SoilForm = { nitrogen_unit: "kg/ha", phosphorus_unit: "kg/ha", potassium_unit: "kg/ha", phosphorus_method: "unknown", value_status: {} };

function SoilFields({ form, setForm }: { form: SoilForm; setForm: (f: SoilForm) => void }) {
  const set = (k: string, v: any) => setForm({ ...form, [k]: v });
  const setStatus = (k: string, v: string) => setForm({ ...form, value_status: { ...form.value_status, [k]: v } });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {FIELDS.map((f) => (
        <div key={f.key}>
          <label className="label" htmlFor={f.key}>{f.label}</label>
          <div className="flex gap-2">
            <input id={f.key} type="number" step={f.step} className="input" value={form[f.key] ?? ""}
                   onChange={(e) => set(f.key, e.target.value === "" ? null : Number(e.target.value))} placeholder="Not measured" />
            {"unitKey" in f ? (
              <select className="input w-28" aria-label={`${f.label} unit`} value={form[f.unitKey]} onChange={(e) => set(f.unitKey, e.target.value)}>
                <option value="kg/ha">kg/ha</option><option value="mg/kg">mg/kg</option><option value="ppm">ppm</option><option value="lb/acre">lb/acre</option>
              </select>
            ) : f.unit ? <span className="self-center whitespace-nowrap text-sm text-ink-faint">{f.unit}</span> : null}
          </div>
          {form[f.key] != null && (
            <div className="mt-1 flex gap-3 text-xs text-ink-soft">
              {["measured", "estimated"].map((s) => (
                <label key={s} className="inline-flex items-center gap-1">
                  <input type="radio" name={`st-${f.key}`} className="accent-forest" checked={(form.value_status?.[f.key] ?? "measured") === s}
                         onChange={() => setStatus(f.key, s)} /> {s === "measured" ? "Measured" : "Estimated"}
                </label>
              ))}
            </div>
          )}
        </div>
      ))}
      <div>
        <label className="label" htmlFor="pm">Phosphorus test method</label>
        <select id="pm" className="input" value={form.phosphorus_method ?? "unknown"} onChange={(e) => set("phosphorus_method", e.target.value)}>
          <option value="unknown">Not stated</option><option value="olsen">Olsen</option><option value="bray1">Bray-1</option><option value="mehlich3">Mehlich-3</option>
        </select>
      </div>
      <div>
        <label className="label" htmlFor="tex">Soil texture</label>
        <select id="tex" className="input" value={form.soil_texture ?? ""} onChange={(e) => set("soil_texture", e.target.value || null)}>
          <option value="">Not known</option>
          {TEXTURES.map((t) => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
        </select>
      </div>
      <div>
        <label className="label" htmlFor="dr">Drainage</label>
        <select id="dr" className="input" value={form.drainage ?? ""} onChange={(e) => set("drainage", e.target.value || null)}>
          <option value="">Not known</option><option value="poorly">Poorly drained (waterlogs)</option><option value="imperfectly">Imperfectly drained</option>
          <option value="well">Well drained</option><option value="excessively">Excessively drained (dries fast)</option>
        </select>
      </div>
      <div>
        <label className="label" htmlFor="md">Sampling or test date</label>
        <input id="md" type="date" className="input" value={form.measurement_date ?? ""} onChange={(e) => set("measurement_date", e.target.value || null)} />
      </div>
    </div>
  );
}

export default function SoilPage() {
  const { farm, farms, loading: fl } = useFarm();
  const fid = farm?.id;
  const soil = useAsync(() => api.get<any>(`/api/farms/${fid}/soil`), [fid], !!fid);
  const [mode, setMode] = useState<"view" | "manual" | "review">("view");
  const [form, setForm] = useState<SoilForm>(EMPTY);
  const [report, setReport] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  if (fl) return <Loading />;
  if (!farms.length) return <NoFarm />;

  const saveManual = async () => {
    setBusy(true); setErr(null);
    try {
      await api.post(`/api/farms/${fid}/soil`, form);
      setMode("view"); setForm(EMPTY); soil.reload();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const upload = async (file: File) => {
    setBusy(true); setErr(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const rep = await api.upload<any>(`/api/farms/${fid}/soil/upload`, fd);
      const p = rep.extracted_values?.parameters ?? {};
      const f: SoilForm = { ...EMPTY, value_status: {} };
      for (const [k, v] of Object.entries<any>(p)) {
        f[k] = v.value;
        if (["nitrogen", "phosphorus", "potassium"].includes(k) && v.unit && ["kg/ha", "mg/kg", "ppm"].includes(v.unit)) f[`${k}_unit`] = v.unit;
        if (k === "phosphorus" && v.method) f.phosphorus_method = v.method;
      }
      f.measurement_date = rep.report_date ?? null;
      f.laboratory = rep.laboratory ?? "";
      f.report_date = rep.report_date ?? null;
      setForm(f); setReport(rep); setMode("review"); soil.reload();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const confirm = async () => {
    setBusy(true); setErr(null);
    try {
      await api.post(`/api/soil/${report.id}/confirm`, form);
      setMode("view"); setReport(null); setForm(EMPTY); soil.reload();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const reject = async () => {
    await api.post(`/api/soil/${report.id}/reject`);
    setMode("view"); setReport(null); setForm(EMPTY); soil.reload();
  };

  const a = soil.data?.assessment;
  const latest = soil.data?.latest;
  return (
    <div className="space-y-6">
      <PageHeader tag="Your soil" title="Soil" accent="analysis"
                  intro="Soil values come only from your soil tests. Weather records cannot tell us pH or available nutrients, so nothing here is estimated from imagery."
                  actions={farm?.can_edit ? <>
                    <button className="btn-secondary" onClick={() => { setForm(latest ? { ...EMPTY, ...latest, value_status: latest.value_status ?? {} } : EMPTY); setMode("manual"); }}>Enter values</button>
                    <button className="btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}>{busy && mode !== "manual" ? <Spinner /> : <FileUp className="h-4 w-4" />} Upload soil report</button>
                    <input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg" className="hidden"
                           onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
                  </> : undefined} />
      {err && <ErrorState message={err} />}

      {mode === "manual" && (
        <section className="panel panel-pad">
          <h2 className="section-title">Enter soil test values</h2>
          <p className="mb-4 mt-1 text-sm text-ink-soft">Leave anything you have not measured empty. Mark values you estimated so they are treated with caution.</p>
          <SoilFields form={form} setForm={setForm} />
          <div className="mt-6 flex gap-2">
            <button className="btn-primary" disabled={busy} onClick={saveManual}>{busy && <Spinner />} Save soil profile</button>
            <button className="btn-ghost" onClick={() => setMode("view")}>Cancel</button>
          </div>
        </section>
      )}

      {mode === "review" && report && (
        <section className="panel panel-pad">
          <h2 className="section-title">Check the values read from your report</h2>
          <Notice tone="warn">
            These values were read automatically ({report.extraction_method === "ocr" ? "text recognition from an image" : "text inside the PDF"}) and may contain mistakes.
            Compare each one with your report and correct it before saving. Nothing is stored as a laboratory measurement until you confirm.
          </Notice>
          {report.extracted_values?.error && <div className="mt-3"><ErrorState message={report.extracted_values.error} /></div>}
          <p className="my-4 text-sm text-ink-soft">
            Found {report.extracted_values?.parameter_count ?? 0} parameters in <strong>{report.original_filename}</strong>.
            {Object.entries<any>(report.extracted_values?.parameters ?? {}).length > 0 && " Text matched: "}
            {Object.entries<any>(report.extracted_values?.parameters ?? {}).map(([k, v]) => (
              <span key={k} className="mr-2 inline-block rounded bg-paper px-1.5 text-xs">{v.context}</span>
            ))}
          </p>
          <div className="mb-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="lab">Laboratory</label>
              <input id="lab" className="input" value={form.laboratory ?? ""} onChange={(e) => setForm({ ...form, laboratory: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="rd">Report date</label>
              <input id="rd" type="date" className="input" value={form.report_date ?? ""} onChange={(e) => setForm({ ...form, report_date: e.target.value || null })} />
            </div>
          </div>
          <SoilFields form={form} setForm={setForm} />
          <div className="mt-6 flex flex-wrap gap-2">
            <button className="btn-primary" disabled={busy} onClick={confirm}>{busy && <Spinner />} Confirm and save</button>
            <button className="btn-ghost" onClick={reject}>Discard extracted values</button>
          </div>
        </section>
      )}

      {soil.loading ? <Loading /> : soil.error ? <ErrorState message={soil.error} onRetry={soil.reload} /> : a && !a.available ? (
        mode === "view" && <section className="panel panel-pad"><h2 className="section-title">No soil information yet</h2>
          <p className="mt-1 text-sm text-ink-soft">{a.message} Recommendations still work without it, but soil pH, texture and nutrient factors are left out and data completeness is lower.</p></section>
      ) : a && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
            <span>Source:</span>
            <Badge tone={latest.data_source === "lab_report_confirmed" ? "green" : "forest"}>
              {latest.data_source === "lab_report_confirmed" ? "Confirmed laboratory report" : "Farmer-provided values"}
            </Badge>
            {latest.measurement_date && <span>tested {latest.measurement_date}</span>}
            <span>{Math.round(a.completeness * 6)} of 6 key soil tests recorded</span>
          </div>
          {a.limitations.length > 0 && (
            <Notice tone="warn"><strong>Possible limitations:</strong> {a.limitations.join(", ")}.</Notice>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {a.items.map((it: any) => (
              <div key={it.parameter} className={`panel border-l-4 p-4 ${STATUS_STYLE[it.status] ?? ""}`}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold">{it.parameter}</h3>
                  <span className="font-display text-lg font-bold">{it.value} <span className="text-xs font-normal text-ink-soft">{it.unit}</span></span>
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <Badge tone={{ good: "green", caution: "orange", constraint: "red", info: "blue" }[it.status as string] ?? "grey"}>{it.class}</Badge>
                  {a.value_status?.[it.key] === "estimated" && <Badge tone="orange">Estimated value</Badge>}
                </div>
                <p className="mt-2 text-sm text-ink-soft">{it.explanation}</p>
                <p className="mt-1 text-xs text-ink-faint">{it.reference}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-ink-faint">{a.methodology} Rating system: {a.rating_system}.</p>
          {a.notes?.map((n: string) => <p key={n} className="text-xs text-ink-faint">{n}</p>)}
        </section>
      )}

      {soil.data?.reports?.length > 0 && (
        <section>
          <h2 className="section-title mb-3">Uploaded reports</h2>
          <div className="overflow-x-auto rounded-panel border border-line bg-white">
            <table className="table-base min-w-[640px]">
              <thead><tr><th>File</th><th>Uploaded</th><th>Laboratory</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {soil.data.reports.map((r: any) => (
                  <tr key={r.id}>
                    <td>{r.original_filename}</td>
                    <td>{r.created_at.slice(0, 10)}</td>
                    <td className="text-ink-soft">{r.laboratory ?? "–"}</td>
                    <td><Badge tone={r.verification_status === "confirmed" ? "green" : r.verification_status === "pending" ? "orange" : "grey"}>{r.verification_status}</Badge></td>
                    <td className="text-right">
                      <button className="btn-ghost py-1 text-xs" onClick={() => downloadFile(`/api/soil/${r.id}/file`, r.original_filename)}>
                        <Download className="h-3.5 w-3.5" /> Original
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {latest && <NextStep href="/app/suitability" title="See which crops fit your farm" body="Scores combine your farm's weather record with these soil values." />}
    </div>
  );
}
