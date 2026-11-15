"use client";

import { useEffect, useMemo, useState } from "react";

/**
 * Illustration: a block of field parcels seen from orbit. Each parcel's colour is the crop it carries
 * in the selected season, so stepping through seasons makes a rotation visible. Not real imagery.
 */
const CROPS = {
  maize: { label: "Maize", color: "#c2b85a" },
  legume: { label: "Green gram", color: "#4f9150" },
  millet: { label: "Pearl millet", color: "#c9a267" },
  chickpea: { label: "Chickpea", color: "#8bb26a" },
  fallow: { label: "Fallow soil", color: "#9c7f5a" },
  rice: { label: "Rice", color: "#6fa86a" },
} as const;
type CropKey = keyof typeof CROPS;

const ROTATIONS: CropKey[][] = [
  ["maize", "chickpea", "legume", "millet"],
  ["legume", "fallow", "maize", "chickpea"],
  ["millet", "chickpea", "maize", "fallow"],
  ["rice", "legume", "rice", "chickpea"],
  ["maize", "fallow", "millet", "legume"],
];
const SEASONS = ["Wet season, year 1", "Dry season, year 1", "Wet season, year 2", "Dry season, year 2"];

function rng(seed: number) {
  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

export default function FieldMosaic() {
  const [season, setSeason] = useState(0);
  const parcels = useMemo(() => {
    const r = rng(42);
    const cols = 9;
    const rows = 6;
    const W = 720;
    const H = 480;
    const pts: [number, number][][] = [];
    for (let y = 0; y <= rows; y++) {
      const row: [number, number][] = [];
      for (let x = 0; x <= cols; x++) {
        const edge = x === 0 || y === 0 || x === cols || y === rows;
        const jx = edge ? 0 : (r() - 0.5) * 34;
        const jy = edge ? 0 : (r() - 0.5) * 28;
        row.push([(x / cols) * W + jx, (y / rows) * H + jy]);
      }
      pts.push(row);
    }
    const out: { d: string; rot: number; offset: number }[] = [];
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const a = pts[y][x], b = pts[y][x + 1], c = pts[y + 1][x + 1], d = pts[y + 1][x];
        const inset = 3;
        const cx = (a[0] + b[0] + c[0] + d[0]) / 4;
        const cy = (a[1] + b[1] + c[1] + d[1]) / 4;
        const shrink = (p: [number, number]) => {
          const dx = cx - p[0];
          const dy = cy - p[1];
          const len = Math.hypot(dx, dy) || 1;
          return `${(p[0] + (dx / len) * inset).toFixed(1)},${(p[1] + (dy / len) * inset).toFixed(1)}`;
        };
        out.push({ d: `M${shrink(a)}L${shrink(b)}L${shrink(c)}L${shrink(d)}Z`, rot: Math.floor(r() * ROTATIONS.length), offset: Math.floor(r() * 4) });
      }
    }
    return out;
  }, []);

  // One orchestrated moment: after load, advance once to the next season to show the rotation.
  useEffect(() => {
    const t = setTimeout(() => setSeason(1), 1400);
    return () => clearTimeout(t);
  }, []);

  const inUse = new Set<CropKey>();
  parcels.forEach((p) => inUse.add(ROTATIONS[p.rot][(season + p.offset) % 4]));

  return (
    <figure className="relative">
      <div className="overflow-hidden rounded-[14px] border border-white/10 bg-[#2a3a24] shadow-[0_30px_60px_-30px_rgba(0,0,0,0.6)]">
        <svg viewBox="0 0 720 480" className="block h-auto w-full" role="img"
             aria-label={`Illustration of field parcels in the ${SEASONS[season].toLowerCase()}`}>
          <rect width="720" height="480" fill="#2d3b26" />
          {parcels.map((p, i) => (
            <path key={i} d={p.d} fill={CROPS[ROTATIONS[p.rot][(season + p.offset) % 4]].color}
                  style={{ transition: "fill 900ms ease" }} />
          ))}
          <path d="M0 330 C 160 300, 260 360, 420 320 S 640 270, 720 290" stroke="#6fa3c9" strokeWidth="5" fill="none" opacity="0.85" />
          <g stroke="#ffffff" strokeOpacity="0.55" fill="none" strokeWidth="1.2">
            <path d="M24 24 h26 M24 24 v26" />
            <path d="M696 24 h-26 M696 24 v26" />
            <path d="M24 456 h26 M24 456 v-26" />
            <path d="M696 456 h-26 M696 456 v-26" />
          </g>
        </svg>
      </div>
      <figcaption className="mt-4 flex flex-col gap-3 text-sm text-white/75">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Season">
          {SEASONS.map((s, i) => (
            <button key={s} role="tab" aria-selected={season === i} onClick={() => setSeason(i)}
                    className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${season === i ? "bg-white text-forest" : "bg-white/10 text-white/80 hover:bg-white/20"}`}>
              {s}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {(Object.keys(CROPS) as CropKey[]).filter((k) => inUse.has(k)).map((k) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: CROPS[k].color }} />
              {CROPS[k].label}
            </span>
          ))}
          <span className="text-white/45">Illustration, not imagery of your farm</span>
        </div>
      </figcaption>
    </figure>
  );
}
