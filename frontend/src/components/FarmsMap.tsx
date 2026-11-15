"use client";

import { useEffect, useRef } from "react";

export default function FarmsMap({ farms }: { farms: { farm_id: number; farm_name: string; latitude: number; longitude: number; owner: string }[] }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let map: any;
    (async () => {
      const L = await import("leaflet");
      if (!el.current) return;
      map = L.map(el.current);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
      const pts = farms.map((f) => {
        L.circleMarker([f.latitude, f.longitude], { radius: 7, color: "#fff", weight: 2, fillColor: "#0f3b2c", fillOpacity: 1 })
          .bindTooltip(`${f.farm_name} (${f.owner})`).addTo(map);
        return [f.latitude, f.longitude] as [number, number];
      });
      if (pts.length === 1) map.setView(pts[0], 10);
      else map.fitBounds(L.latLngBounds(pts), { padding: [30, 30] });
    })();
    return () => map?.remove();
  }, [farms]);
  return <div ref={el} className="relative z-0 h-[340px] w-full overflow-hidden rounded-panel border border-line bg-[#e7ece6]" aria-label="Map of member farms" />;
}
