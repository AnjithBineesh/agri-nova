"use client";

import { useMemo, useState } from "react";
import { Badge, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Crop } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const CATEGORY: Record<string, string> = {
  cereal: "Cereals", legume: "Legumes", oilseed: "Oilseeds", fibre: "Fibre", cash: "Cash crops",
  vegetable: "Vegetables", cover_crop: "Cover crops and green manures",
};

function Range({ r, unit }: { r: any; unit: string }) {
  return <>{r.optimal_min}–{r.optimal_max} {unit} <span className="text-ink-faint">(tolerates {r.absolute_min}–{r.absolute_max})</span></>;
}

function CropDetail({ c }: { c: Crop }) {
  const t = c.climate_requirements.temperature_c;
  const rows: [string, React.ReactNode][] = [
    ["Scientific name", <i key="s">{c.scientific_name}</i>],
    ["Family", c.crop_family],
    ["Growing duration", `about ${c.duration.typical_days} days (ECOCROP range ${c.duration.ecocrop_min_days}–${c.duration.ecocrop_max_days})`],
    ["Planting season", c.planting_season],
    ["Harvest", c.harvest_period],
    ["Temperature", <Range key="t" r={t} unit="°C" />],
    ["Annual rainfall", <Range key="r" r={c.climate_requirements.annual_rainfall_mm} unit="mm" />],
    ["Seasonal water need", c.water_requirement.fao_seasonal_mm ? `${c.water_requirement.fao_seasonal_mm.min}–${c.water_requirement.fao_seasonal_mm.max} mm (FAO)` : "Calculated from crop coefficients"],
    ["Crop coefficient (Kc)", `${c.water_requirement.kc.ini} → ${c.water_requirement.kc.mid} → ${c.water_requirement.kc.end} (${c.water_requirement.kc_source})`],
    ["Soil pH", <Range key="p" r={c.soil_preferences.ph} unit="" />],
    ["Soil texture", `prefers ${c.soil_preferences.texture_optimal.join(", ")}; tolerates ${c.soil_preferences.texture_range.join(", ")}`],
    ["Drainage", `prefers ${c.soil_preferences.drainage_optimal.join(", ")} drained`],
    ["Nitrogen demand", `${c.nutrient_requirements.nitrogen_demand}`],
    ["Nutrients removed per tonne", `N ${c.nutrient_requirements.removal_kg_per_t.N}, P2O5 ${c.nutrient_requirements.removal_kg_per_t.P2O5}, K2O ${c.nutrient_requirements.removal_kg_per_t.K2O} kg (indicative)`],
    ["Nitrogen fixation", c.nitrogen_fixation ? `Yes, about ${Math.round(c.fixation.ndfa_fraction * 100)}% of crop N from the air (indicative)` : "No"],
    ["Roots", `${c.root_characteristics.type}, ${c.root_characteristics.max_depth_m.min}–${c.root_characteristics.max_depth_m.max} m (${c.root_characteristics.source})`],
    ["Residues", c.residue.green_manure ? "Whole crop incorporated as green manure" : `about ${c.residue.residue_to_product_ratio} t residue per t harvested`],
  ];
  return (
    <div className="border-t border-line bg-paper/60 px-5 py-4">
      <dl className="grid gap-x-8 gap-y-2 text-sm md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[11rem_1fr] gap-2"><dt className="text-ink-soft">{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold">Rotation benefits</h4>
          <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">{c.rotation.potential_benefits.map((b: string) => <li key={b}>{b}</li>)}</ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold">Pests and diseases to manage</h4>
          <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">{c.pest_disease_considerations.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
      </div>
      <p className="mt-3 text-sm text-ink-soft">{c.geographic_suitability}</p>
      <div className="mt-3 text-xs text-ink-faint">
        Sources: {c.sources.join("; ")}
      </div>
    </div>
  );
}

export default function CropsPage() {
  const crops = useAsync(() => api.get<{ crops: Crop[] }>("/api/crops"), []);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const list = useMemo(() => (crops.data?.crops ?? []).filter((c) =>
    (!cat || c.category === cat) && (!q || `${c.crop_name} ${c.scientific_name} ${c.crop_family}`.toLowerCase().includes(q.toLowerCase()))), [crops.data, q, cat]);
  const groups = useMemo(() => {
    const g: Record<string, Crop[]> = {};
    list.forEach((c) => (g[c.category] ??= []).push(c));
    return g;
  }, [list]);

  return (
    <div className="space-y-6">
      <PageHeader tag="Crop knowledge" title="Crop" accent="intelligence"
                  intro="Requirements for each crop, taken from FAO ECOCROP and FAO-56. Suitability for your farm is assessed separately using your own climate and soil." />
      <div className="flex flex-wrap gap-3">
        <input className="input max-w-xs" placeholder="Search crops" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search crops" />
        <select className="input w-auto" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {crops.loading ? <Loading /> : crops.error ? <ErrorState message={crops.error} onRetry={crops.reload} /> : (
        Object.entries(groups).map(([k, items]) => (
          <section key={k}>
            <h2 className="section-title mb-2">{CATEGORY[k] ?? k}</h2>
            <div className="overflow-hidden rounded-panel border border-line bg-white">
              {items.map((c, i) => (
                <div key={c.slug} className={i ? "border-t border-line" : ""}>
                  <button className="grid w-full grid-cols-[1fr_auto] items-center gap-3 px-5 py-3 text-left hover:bg-leaf-50/60 sm:grid-cols-[1.4fr_1fr_1fr_1fr_auto]"
                          aria-expanded={open === c.slug} onClick={() => setOpen(open === c.slug ? null : c.slug)}>
                    <span>
                      <span className="font-semibold text-forest">{c.crop_name}</span>
                      <span className="ml-2 text-xs text-ink-faint">{c.crop_family}</span>
                    </span>
                    <span className="hidden text-sm text-ink-soft sm:block">{c.climate_requirements.temperature_c.optimal_min}–{c.climate_requirements.temperature_c.optimal_max} °C</span>
                    <span className="hidden text-sm text-ink-soft sm:block">{c.duration.typical_days} days</span>
                    <span className="hidden sm:block">{c.nitrogen_fixation ? <Badge tone="green">Fixes nitrogen</Badge> : <Badge>N demand {c.nutrient_requirements.nitrogen_demand}</Badge>}</span>
                    <span className="text-sm text-ink-faint">{open === c.slug ? "Hide" : "Details"}</span>
                  </button>
                  {open === c.slug && <CropDetail c={c} />}
                </div>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
