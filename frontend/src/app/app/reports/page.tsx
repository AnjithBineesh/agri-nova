"use client";

import { useState } from "react";
import { Download, FileText } from "lucide-react";
import { ErrorState, Loading, NoFarm, PageHeader, Spinner } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { useAsync } from "@/lib/useAsync";

const KINDS = [
  { key: "farmer", title: "Farm report", body: "Plain-language summary: conditions, soil, suitable crops, the rotation strategies and their trade-offs, risks and next steps." },
  { key: "scientific", title: "Scientific report", body: "Adds data provenance, factor-level suitability, season-by-season simulation tables, every model assumption and the methodology." },
];

export default function ReportsPage() {
  const { farm, farms, loading: fl } = useFarm();
  const fid = farm?.id;
  const list = useAsync(() => api.get<any>(`/api/reports/farm/${fid}`), [fid], !!fid);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (fl) return <Loading />;
  if (!farms.length) return <NoFarm />;

  const generate = async (kind: string) => {
    setBusy(kind); setErr(null);
    try {
      const r = await api.post<any>("/api/reports/generate", { farm_id: fid, report_type: kind });
      await downloadFile(r.download_url, `agrinova-${kind}-report-${farm!.farm_name.replace(/\W+/g, "-").toLowerCase()}.pdf`);
      list.reload();
    } catch (e: any) { setErr(e.message); } finally { setBusy(null); }
  };

  return (
    <div className="space-y-6">
      <PageHeader tag="Share" title="Farm" accent="reports" intro="PDF reports built from the latest data, soil profile and rotation strategies for this farm." />
      {err && <ErrorState message={err} />}
      <div className="grid gap-4 md:grid-cols-2">
        {KINDS.map((k) => (
          <section key={k.key} className="panel panel-pad flex flex-col">
            <FileText className="h-5 w-5 text-forest" />
            <h2 className="section-title mt-2">{k.title}</h2>
            <p className="mt-1 flex-1 text-sm text-ink-soft">{k.body}</p>
            <button className="btn-primary mt-4 self-start" disabled={!!busy} onClick={() => generate(k.key)}>
              {busy === k.key ? <Spinner /> : <Download className="h-4 w-4" />} Download {k.title.toLowerCase()}
            </button>
          </section>
        ))}
      </div>
      <section>
        <h2 className="section-title mb-3">Previously generated</h2>
        {list.loading ? <Loading /> : list.error ? <ErrorState message={list.error} /> : !list.data?.reports.length ? (
          <p className="text-sm text-ink-soft">No reports yet.</p>
        ) : (
          <div className="overflow-hidden rounded-panel border border-line bg-white">
            <table className="table-base">
              <thead><tr><th>Report</th><th>Created</th><th></th></tr></thead>
              <tbody>
                {list.data.reports.map((r: any) => (
                  <tr key={r.id}>
                    <td className="capitalize">{r.report_type === "farmer" ? "Farm report" : "Scientific report"}</td>
                    <td>{new Date(r.created_at).toLocaleString()}</td>
                    <td className="text-right">
                      <button className="btn-ghost py-1 text-xs" onClick={() => downloadFile(r.download_url, `agrinova-${r.report_type}-${r.id}.pdf`)}>
                        <Download className="h-3.5 w-3.5" /> PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <p className="text-xs text-ink-faint">Reports are decision support. For high-impact decisions, discuss them with your local agricultural extension officer or an agronomist.</p>
    </div>
  );
}
