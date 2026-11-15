"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Badge, ErrorState, Loading, NoFarm, PageHeader } from "@/components/ui";
import { useFarm } from "@/lib/farm";
import { fmt } from "@/lib/format";

export default function FarmsPage() {
  const { farms, loading, error, reload, selectFarm, farm: current } = useFarm();
  return (
    <div>
      <PageHeader tag="Your farm" title="Your" accent="farms" intro="Each farm has its own location, soil profile, crop predictions and rotation plans."
                  actions={<Link href="/app/farms/new" className="btn-primary"><Plus className="h-4 w-4" /> Add farm</Link>} />
      {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={reload} /> : !farms.length ? <NoFarm /> : (
        <div className="overflow-x-auto rounded-panel border border-line bg-white">
          <table className="table-base min-w-[760px]">
            <thead>
              <tr><th>Farm</th><th>Location</th><th>Area</th><th>Boundary</th><th>Irrigation</th><th>Current crop</th><th></th></tr>
            </thead>
            <tbody>
              {farms.map((f) => (
                <tr key={f.id} className={current?.id === f.id ? "bg-leaf-50/60" : ""}>
                  <td>
                    <Link href={`/app/farms/${f.id}`} className="font-semibold text-forest hover:underline">{f.farm_name}</Link>
                    {!f.can_edit && <div className="text-xs text-ink-faint">Owner: {f.owner_name}</div>}
                  </td>
                  <td className="text-ink-soft">{[f.region, f.state, f.country].filter(Boolean).join(", ")}
                    <div className="text-xs text-ink-faint">{f.latitude.toFixed(4)}, {f.longitude.toFixed(4)}</div></td>
                  <td>{f.area_ha ? fmt(f.area_ha, 2, "ha") : "–"}</td>
                  <td>{f.boundary_status === "none" ? <Badge>Point only</Badge> : <Badge tone="green">{f.boundary_status === "verified" ? "Verified" : "Drawn"}</Badge>}</td>
                  <td className="capitalize">{f.irrigation_type}</td>
                  <td className="capitalize">{f.current_crop?.replace("_", " ") ?? "–"}</td>
                  <td className="text-right">
                    {current?.id === f.id ? <span className="text-xs text-ink-faint">Selected</span> :
                      <button className="btn-ghost py-1 text-xs" onClick={() => selectFarm(f.id)}>Select</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
