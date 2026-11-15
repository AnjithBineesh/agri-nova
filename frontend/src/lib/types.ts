export type Role = "farmer" | "researcher" | "organisation" | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  organisation_id: number | null;
  organisation_name: string | null;
  preferences: Record<string, any> | null;
  created_at: string;
}

export interface Season {
  name: string;
  start_month: number;
  end_month: number;
  label?: string;
}

export interface CropHistoryItem {
  crop_slug: string;
  season: string;
  year: number;
}

export interface Farm {
  id: number;
  user_id: number;
  farm_name: string;
  country: string;
  state: string | null;
  region: string | null;
  latitude: number;
  longitude: number;
  location_source: "gps" | "map" | "manual";
  boundary: GeoJSONPolygon | null;
  boundary_status: "none" | "user_drawn" | "verified";
  area_ha: number | null;
  area_source: string | null;
  soil_type: string | null;
  current_crop: string | null;
  previous_crops: string[] | null;
  irrigation_type: "none" | "supplemental" | "full";
  irrigation_capacity_mm: number | null;
  growing_seasons: Season[] | null;
  farming_method: string | null;
  residue_management: "removed" | "partial" | "retained";
  crop_history: CropHistoryItem[];
  owner_name: string | null;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
}

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface DatasetStatus {
  key: string;
  name: string;
  provider: string;
  products: string;
  spatial_resolution: string;
  temporal_resolution: string;
  coverage: string;
  data_type: string;
  access: string;
  requires_credentials: boolean;
  integration: string;
  documentation_url: string;
  notes: string;
  status: string;
  message: string | null;
  display_name: string;
  display_resolution: string;
  display_message: string;
  last_attempt: string | null;
  last_success: string | null;
  coverage_start: string | null;
  coverage_end: string | null;
  record_count: number;
  is_demo: boolean;
}

export interface MonthlyRow {
  month: number;
  t_mean: number | null;
  t_max: number | null;
  t_min: number | null;
  precip_mm: number | null;
  rh: number | null;
  solar: number | null;
  wind: number | null;
  et0_mm: number | null;
  et0_method: string | null;
}

export interface Profile {
  farm_id: number;
  is_demo: boolean;
  has_climate: boolean;
  monthly: MonthlyRow[];
  annual: { year: number; t_mean: number | null; precip_mm: number | null }[];
  annual_precip_mean: number | null;
  annual_precip_cv: number | null;
  temp_trend_c_per_decade: number | null;
  precip_trend_mm_per_decade: number | null;
  soil_moisture: any;
  vegetation: any;
  terrain: any;
  sources: Record<string, any>;
  gaps: string[];
}

export interface EarthOverview {
  farm_id: number;
  datasets: DatasetStatus[];
  profile: Profile;
  demo_enabled: boolean;
  earthdata_configured: boolean;
  spatial_note: string;
}

export interface Crop {
  id: number;
  slug: string;
  crop_name: string;
  scientific_name: string;
  crop_family: string;
  category: string;
  duration: { typical_days: number; ecocrop_min_days: number; ecocrop_max_days: number };
  planting_season: string;
  harvest_period: string;
  climate_requirements: any;
  water_requirement: any;
  soil_preferences: any;
  nutrient_requirements: any;
  nitrogen_fixation: boolean;
  fixation: any;
  root_characteristics: any;
  residue: any;
  rotation: any;
  pest_disease_considerations: string[];
  geographic_suitability: string;
  sources: string[];
}

export interface SuitabilityFactor {
  name: string;
  score: number | null;
  value: any;
  explanation: string;
  available: boolean;
  critical: string | null;
  weight: number;
}

export interface SuitabilityResult {
  crop: string;
  crop_name: string;
  family: string;
  category: string;
  season: string;
  season_label: string;
  score: number | null;
  class: "suitable" | "moderately_suitable" | "unsuitable" | "insufficient_data";
  critical_constraints: string[];
  factors: SuitabilityFactor[];
  reasons: string[];
  limitations: string[];
  data_completeness: number;
  water: any;
  is_demo_basis: boolean;
}

export interface RotationSlot {
  crop: string;
  span: number;
}

export interface Strategy {
  id?: number;
  key: string;
  name: string;
  rank?: number;
  rotation: RotationSlot[];
  crop_sequence: { crop: string; span: number; crop_name: string; season: string }[];
  mean_suitability: number | null;
  harvested_seasons: number;
  cycle_seasons: number;
  objectives: Record<string, number | null>;
  priority_score: number | null;
  rules: { findings: { rule: string; severity: string; message: string; position?: string }[]; rotation_health_index: number; families: string[] };
  simulation_summary: any;
  stress_summary: any;
  explanation: any;
}

export interface SimSeason {
  index: number;
  year: number;
  season: string;
  season_label?: string;
  crop: string;
  crop_name: string;
  family?: string;
  span?: number;
  continuation: boolean;
  water?: any;
  suitability_score?: number | null;
  critical_constraints?: string[];
  n_balance_kg_ha?: number;
  n_balance_cum?: number;
  p2o5_balance_cum?: number;
  k2o_balance_cum?: number;
  carbon_input_t_ha?: number;
  soc_t_ha?: { central: number; low: number; high: number };
  family_count?: number;
  shannon_diversity?: number;
  climate_vulnerability?: number;
  climate_vulnerability_class?: string;
  erosion_index?: number;
  erosion_class?: string;
  gross_margin?: number;
  yield_t_ha?: number;
  yield_source?: string;
}

export interface Simulation {
  seasons: SimSeason[];
  summary: any;
  assumptions: Record<string, string>;
  scenario: any;
  rotation?: RotationSlot[];
}
