"use client";

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import { Crosshair, MapPin, PenLine, Search, Trash2, Undo2 } from "lucide-react";
import type { GeoJSONPolygon } from "@/lib/types";
import { Spinner } from "./ui";

interface Props {
  lat: number | null;
  lon: number | null;
  boundary: GeoJSONPolygon | null;
  onLocation?: (lat: number, lon: number, source: "gps" | "map") => void;
  onBoundary?: (b: GeoJSONPolygon | null) => void;
  readOnly?: boolean;
  height?: number;
}

/**
 * Leaflet map for selecting a farm point and optionally drawing a field polygon.
 * A point is only a location; a polygon is shown separately as a user-drawn boundary.
 */
export default function MapPicker({ lat, lon, boundary, onLocation, onBoundary, readOnly, height = 380 }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const L = useRef<typeof Leaflet | null>(null);
  const layers = useRef<{ point?: Leaflet.Layer; poly?: Leaflet.Layer; draft?: Leaflet.Layer }>({});
  const [mode, setMode] = useState<"pin" | "draw">("pin");
  const [draft, setDraft] = useState<[number, number][]>([]);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<{ display_name: string; lat: string; lon: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const leaflet = await import("leaflet");
      if (cancelled || !el.current || map.current) return;
      L.current = leaflet;
      const m = leaflet.map(el.current, { zoomControl: true, attributionControl: true })
        .setView(lat !== null && lon !== null ? [lat, lon] : [20, 10], lat !== null ? 14 : 2);
      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(m);
      if (!readOnly) {
        m.on("click", (e: Leaflet.LeafletMouseEvent) => {
          const p: [number, number] = [Number(e.latlng.lat.toFixed(6)), Number(e.latlng.lng.toFixed(6))];
          if (modeRef.current === "pin") onLocation?.(p[0], p[1], "map");
          else setDraft((d) => [...d, p]);
        });
      }
      map.current = m;
      setReady(true);
      setTimeout(() => m.invalidateSize(), 50);
    })();
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Render point
  useEffect(() => {
    const m = map.current, lf = L.current;
    if (!m || !lf) return;
    layers.current.point?.remove();
    if (lat !== null && lon !== null) {
      layers.current.point = lf.circleMarker([lat, lon], { radius: 8, color: "#ffffff", weight: 2, fillColor: "#0e2a1f", fillOpacity: 1 })
        .bindTooltip("Selected location (point)").addTo(m);
      // Bring typed or GPS coordinates into view without fighting the user's own panning.
      if (!m.getBounds().contains([lat, lon])) m.setView([lat, lon], Math.max(m.getZoom(), 13));
    }
  }, [lat, lon, ready]);

  // Render saved polygon
  useEffect(() => {
    const m = map.current, lf = L.current;
    if (!m || !lf) return;
    layers.current.poly?.remove();
    if (boundary) {
      const ring = boundary.coordinates[0].map(([x, y]) => [y, x] as [number, number]);
      const poly = lf.polygon(ring, { color: "#3d8b4f", weight: 2, fillOpacity: 0.18 }).bindTooltip("User-drawn field boundary");
      poly.addTo(m);
      layers.current.poly = poly;
      if (readOnly) m.fitBounds(poly.getBounds(), { maxZoom: 17 });
    }
  }, [boundary, ready, readOnly]);

  // Render draft polygon
  useEffect(() => {
    const m = map.current, lf = L.current;
    if (!m || !lf) return;
    layers.current.draft?.remove();
    if (draft.length) {
      layers.current.draft = (draft.length > 2 ? lf.polygon(draft, { color: "#2f6fa8", dashArray: "4 4", weight: 2, fillOpacity: 0.1 })
        : lf.polyline(draft, { color: "#2f6fa8", dashArray: "4 4", weight: 2 })).addTo(m);
    }
  }, [draft, ready]);

  const useGps = () => {
    setMsg(null);
    if (!navigator.geolocation) {
      setMsg("This browser cannot share its location. Click the map or enter coordinates instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const la = Number(pos.coords.latitude.toFixed(6)), lo = Number(pos.coords.longitude.toFixed(6));
        onLocation?.(la, lo, "gps");
        map.current?.setView([la, lo], 15);
        setMsg(`Location shared (accuracy about ${Math.round(pos.coords.accuracy)} m).`);
      },
      (err) => setMsg(err.code === 1 ? "Location permission was declined. Click the map or enter coordinates instead." : "Could not get your location. Click the map or enter coordinates instead."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setResults([]);
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`,
        { headers: { Accept: "application/json" } });
      const data = await r.json();
      setResults(data);
      if (!data.length) setMsg("No places found. Try a nearby town or district.");
    } catch {
      setMsg("Place search is unavailable right now. Click the map or enter coordinates.");
    } finally {
      setSearching(false);
    }
  };

  const finish = () => {
    if (draft.length < 3) {
      setMsg("A boundary needs at least three points.");
      return;
    }
    const ring = [...draft.map(([a, b]) => [b, a]), [draft[0][1], draft[0][0]]];
    onBoundary?.({ type: "Polygon", coordinates: [ring] });
    setDraft([]);
    setMode("pin");
    setMsg("Boundary saved as a user-drawn polygon. Area is calculated from it.");
  };

  return (
    <div>
      {!readOnly && (
        <div className="mb-3 flex flex-col gap-3">
          <form onSubmit={search} className="flex gap-2">
            <input className="input" placeholder="Search for a village, town or district" value={query}
                   onChange={(e) => setQuery(e.target.value)} aria-label="Search location" />
            <button className="btn-secondary" disabled={searching}>{searching ? <Spinner /> : <Search className="h-4 w-4" />} Search</button>
          </form>
          {results.length > 0 && (
            <ul className="panel max-h-44 overflow-y-auto text-sm">
              {results.map((r) => (
                <li key={r.lat + r.lon}>
                  <button type="button" className="w-full px-3 py-2 text-left hover:bg-leaf-50"
                          onClick={() => {
                            const la = Number(Number(r.lat).toFixed(6)), lo = Number(Number(r.lon).toFixed(6));
                            map.current?.setView([la, lo], 15);
                            onLocation?.(la, lo, "map");
                            setResults([]);
                          }}>
                    {r.display_name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setMode("pin")} className={mode === "pin" ? "btn-primary" : "btn-secondary"}>
              <MapPin className="h-4 w-4" /> Place farm point
            </button>
            <button type="button" onClick={() => { setMode("draw"); setDraft([]); }} className={mode === "draw" ? "btn-primary" : "btn-secondary"}>
              <PenLine className="h-4 w-4" /> Draw field boundary
            </button>
            <button type="button" onClick={useGps} className="btn-secondary">
              <Crosshair className="h-4 w-4" /> Use my location
            </button>
            {boundary && (
              <button type="button" onClick={() => onBoundary?.(null)} className="btn-ghost text-risk">
                <Trash2 className="h-4 w-4" /> Remove boundary
              </button>
            )}
          </div>
          {mode === "draw" && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl bg-orbit-50 px-3 py-2 text-sm text-[#1f4a72]">
              Click the corners of your field on the map ({draft.length} points).
              <button type="button" className="btn-secondary py-1" onClick={() => setDraft((d) => d.slice(0, -1))} disabled={!draft.length}>
                <Undo2 className="h-4 w-4" /> Undo
              </button>
              <button type="button" className="btn-leaf py-1" onClick={finish} disabled={draft.length < 3}>Save boundary</button>
            </div>
          )}
          {msg && <p className="text-sm text-ink-soft" role="status">{msg}</p>}
        </div>
      )}
      <div ref={el} style={{ height }} className="relative z-0 w-full overflow-hidden rounded-panel border border-line bg-[#e7ece6]" />
    </div>
  );
}
