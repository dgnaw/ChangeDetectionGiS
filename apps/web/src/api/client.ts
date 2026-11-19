const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface TimeseriesPoint {
  year: number;
  water_area_km2: number;
  water_ratio_pct: number;
  water_gain_km2: number;
  water_loss_km2: number;
  otsu_threshold: number;
  cloud_cover_pct: number;
  total_pop: number;
  pop_in_buffer_500m: number;
  pop_buffer_ratio_pct: number;
  jrc_iou_score: number | null;
}

export interface TimeseriesResponse {
  aoi_name: string;
  aoi_area_km2: number;
  crs_storage: string;
  crs_metric: string;
  years: number[];
  series: TimeseriesPoint[];
}

export async function fetchAoi(): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(`${API_BASE}/api/v1/aoi`);
  if (!res.ok) throw new Error("Failed to fetch AOI");
  return res.json();
}

export async function fetchWaterLayer(year: number): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(`${API_BASE}/api/v1/layers/water?year=${year}`);
  if (!res.ok) throw new Error(`Failed to fetch water layer for ${year}`);
  return res.json();
}

export async function fetchPopulationLayer(
  year: number,
  onlyBuffer = false
): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(
    `${API_BASE}/api/v1/layers/population?year=${year}&only_buffer=${onlyBuffer}`
  );
  if (!res.ok) throw new Error(`Failed to fetch population layer for ${year}`);
  return res.json();
}

export async function fetchTimeseries(): Promise<TimeseriesResponse> {
  const res = await fetch(`${API_BASE}/api/v1/analytics/timeseries`);
  if (!res.ok) throw new Error("Failed to fetch timeseries");
  return res.json();
}
