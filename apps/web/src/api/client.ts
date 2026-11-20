/**
 * API client cho WebGIS — 5 endpoint chuẩn theo CLAUDE.md §4:
 *   GET /api/v1/health
 *   GET /api/v1/aoi
 *   GET /api/v1/layers/water?year=YYYY
 *   GET /api/v1/layers/population?year=YYYY&only_buffer=bool
 *   GET /api/v1/analytics/timeseries
 *
 * Chế độ FALLBACK: nếu Backend FastAPI (mặc định http://localhost:8000) chưa chạy
 * hoặc trả lỗi, client tự động đọc dữ liệu mẫu từ `contracts/mock/` và
 * `contracts/aoi.geojson` (chỉ ĐỌC, không sửa contracts/).
 * Có thể ép dùng mock bằng biến môi trường `VITE_USE_MOCK=true`.
 */

const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const FORCE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const REQUEST_TIMEOUT_MS = 2500;
/** Sau khi Backend lỗi, chờ bao lâu mới thử gọi lại API thật (ms). */
const RETRY_BACKEND_AFTER_MS = 15000;

export const VALID_YEARS = [2016, 2018, 2020, 2022, 2024] as const;

// ───────────────────────────── Kiểu dữ liệu (khớp contracts/schemas) ─────────────────────────────

export type ChangeType = "stable" | "gain" | "loss";

export interface WaterProperties {
  water_id: string;
  year: number;
  area_km2: number;
  perimeter_km: number;
  mean_mndwi: number;
  otsu_threshold: number;
  change_type: ChangeType;
}

export interface PopulationProperties {
  grid_id: string;
  year: number;
  pop_count: number;
  density_per_km2: number;
  in_water_buffer_500m: boolean;
  dist_to_water_m: number;
}

export type WaterLayer = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, WaterProperties>;
export type PopulationLayer = GeoJSON.FeatureCollection<GeoJSON.Polygon, PopulationProperties>;

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

export interface HealthResponse {
  status: string;
  service: string;
}

// ───────────────────────────── Theo dõi nguồn dữ liệu (API / Mock) ─────────────────────────────

export type DataSource = "unknown" | "api" | "mock";

let currentSource: DataSource = FORCE_MOCK ? "mock" : "unknown";
let backendDownSince: number | null = null;
const listeners = new Set<(s: DataSource) => void>();

function setSource(s: DataSource) {
  if (s === currentSource) return;
  currentSource = s;
  listeners.forEach((fn) => fn(s));
}

export function getDataSource(): DataSource {
  return currentSource;
}

/** Đăng ký lắng nghe thay đổi nguồn dữ liệu. Trả về hàm hủy đăng ký. */
export function subscribeDataSource(fn: (s: DataSource) => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

// ───────────────────────────── Đọc dữ liệu mẫu từ contracts/ ─────────────────────────────

// Vite nạp lười (lazy) nội dung file dạng chuỗi thô, chỉ tải khi thật sự cần fallback.
const mockFiles = import.meta.glob<string>("../../../../contracts/mock/*.{geojson,json}", {
  query: "?raw",
  import: "default"
});
const aoiFiles = import.meta.glob<string>("../../../../contracts/aoi.geojson", {
  query: "?raw",
  import: "default"
});

async function loadContractFile<T>(files: Record<string, () => Promise<string>>, fileName: string): Promise<T> {
  const key = Object.keys(files).find((k) => k.endsWith(`/${fileName}`));
  if (!key) throw new Error(`Không tìm thấy file mẫu contracts: ${fileName}`);
  const raw = await files[key]();
  return JSON.parse(raw) as T;
}

function assertValidYear(year: number) {
  if (!(VALID_YEARS as readonly number[]).includes(year)) {
    throw new Error(`Year ${year} not available. Choose from ${VALID_YEARS.join(", ")}.`);
  }
}

const mock = {
  health: async (): Promise<HealthResponse> => ({ status: "mock", service: "contracts/mock (offline fallback)" }),
  aoi: () => loadContractFile<GeoJSON.FeatureCollection>(aoiFiles, "aoi.geojson"),
  water: (year: number) => {
    assertValidYear(year);
    return loadContractFile<WaterLayer>(mockFiles, `water_${year}.geojson`);
  },
  population: async (year: number, onlyBuffer: boolean) => {
    assertValidYear(year);
    const data = await loadContractFile<PopulationLayer>(mockFiles, `pop_${year}.geojson`);
    if (!onlyBuffer) return data;
    // Lọc giống hệt services/api/app/routers/layers.py
    return { ...data, features: data.features.filter((f) => f.properties.in_water_buffer_500m === true) };
  },
  timeseries: () => loadContractFile<TimeseriesResponse>(mockFiles, "timeseries_summary.json")
};

// ───────────────────────────── Lõi gọi API có fallback ─────────────────────────────

async function fetchJson<T>(path: string): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status} — ${path}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

async function withFallback<T>(path: string, fallback: () => Promise<T>): Promise<T> {
  const backendRecentlyDown =
    backendDownSince !== null && Date.now() - backendDownSince < RETRY_BACKEND_AFTER_MS;

  if (!FORCE_MOCK && !backendRecentlyDown) {
    try {
      const data = await fetchJson<T>(path);
      backendDownSince = null;
      setSource("api");
      return data;
    } catch (err) {
      backendDownSince = Date.now();
      console.warn(`[api] ${API_BASE}${path} không khả dụng → dùng dữ liệu mẫu contracts/mock.`, err);
    }
  }
  const data = await fallback();
  setSource("mock");
  return data;
}

// ───────────────────────────── 5 hàm gọi API chuẩn ─────────────────────────────

export function fetchHealth(): Promise<HealthResponse> {
  return withFallback("/api/v1/health", mock.health);
}

export function fetchAoi(): Promise<GeoJSON.FeatureCollection> {
  return withFallback("/api/v1/aoi", mock.aoi);
}

export function fetchWaterLayer(year: number): Promise<WaterLayer> {
  return withFallback(`/api/v1/layers/water?year=${year}`, () => mock.water(year));
}

export function fetchPopulationLayer(year: number, onlyBuffer = false): Promise<PopulationLayer> {
  return withFallback(`/api/v1/layers/population?year=${year}&only_buffer=${onlyBuffer}`, () =>
    mock.population(year, onlyBuffer)
  );
}

export function fetchTimeseries(): Promise<TimeseriesResponse> {
  return withFallback("/api/v1/analytics/timeseries", mock.timeseries);
}
