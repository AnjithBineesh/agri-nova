"use client";

import { useState } from "react";
import { Badge } from "./ui";

type Algo = { algorithm: string; cv_accuracy_mean: number; cv_accuracy_std: number; cv_macro_f1_mean: number };
type Importance = { feature: string; label: string; importance: number };
export type ModelInfo = {
  name: string;
  rows: number;
  classes: { key: string; name: string; rows: number }[];
  features: { key: string; label: string; unit: string; help: string; min: number; max: number; median: number }[];
  algorithm_comparison: Algo[];
  selected_algorithm: string;
  test_split: { rows: number; accuracy: number; macro_f1: number };
  per_class: { crop: string; name: string; precision: number; recall: number; f1: number; support: number }[];
  confusions: { actual: string; predicted: string; count: number }[];
  feature_importance: Importance[];
};
export type ModelCard = {
  trained_at: string;
  crop_model: ModelInfo;
  soil_model: ModelInfo;
  yield_dataset: { rows: number; deployed: boolean; best_cv_r2: number; verdict: string;
                   models: { algorithm: string; cv_r2_mean: number; cv_mae_t_ha: number }[] };
  weather_reference: { location: string; period: string; note: string;
                       examples: { season: string; climate: Record<string, number>; top_crops: { crop: string; probability: number }[] }[] };
  limitations: string[];
};

const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;

function Bars({ rows, max, highlight }: { rows: { label: string; value: number; text: string }[]; max: number; highlight?: string }) {
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,10rem)_1fr_3.5rem] items-center gap-3 text-sm">
          <span className={`truncate ${r.label === highlight ? "font-bold text-forest" : "text-ink-soft"}`}>{r.label}</span>
          <span className="h-2 rounded-full bg-paper">
            <span className={`block h-2 rounded-full ${r.label === highlight ? "bg-forest" : "bg-forest/35"}`}
                  style={{ width: `${Math.max(1.5, (r.value / max) * 100)}%` }} />
          </span>
          <span className="text-right tabular-nums text-ink-soft">{r.text}</span>
        </li>
      ))}
    </ul>
  );
}

/** Explains one trained model: how it was chosen, how accurate it is and what it pays attention to. */
export function ModelSummary({ m, title }: { m: ModelInfo; title: string }) {
  const [showAll, setShowAll] = useState(false);
  const algos = [...m.algorithm_comparison].sort((a, b) => b.cv_accuracy_mean - a.cv_accuracy_mean);
  const lo = Math.min(...algos.map((a) => a.cv_accuracy_mean)) - 0.05;
  const imp = m.feature_importance.filter((f) => f.importance > 0);
  const weakest = [...m.per_class].sort((a, b) => a.f1 - b.f1).slice(0, showAll ? m.per_class.length : 4);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold">{title}</h3>
        <span className="text-sm text-ink-soft">{m.rows.toLocaleString()} training records, {m.classes.length} crops</span>
      </div>
      <dl className="grid grid-cols-3 gap-3">
        {[
          ["Algorithm used", m.selected_algorithm],
          ["Accuracy on unseen records", pct(m.test_split.accuracy)],
          ["Balanced score (macro F1)", pct(m.test_split.macro_f1)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-2xl bg-paper p-4">
            <dt className="text-xs text-ink-faint">{k}</dt>
            <dd className="mt-1 text-lg font-bold leading-tight text-forest">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold">Six algorithms compared</h4>
          <p className="mb-3 text-xs text-ink-faint">Average accuracy over 5 cross-validation rounds. The best one is used.</p>
          <Bars highlight={m.selected_algorithm} max={1 - lo}
                rows={algos.map((a) => ({ label: a.algorithm, value: a.cv_accuracy_mean - lo, text: pct(a.cv_accuracy_mean) }))} />
        </div>
        <div>
          <h4 className="text-sm font-semibold">What the model pays attention to</h4>
          <p className="mb-3 text-xs text-ink-faint">How much accuracy drops when each value is scrambled.</p>
          <Bars max={Math.max(...imp.map((f) => f.importance))}
                rows={imp.map((f) => ({ label: f.label, value: f.importance, text: f.importance.toFixed(2) }))} />
        </div>
      </div>
      <div>
        <h4 className="text-sm font-semibold">Hardest crops to tell apart</h4>
        <p className="mb-2 text-xs text-ink-faint">Scores on the {m.test_split.rows} records held back from training.</p>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="table-base">
            <thead><tr><th>Crop</th><th>Precision</th><th>Recall</th><th>F1</th><th>Test records</th></tr></thead>
            <tbody>
              {weakest.map((c) => (
                <tr key={c.crop}><td className="font-semibold">{c.name}</td><td>{pct(c.precision, 0)}</td><td>{pct(c.recall, 0)}</td><td>{pct(c.f1, 0)}</td><td>{c.support}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink-faint">
          <button className="font-semibold text-forest underline-offset-2 hover:underline" onClick={() => setShowAll(!showAll)}>
            {showAll ? "Show fewer crops" : `Show all ${m.per_class.length} crops`}
          </button>
          {m.confusions.length > 0 && (
            <span>Mistakes on unseen records: {m.confusions.map((c) => `${c.actual} read as ${c.predicted} (${c.count})`).join("; ")}.</span>
          )}
        </div>
      </div>
    </div>
  );
}

export function ModelLimitations({ card }: { card: ModelCard }) {
  const y = card.yield_dataset;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <h4 className="text-sm font-semibold">Keep in mind</h4>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-soft">
          {card.limitations.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </div>
      <div className="rounded-2xl border border-line p-4">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-sm font-semibold">Yield prediction</h4>
          <Badge tone={y.deployed ? "green" : "orange"}>{y.deployed ? "In use" : "Not offered"}</Badge>
        </div>
        <p className="mt-2 text-sm text-ink-soft">
          We also trained yield models on {y.rows.toLocaleString()} crop-yield records.{" "}
          {y.deployed
            ? "The best model is used to estimate yield."
            : `None predicted yield more accurately than simply using the average yield (best R² ${y.best_cv_r2.toFixed(3)}), so Agri Nova doesn't offer yield predictions: it won't show numbers it can't back up.`}
        </p>
        <p className="mt-2 text-xs text-ink-faint">
          {y.models.map((m) => `${m.algorithm}: R² ${m.cv_r2_mean.toFixed(3)}`).join("; ")}
        </p>
      </div>
    </div>
  );
}
