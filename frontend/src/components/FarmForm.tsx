"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, CloudRain, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { MONTHS, TEXTURES } from "@/lib/format";
import type { Crop, Farm, GeoJSONPolygon, Season } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";
import { ErrorState, Notice, Spinner } from "./ui";

const MapPicker = dynamic(() => import("./MapPicker"), { ssr: false, loading: () => <div className="h-[380px] rounded-panel bg-[#e7ece6]" /> });

type FormState = {
  farm_name: string; country: string; state: string; region: string;
  latitude: string; longitude: string; location_source: "gps" | "map" | "manual";
  boundary: GeoJSONPolygon | null; area_ha: string; soil_type: string; current_crop: string;
  irrigation_type: "none" | "supplemental" | "full"; irrigation_capacity_mm: string;
  residue_management: "removed" | "partial" | "retained"; farming_method: string;
  growing_seasons: Season[]; crop_history: { crop_slug: string; season: string; year: number }[];
};

function initial(f?: Farm): FormState {
  return {
    farm_name: f?.farm_name ?? "", country: f?.country ?? "", state: f?.state ?? "", region: f?.region ?? "",
    latitude: f ? String(f.latitude) : "", longitude: f ? String(f.longitude) : "",
    location_source: f?.location_source ?? "map", boundary: f?.boundary ?? null,
    area_ha: f?.area_ha && f.area_source === "user_entered" ? String(f.area_ha) : "",
    soil_type: f?.soil_type ?? "", current_crop: f?.current_crop ?? "",
    irrigation_type: f?.irrigation_type ?? "none",
    irrigation_capacity_mm: f?.irrigation_capacity_mm != null ? String(f.irrigation_capacity_mm) : "",
    residue_management: f?.residue_management ?? "partial", farming_method: f?.farming_method ?? "",
    growing_seasons: f?.growing_seasons ?? [], crop_history: f?.crop_history ?? [],
  };
}

const STEPS = ["Location", "About the farm", "Water and residues", "Seasons and crops"];

function LocationPreview({ lat, lon }: { lat: number; lon: number }) {
  const [state, setState] = useState<{ loading: boolean; data?: any; error?: string }>({ loading: false });
  const check = async () => {
    setState({ loading: true });
    try {
      setState({ loading: false, data: await api.get<any>(`/api/power/preview?latitude=${lat}&longitude=${lon}`) });
    } catch (e: any) {
      setState({ loading: false, error: e.message });
    }
  };
  return (
    <div className="mt-4 rounded-2xl border border-orbit/20 bg-orbit-50 p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex items-center gap-2 font-semibold text-[#1f4a72]"><CloudRain className="h-4 w-4" /> Check the weather at this location</span>
        <button type="button" className="btn-secondary py-1.5" onClick={check} disabled={state.loading}>
          {state.loading && <Spinner />} {state.data ? "Check again" : "Check weather so far this year"}
        </button>
      </div>
      {state.error && <p className="mt-2 text-risk">{state.error}</p>}
      {state.data?.available && (
        <p className="mt-2 text-[#1f4a72]">
          Since 1 January: <strong>{state.data.rain_total_mm} mm</strong> of rain on {state.data.wet_days} wet days,
          average temperature <strong>{state.data.mean_temp_c} °C</strong>, {state.data.hot_days} days above {state.data.heat_threshold_c} °C
          (daily record to {state.data.last_day}; regional average for about 50 km around the pin).
        </p>
      )}
      {state.data && !state.data.available && <p className="mt-2 text-ink-soft">{state.data.message}</p>}
    </div>
  );
}

