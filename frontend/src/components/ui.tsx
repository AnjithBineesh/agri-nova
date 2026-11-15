"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { AlertTriangle, ArrowRight, CircleHelp, FlaskConical, Loader2, Sprout } from "lucide-react";
import { DATA_TYPE_LABEL } from "@/lib/format";

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden />;
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm text-ink-soft" role="status">
      <Spinner /> {label}…
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-risk/30 bg-risk-100/60 p-4 text-sm text-risk" role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        <p>{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="mt-2 font-semibold underline underline-offset-2">
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "demo"; children: React.ReactNode }) {
  const cls =
    tone === "warn"
      ? "border-warn/30 bg-warn-100/60 text-[#7a4208]"
      : tone === "demo"
        ? "border-warn/50 bg-warn-100 text-[#7a4208]"
        : "border-orbit/25 bg-orbit-50 text-[#1f4a72]";
  return <div className={`rounded-2xl border px-4 py-3 text-sm ${cls}`}>{children}</div>;
}

export function DemoBanner({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <Notice tone="demo">
      <span className="inline-flex items-start gap-2">
        <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          <strong>Demonstration data.</strong> Some weather and field values on this page are synthetic, generated
          for testing. They are not real measurements and must not be used for real decisions.
        </span>
      </span>
    </Notice>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="panel flex flex-col items-start gap-3 p-8">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-lime text-forest"><Sprout className="h-5 w-5" /></span>
      <h2 className="section-title">{title}</h2>
      <p className="max-w-prose text-sm text-ink-soft">{body}</p>
      {action}
    </div>
  );
}

export function NoFarm() {
  return (
    <EmptyState
      title="Add your first farm"
      body="Agri Nova needs a farm location to look up its weather and predict which crops suit it. It takes about two minutes."
      action={
        <Link href="/app/farms/new" className="btn-primary">
          Add a farm
        </Link>
      }
    />
  );
}

export function NeedsClimate({ farmId }: { farmId?: number }) {
  return (
    <EmptyState
      title="Weather data needed first"
      body="Crop prediction, suitability, rotation planning and simulations use your farm's weather record. Retrieve it on the Field conditions page."
      action={
        <Link href={farmId ? `/app/earth?farm=${farmId}` : "/app/earth"} className="btn-primary">
          Open Field conditions
        </Link>
      }
    />
  );
}

const TONES: Record<string, string> = {
  green: "bg-leaf-100 text-leaf-600",
  blue: "bg-orbit-100 text-orbit",
  orange: "bg-warn-100 text-warn",
  red: "bg-risk-100 text-risk",
  grey: "bg-paper text-ink-soft",
  lime: "bg-lime text-forest",
  forest: "bg-forest text-white",
};

