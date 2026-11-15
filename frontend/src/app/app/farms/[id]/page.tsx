"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { Badge, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useFarm } from "@/lib/farm";
import { fmt, seasonText } from "@/lib/format";
import type { Farm } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const MapPicker = dynamic(() => import("@/components/MapPicker"), { ssr: false });

export default function FarmDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { reload, selectFarm } = useFarm();
  const farm = useAsync(() => api.get<Farm>(`/api/farms/${id}`), [id]);
  const [confirm, setConfirm] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const f = farm.data;

  const remove = async () => {
    try {
      await api.del(`/api/farms/${id}`);
      await reload();
      router.push("/app/farms");
    } catch (e: any) {
      setErr(e.message);
    }
  };

  if (farm.loading) return <Loading />;
  if (farm.error || !f) return <ErrorState message={farm.error ?? "Farm not found"} />;
  const rows: [string, React.ReactNode][] = [
    ["Location", `${[f.region, f.state, f.country].filter(Boolean).join(", ")} (${f.latitude.toFixed(5)}, ${f.longitude.toFixed(5)})`],
    ["Location source", f.location_source === "gps" ? "Device GPS" : f.location_source === "map" ? "Selected on map" : "Entered manually"],
    ["Field boundary", f.boundary_status === "none" ? "Not drawn: the farm is represented by a point" : f.boundary_status === "verified" ? "Verified polygon" : "Drawn by the farmer"],
    ["Area", f.area_ha ? `${fmt(f.area_ha, 2, "ha")} (${f.area_source === "computed_from_boundary" ? "calculated from boundary" : "entered by farmer"})` : "Not provided"],
    ["Irrigation", f.irrigation_type === "none" ? "Rainfed" : `${f.irrigation_type}${f.irrigation_capacity_mm ? `, about ${f.irrigation_capacity_mm} mm per season` : ""}`],
    ["Residues", f.residue_management],
    ["Growing seasons", f.growing_seasons?.length ? f.growing_seasons.map(seasonText).join("; ") : "Detected automatically from rainfall"],
    ["Current crop", f.current_crop?.replace("_", " ") ?? "–"],
    ["Previous crops", f.crop_history.length ? f.crop_history.map((h) => `${h.crop_slug.replace("_", " ")} (${h.season} ${h.year})`).join(", ") : "–"],
  ];
  return (
    <div>
      <PageHeader title={f.farm_name} intro={f.can_edit ? undefined : `Shared with your organisation by ${f.owner_name}. View only.`}
                  actions={<>
                    <button className="btn-secondary" onClick={() => { selectFarm(f.id); router.push("/app/earth"); }}>Open Field conditions</button>
                    {f.can_edit && <Link href={`/app/farms/${f.id}/edit`} className="btn-primary"><Pencil className="h-4 w-4" /> Edit</Link>}
                  </>} />
      {err && <ErrorState message={err} />}
      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <MapPicker lat={f.latitude} lon={f.longitude} boundary={f.boundary} readOnly height={420} />
        <div className="panel panel-pad">
          <dl className="space-y-3 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="grid grid-cols-[9rem_1fr] gap-2">
                <dt className="text-ink-soft">{k}</dt>
                <dd className="capitalize-first">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-4 flex gap-2">
            {f.boundary_status === "none" ? <Badge tone="orange">Point location only</Badge> : <Badge tone="green">Field polygon</Badge>}
          </div>
          {f.can_edit && (
            <div className="mt-6 border-t border-line pt-4">
              {!confirm ? (
                <button className="btn-ghost text-risk" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" /> Delete farm</button>
              ) : (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  This deletes the farm, its soil data, observations and plans.
                  <button className="btn bg-risk text-white hover:bg-risk/90" onClick={remove}>Delete farm</button>
                  <button className="btn-ghost" onClick={() => setConfirm(false)}>Keep farm</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