export default function FarmForm({ farm, onSaved }: { farm?: Farm; onSaved: (f: Farm) => void }) {
  const [s, setS] = useState<FormState>(() => initial(farm));
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const crops = useAsync(() => api.get<{ crops: Crop[] }>("/api/crops"), []);
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setS((p) => ({ ...p, [k]: v }));
  const lat = s.latitude === "" ? null : Number(s.latitude);
  const lon = s.longitude === "" ? null : Number(s.longitude);
  const cropList = crops.data?.crops ?? [];

  const locationOk = lat !== null && lon !== null && !Number.isNaN(lat) && !Number.isNaN(lon);
  const stepError = (i: number): string | null => {
    if (i === 0 && !locationOk) return "Choose the farm location on the map, share your location, or enter latitude and longitude.";
    if (i === 1 && (!s.farm_name.trim() || s.country.trim().length < 2)) return "Add a farm name and the country.";
    return null;
  };
  const goNext = () => {
    const err = stepError(step);
    setError(err);
    if (!err) {
      setStep(step + 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (step < STEPS.length - 1) {
      goNext();
      return;
    }
    for (const i of [0, 1]) {
      const err = stepError(i);
      if (err) {
        setError(err);
        setStep(i);
        return;
      }
    }
    if (lat === null || lon === null) return;
    setBusy(true);
    const body = {
      farm_name: s.farm_name, country: s.country, state: s.state || null, region: s.region || null,
      latitude: lat, longitude: lon, location_source: s.location_source, boundary: s.boundary,
      boundary_status: s.boundary ? (farm?.boundary_status === "verified" ? "verified" : "user_drawn") : "none",
      area_ha: s.boundary ? null : s.area_ha ? Number(s.area_ha) : null,
      soil_type: s.soil_type || null, current_crop: s.current_crop || null,
      previous_crops: Array.from(new Set(s.crop_history.map((h) => h.crop_slug))),
      irrigation_type: s.irrigation_type,
      irrigation_capacity_mm: s.irrigation_type !== "none" && s.irrigation_capacity_mm ? Number(s.irrigation_capacity_mm) : null,
      growing_seasons: s.growing_seasons, farming_method: s.farming_method || null,
      residue_management: s.residue_management,
      crop_history: s.crop_history.filter((h) => h.crop_slug && h.season),
    };
    try {
      const saved = farm ? await api.put<Farm>(`/api/farms/${farm.id}`, body) : await api.post<Farm>("/api/farms", body);
      onSaved(saved);
    } catch (err: any) {
      setError(err.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  };

  const seasonNames = s.growing_seasons.map((x) => x.name);

  return (
    <form onSubmit={submit} className="space-y-6">
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Steps">
        {STEPS.map((t, i) => (
          <li key={t}>
            <button type="button" onClick={() => (i <= step || farm ? setStep(i) : goNext())}
                    aria-current={step === i ? "step" : undefined}
                    className={`flex w-full items-center gap-2.5 rounded-full border px-3 py-2 text-left text-sm transition-colors ${step === i ? "border-forest bg-forest text-white" : i < step ? "border-line bg-lime-100 text-forest" : "border-line bg-white text-ink-soft"}`}>
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${step === i ? "bg-lime text-forest" : i < step ? "bg-forest text-white" : "bg-paper"}`}>
                {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </span>
              <span className="truncate font-semibold">{t}</span>
            </button>
          </li>
        ))}
      </ol>
      {error && <ErrorState message={error} />}

      {step === 0 && (
      <section className="panel panel-pad">
        <h2 className="section-title">Location</h2>
        <p className="mb-4 mt-1 text-sm text-ink-soft">
          Place a point on the farm, or draw the field boundary for an area calculation. A point marks a location
          only; it is not treated as a field boundary.
        </p>
        <MapPicker lat={lat} lon={lon} boundary={s.boundary}
                   onLocation={(la, lo, src) => setS((p) => ({ ...p, latitude: String(la), longitude: String(lo), location_source: src }))}
                   onBoundary={(b) => set("boundary", b)} />
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <label className="label" htmlFor="lat">Latitude</label>
            <input id="lat" className="input" inputMode="decimal" value={s.latitude} required
                   onChange={(e) => setS((p) => ({ ...p, latitude: e.target.value, location_source: "manual" }))} />
          </div>
          <div>
            <label className="label" htmlFor="lon">Longitude</label>
            <input id="lon" className="input" inputMode="decimal" value={s.longitude} required
                   onChange={(e) => setS((p) => ({ ...p, longitude: e.target.value, location_source: "manual" }))} />
          </div>
          <div className="text-sm">
            <span className="label">Location status</span>
            <p className="text-ink-soft">
              {lat === null ? "Not set" : `Point from ${s.location_source === "gps" ? "your device GPS" : s.location_source === "map" ? "the map" : "manual entry"}`}
              <br />
              {s.boundary ? "Field boundary drawn by you" : "No field boundary"}
            </p>
          </div>
        </div>
        {locationOk && <LocationPreview lat={lat!} lon={lon!} />}
        {farm && (lat !== farm.latitude || lon !== farm.longitude) && (
          <div className="mt-4"><Notice tone="warn">Moving the farm clears its stored weather and field records. They will be retrieved again for the new location.</Notice></div>
        )}
      </section>
      )}

      {step === 1 && (
      <section className="panel panel-pad">
        <h2 className="section-title">Farm details</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="name">Farm name</label>
            <input id="name" className="input" required value={s.farm_name} onChange={(e) => set("farm_name", e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="country">Country</label>
            <input id="country" className="input" required value={s.country} onChange={(e) => set("country", e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="state">State or province</label>
            <input id="state" className="input" value={s.state} onChange={(e) => set("state", e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="region">District or region</label>
            <input id="region" className="input" value={s.region} onChange={(e) => set("region", e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="area">Farm area (hectares)</label>
            <input id="area" className="input" inputMode="decimal" disabled={!!s.boundary} value={s.boundary ? "" : s.area_ha}
                   placeholder={s.boundary ? "Calculated from the boundary" : "Optional"} onChange={(e) => set("area_ha", e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="soiltype">Soil type, if known</label>
            <select id="soiltype" className="input" value={s.soil_type} onChange={(e) => set("soil_type", e.target.value)}>
              <option value="">Not known</option>
              {TEXTURES.map((t) => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="method">Farming method</label>
            <select id="method" className="input" value={s.farming_method} onChange={(e) => set("farming_method", e.target.value)}>
              <option value="">Not specified</option>
              <option value="conventional">Conventional</option>
              <option value="conservation">Conservation agriculture</option>
              <option value="organic">Organic</option>
              <option value="mixed">Mixed crop–livestock</option>
            </select>
          </div>
        </div>
      </section>
      )}

      {step === 2 && (
      <section className="panel panel-pad">
        <h2 className="section-title">Water and residues</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <label className="label" htmlFor="irr">Irrigation</label>
            <select id="irr" className="input" value={s.irrigation_type} onChange={(e) => set("irrigation_type", e.target.value as FormState["irrigation_type"])}>
              <option value="none">None (rainfed)</option>
              <option value="supplemental">Supplemental (some seasons or limited)</option>
              <option value="full">Full irrigation</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="cap">Water available per season (mm)</label>
            <input id="cap" className="input" inputMode="decimal" disabled={s.irrigation_type === "none"} value={s.irrigation_capacity_mm}
                   onChange={(e) => set("irrigation_capacity_mm", e.target.value)} placeholder="Optional" />
            <p className="hint">100 mm on 1 ha is 1,000 m³ of water.</p>
          </div>
          <div>
            <label className="label" htmlFor="res">Crop residues after harvest</label>
            <select id="res" className="input" value={s.residue_management} onChange={(e) => set("residue_management", e.target.value as FormState["residue_management"])}>
              <option value="removed">Mostly removed or burnt</option>
              <option value="partial">Partly left on the field</option>
              <option value="retained">Mostly left or incorporated</option>
            </select>
          </div>
        </div>
      </section>
      )}

      {step === 3 && (
      <section className="panel panel-pad">
        <div className="flex items-center justify-between">
          <h2 className="section-title">Growing seasons</h2>
          <button type="button" className="btn-secondary py-1.5" onClick={() => set("growing_seasons", [...s.growing_seasons, { name: `Season ${s.growing_seasons.length + 1}`, start_month: 6, end_month: 10 }])}>
            <Plus className="h-4 w-4" /> Add season
          </button>
        </div>
        <p className="mt-1 text-sm text-ink-soft">
          For example Kharif (June–October) and Rabi (November–March). If you leave this empty, Agri Nova detects two seasons from your rainfall record and tells you it did.
        </p>
        <div className="mt-4 space-y-2">
          {s.growing_seasons.map((g, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_auto_auto] items-end gap-2">
              <div>
                <label className="label sr-only" htmlFor={`sn${i}`}>Season name</label>
                <input id={`sn${i}`} className="input" value={g.name} aria-label="Season name"
                       onChange={(e) => set("growing_seasons", s.growing_seasons.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
              </div>
              <select className="input w-24" aria-label="Start month" value={g.start_month}
                      onChange={(e) => set("growing_seasons", s.growing_seasons.map((x, j) => j === i ? { ...x, start_month: Number(e.target.value) } : x))}>
                {MONTHS.map((m, k) => <option key={m} value={k + 1}>{m}</option>)}
              </select>
              <select className="input w-24" aria-label="End month" value={g.end_month}
                      onChange={(e) => set("growing_seasons", s.growing_seasons.map((x, j) => j === i ? { ...x, end_month: Number(e.target.value) } : x))}>
                {MONTHS.map((m, k) => <option key={m} value={k + 1}>{m}</option>)}
              </select>
              <button type="button" className="btn-ghost px-2" aria-label="Remove season"
                      onClick={() => set("growing_seasons", s.growing_seasons.filter((_, j) => j !== i))}>
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </section>
      )}

      {step === 3 && (
      <section className="panel panel-pad">
        <h2 className="section-title">Crops</h2>
        <div className="mt-4 max-w-sm">
          <label className="label" htmlFor="cur">Current crop</label>
          <select id="cur" className="input" value={s.current_crop} onChange={(e) => set("current_crop", e.target.value)}>
            <option value="">None or not listed</option>
            {cropList.map((c) => <option key={c.slug} value={c.slug}>{c.crop_name}</option>)}
          </select>
        </div>
        <div className="mt-6 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Previous crops</h3>
          <button type="button" className="btn-secondary py-1.5"
                  onClick={() => set("crop_history", [...s.crop_history, { crop_slug: "", season: seasonNames[0] ?? "Main season", year: new Date().getFullYear() - 1 }])}>
            <Plus className="h-4 w-4" /> Add previous crop
          </button>
        </div>
        <p className="mt-1 text-sm text-ink-soft">Used to evaluate your existing practice and avoid repeating crop families.</p>
        <div className="mt-3 space-y-2">
          {s.crop_history.map((h, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_6rem_auto] gap-2">
              <select className="input" aria-label="Crop" value={h.crop_slug}
                      onChange={(e) => set("crop_history", s.crop_history.map((x, j) => j === i ? { ...x, crop_slug: e.target.value } : x))}>
                <option value="">Choose crop</option>
                <option value="fallow">Fallow</option>
                {cropList.map((c) => <option key={c.slug} value={c.slug}>{c.crop_name}</option>)}
              </select>
              {seasonNames.length ? (
                <select className="input" aria-label="Season" value={h.season}
                        onChange={(e) => set("crop_history", s.crop_history.map((x, j) => j === i ? { ...x, season: e.target.value } : x))}>
                  {seasonNames.map((n) => <option key={n}>{n}</option>)}
                </select>
              ) : (
                <input className="input" aria-label="Season" value={h.season}
                       onChange={(e) => set("crop_history", s.crop_history.map((x, j) => j === i ? { ...x, season: e.target.value } : x))} />
              )}
              <input className="input" aria-label="Year" type="number" min={1950} max={2100} value={h.year}
                     onChange={(e) => set("crop_history", s.crop_history.map((x, j) => j === i ? { ...x, year: Number(e.target.value) } : x))} />
              <button type="button" className="btn-ghost px-2" aria-label="Remove previous crop"
                      onClick={() => set("crop_history", s.crop_history.filter((_, j) => j !== i))}>
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </section>
      )}

      <div className="flex items-center justify-between gap-2">
        <button type="button" className="btn-ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="flex gap-2">
          {farm && step < STEPS.length - 1 && <button type="button" className="btn-secondary" disabled={busy}
            onClick={() => { setStep(STEPS.length - 1); }}>Skip to save</button>}
          {step < STEPS.length - 1 ? (
            <button type="submit" className="btn-primary px-6">Continue <ArrowRight className="h-4 w-4" /></button>
          ) : (
            <button type="submit" className="btn-lime px-6" disabled={busy}>{busy && <Spinner />} {farm ? "Save changes" : "Save farm"}</button>
          )}
        </div>
      </div>
    </form>
  );
}
