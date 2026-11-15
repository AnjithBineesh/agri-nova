"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Download } from "lucide-react";
import { Badge, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFarm } from "@/lib/farm";
import { fmt } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

const FarmsMap = dynamic(() => import("@/components/FarmsMap"), { ssr: false, loading: () => <div className="h-[340px] rounded-panel bg-[#e7ece6]" /> });

export default function OrganisationPage() {
  const { user } = useAuth();
  const { selectFarm } = useFarm();
  const allowed = user && ["organisation", "admin"].includes(user.role);
  const org = useAsync(() => api.get<any>("/api/organisations/me"), [], !!allowed);
  const farms = useAsync(() => api.get<any>("/api/organisations/me/farms"), [], !!allowed);
  const regional = useAsync(() => api.get<any>("/api/organisations/me/regional"), [], !!allowed);

  if (!allowed) return <ErrorState message="The organisation portal is available to organisation accounts." />;
  if (org.loading) return <Loading />;
  if (org.error) return <ErrorState message={org.error} />;
  const list = farms.data?.farms ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title={org.data.name} intro={`${org.data.members.length} members. Farmers join by entering “${org.data.name}” when they register.`}
                  actions={<button className="btn-secondary" onClick={() => downloadFile("/api/organisations/me/report.csv", "agrinova-organisation-farms.csv")}><Download className="h-4 w-4" /> Aggregated report (CSV)</button>} />
      {farms.loading ? <Loading /> : farms.error ? <ErrorState message={farms.error} /> : (
        <>
          {list.length ? <FarmsMap farms={list} /> : <p className="text-sm text-ink-soft">No member farms yet.</p>}
          <section>
            <h2 className="section-title mb-3">Regional indicators</h2>
            <div className="overflow-x-auto rounded-panel border border-line bg-white">
              <table className="table-base min-w-[760px]">
                <thead><tr><th>Region</th><th>Farms</th><th>Area</th><th>Mean rainfall</th><th>Mean temperature</th><th>Irrigated</th><th>Soil data</th><th>Common soil limitations</th></tr></thead>
                <tbody>
                  {(regional.data?.regions ?? []).map((r: any) => (
                    <tr key={r.country + r.state}>
                      <td>{r.state}, {r.country}</td><td>{r.farm_count}</td><td>{fmt(r.total_area_ha, 1)} ha</td>
                      <td>{fmt(r.mean_annual_rainfall_mm)} mm</td><td>{fmt(r.mean_temperature_c, 1)} °C</td>
                      <td>{r.irrigated_farms}</td><td>{r.farms_with_soil_data}/{r.farm_count}</td>
                      <td className="text-ink-soft">{r.common_soil_limitations.map(([l, n]: [string, number]) => `${l} (${n})`).join(", ") || "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section>
            <h2 className="section-title mb-3">Member farms</h2>
            <div className="overflow-x-auto rounded-panel border border-line bg-white">
              <table className="table-base min-w-[900px]">
                <thead><tr><th>Farm</th><th>Owner</th><th>Rainfall</th><th>Temperature</th><th>Soil moisture</th><th>Soil limitations</th><th>Latest strategy</th><th></th></tr></thead>
                <tbody>
                  {list.map((f: any) => (
                    <tr key={f.farm_id}>
                      <td className="font-semibold">{f.farm_name}<div className="text-xs font-normal text-ink-faint">{[f.region, f.state, f.country].filter(Boolean).join(", ")}</div>
                        {f.uses_demo_data && <Badge tone="orange">Demo data</Badge>}</td>
                      <td>{f.owner}</td>
                      <td>{fmt(f.annual_rainfall_mm)} mm</td>
                      <td>{fmt(f.mean_temperature_c, 1)} °C</td>
                      <td>{fmt(f.surface_soil_moisture, 2)}</td>
                      <td className="text-xs text-ink-soft">{f.soil_limitations.join(", ") || (f.soil_data ? "None noted" : "No soil data")}</td>
                      <td className="text-xs text-ink-soft">{f.latest_strategy?.sequence ?? "–"}</td>
                      <td><Link href={`/app/farms/${f.farm_id}`} onClick={() => selectFarm(f.farm_id)} className="text-sm font-semibold text-forest hover:underline">Open</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel panel-pad">
            <h2 className="section-title">Members</h2>
            <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
              {org.data.members.map((m: any) => <li key={m.id}>{m.name} <span className="text-ink-faint">({m.role}, {m.farms} farms)</span></li>)}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
