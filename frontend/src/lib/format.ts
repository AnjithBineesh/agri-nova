export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmt(v: number | null | undefined, digits = 0, unit = ""): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })}${unit ? " " + unit : ""}`;
}

export function signed(v: number | null | undefined, digits = 0, unit = ""): string {
  if (v === null || v === undefined) return "–";
  const s = v > 0 ? "+" : "";
  return `${s}${fmt(v, digits)}${unit ? " " + unit : ""}`;
}

export const DATA_TYPE_LABEL: Record<string, string> = {
  satellite_observation: "Remote observation",
  derived_satellite_indicator: "Derived field indicator",
  weather_climate_estimate: "Weather or climate estimate",
  farmer_provided: "Farmer-provided value",
  model_estimate: "Model-generated estimate",
  demonstration: "Demonstration data",
};

export const STATUS_LABEL: Record<string, string> = {
  complete: "Retrieved",
  pending: "Submitted, waiting",
  processing: "Processing",
  failed: "Retrieval failed",
  not_configured: "Not set up yet",
  not_integrated: "Planned",
  not_requested: "Not requested yet",
  no_data: "No usable observations",
  demonstration: "Demonstration data",
};

export const CLASS_LABEL: Record<string, string> = {
  suitable: "Suitable",
  moderately_suitable: "Moderately suitable",
  unsuitable: "Unsuitable",
  insufficient_data: "Not enough data",
};

export function seasonText(s: { name: string; start_month: number; end_month: number }) {
  return `${s.name} (${MONTHS[s.start_month - 1]}–${MONTHS[s.end_month - 1]})`;
}

export const TEXTURES = [
  "sand", "loamy sand", "sandy loam", "loam", "silt loam", "silt", "sandy clay loam",
  "clay loam", "silty clay loam", "sandy clay", "silty clay", "clay",
];