export function Badge({ tone = "grey", children }: { tone?: keyof typeof TONES | string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone] ?? TONES.grey}`}>
      {children}
    </span>
  );
}

const TYPE_TONE: Record<string, string> = {
  satellite_observation: "blue",
  derived_satellite_indicator: "blue",
  weather_climate_estimate: "green",
  farmer_provided: "forest",
  model_estimate: "grey",
  demonstration: "orange",
};

export function DataTypeTag({ type }: { type: string }) {
  return <Badge tone={TYPE_TONE[type] ?? "grey"}>{DATA_TYPE_LABEL[type] ?? type}</Badge>;
}

export function InfoTip({ text, label = "What does this mean?" }: { text: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="ml-1 text-ink-faint hover:text-orbit"
      >
        <CircleHelp className="h-3.5 w-3.5" />
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute left-1/2 top-6 z-50 w-64 -translate-x-1/2 rounded-xl bg-forest-900 px-3 py-2 text-xs font-normal leading-relaxed text-white shadow-lg"
        >
          {text}
        </span>
      )}
    </span>
  );
}

export const TERMS = {
  ndvi: "NDVI (Normalised Difference Vegetation Index) compares near-infrared and red light reflected by plants. Values near 0 mean bare soil; 0.6+ means dense, healthy green vegetation.",
  et0: "Reference evapotranspiration (ET0) is how much water a well-watered grass surface would lose to the air. Crop water use is ET0 multiplied by a crop coefficient.",
  et: "Evapotranspiration is water leaving the field through soil evaporation and plant transpiration.",
  soilMoisture: "Surface soil moisture describes roughly the top 5 cm of soil averaged over a 9 km area. It shows wet and dry periods, not the water-holding capacity of your field.",
  rootzone: "Root-zone soil moisture (0–100 cm) is a model estimate for the surrounding area.",
  lst: "Land surface temperature is the temperature of the ground or crop canopy surface. It can be much hotter than air temperature at midday.",
  soc: "Soil organic carbon is the carbon held in soil organic matter. More of it usually means better structure, water retention and nutrient supply.",
  nbalance: "Nitrogen removed in harvests minus nitrogen supplied by legumes and their residues, before any fertiliser or manure. Negative values show how much N must be supplied.",
  suitability: "A 0–100 score combining temperature, water, season length, soil pH, texture, nutrients and salinity. Any critical constraint makes a crop unsuitable whatever the score.",
  completeness: "The share of the scoring weight backed by real data. Missing soil tests or climate records lower completeness instead of being guessed.",
  vulnerability: "How close the crop is to its temperature and water limits under the chosen scenario: 0 is comfortable, 1 is at or beyond a limit.",
  erosion: "A qualitative indicator combining ground cover, slope and seasonal rainfall. It is not a soil-loss measurement.",
};

export function PageHeader({ title, accent, intro, actions, tag }: {
  title: string; accent?: string; intro?: string; actions?: React.ReactNode; tag?: string;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {tag && <span className="tag mb-3">{tag}</span>}
        <h1 className="page-title">{title}{accent && <> <span className="accent">{accent}</span></>}</h1>
        {intro && <p className="mt-2 max-w-2xl text-[15px] text-ink-soft">{intro}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

/** Guides the user to the logical next page of the farmer journey. */
export function NextStep({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link href={href} className="group mt-10 flex items-center justify-between gap-4 rounded-panel bg-forest p-6 text-white transition-colors hover:bg-forest-700">
      <span>
        <span className="text-xs font-semibold text-lime">Next step</span>
        <span className="mt-1 block text-lg font-bold text-white">{title}</span>
        <span className="mt-0.5 block text-sm text-white/70">{body}</span>
      </span>
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-lime text-forest transition-transform group-hover:translate-x-1">
        <ArrowRight className="h-5 w-5" />
      </span>
    </Link>
  );
}

export function Stat({
  label,
  value,
  unit,
  note,
  tip,
  accent = "ink",
}: {
  label: string;
  value: string;
  unit?: string;
  note?: React.ReactNode;
  tip?: string;
  accent?: "ink" | "orbit" | "leaf" | "warn" | "risk";
}) {
  const color = { ink: "text-ink", orbit: "text-orbit", leaf: "text-leaf-600", warn: "text-warn", risk: "text-risk" }[accent];
  return (
    <div className="panel panel-pad">
      <div className="flex items-center text-sm text-ink-soft">
        {label}
        {tip && <InfoTip text={tip} />}
      </div>
      <div className={`mt-2 font-display text-[26px] font-bold leading-none ${color}`}>
        {value}
        {unit && <span className="ml-1 text-sm font-medium text-ink-soft">{unit}</span>}
      </div>
      {note && <div className="mt-2 text-xs text-ink-faint">{note}</div>}
    </div>
  );
}

export function ScoreBar({ value, tone }: { value: number | null; tone?: string }) {
  const v = value ?? 0;
  const c = tone ?? (v >= 70 ? "bg-leaf" : v >= 45 ? "bg-warn" : "bg-risk");
  return (
    <div className="h-1.5 w-full rounded-full bg-paper" aria-hidden>
      <div className={`h-1.5 rounded-full ${c}`} style={{ width: `${Math.max(2, Math.min(100, v))}%` }} />
    </div>
  );
}
