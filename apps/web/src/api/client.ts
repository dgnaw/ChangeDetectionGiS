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
const REQUEST_TIMEOUT_MS = 8000;
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
export type PopulationLayer = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, PopulationProperties>;

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
  database?: string;
  postgis_version?: string | null;
  records?: Record<string, number> | null;
  detail?: string | null;
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

// ───────────────────────────── Bộ nhớ đệm & Tải trước (Preload 5 năm) ─────────────────────────────

export interface PreloadProgress {
  loaded: number;
  total: number;
  ready: boolean;
  error: string | null;
}

const waterCache = new Map<number, WaterLayer>();
const waterInFlight = new Map<number, Promise<WaterLayer>>();
const popFullCache = new Map<number, PopulationLayer>();
const popFullInFlight = new Map<number, Promise<PopulationLayer>>();

let aoiCache: GeoJSON.FeatureCollection | null = null;
let aoiInFlight: Promise<GeoJSON.FeatureCollection> | null = null;
let timeseriesCache: TimeseriesResponse | null = null;
let timeseriesInFlight: Promise<TimeseriesResponse> | null = null;

const preloadListeners = new Set<(p: PreloadProgress) => void>();
let preloadPromise: Promise<void> | null = null;

export function getCachedWaterLayer(year: number): WaterLayer | undefined {
  return waterCache.get(year);
}

export function getCachedPopulationLayer(year: number): PopulationLayer | undefined {
  return popFullCache.get(year);
}

export function isAllLayersCached(): boolean {
  return VALID_YEARS.every((y) => waterCache.has(y) && popFullCache.has(y));
}

function getCurrentPreloadProgress(error: string | null = null): PreloadProgress {
  const total = VALID_YEARS.length * 2;
  let loaded = 0;
  for (const y of VALID_YEARS) {
    if (waterCache.has(y)) loaded += 1;
    if (popFullCache.has(y)) loaded += 1;
  }
  return { loaded, total, ready: loaded === total, error };
}

function notifyPreload(progress: PreloadProgress) {
  preloadListeners.forEach((fn) => fn(progress));
}

// ───────────────────────────── 5 hàm gọi API chuẩn ─────────────────────────────

export function fetchHealth(): Promise<HealthResponse> {
  return withFallback("/api/v1/health", mock.health);
}

export function fetchAoi(): Promise<GeoJSON.FeatureCollection> {
  if (aoiCache) return Promise.resolve(aoiCache);
  if (aoiInFlight) return aoiInFlight;
  aoiInFlight = withFallback("/api/v1/aoi", mock.aoi)
    .then((data) => {
      aoiCache = data;
      return data;
    })
    .finally(() => {
      aoiInFlight = null;
    });
  return aoiInFlight;
}

export function fetchWaterLayer(year: number): Promise<WaterLayer> {
  const cached = waterCache.get(year);
  if (cached) return Promise.resolve(cached);

  const inFlight = waterInFlight.get(year);
  if (inFlight) return inFlight;

  const req = withFallback(`/api/v1/layers/water?year=${year}`, () => mock.water(year))
    .then((data) => {
      waterCache.set(year, data);
      return data;
    })
    .finally(() => {
      waterInFlight.delete(year);
    });
  waterInFlight.set(year, req);
  return req;
}

function fetchFullPopulationLayer(year: number): Promise<PopulationLayer> {
  const cached = popFullCache.get(year);
  if (cached) return Promise.resolve(cached);

  const inFlight = popFullInFlight.get(year);
  if (inFlight) return inFlight;

  const req = withFallback(`/api/v1/layers/population?year=${year}&only_buffer=false`, () =>
    mock.population(year, false)
  )
    .then((data) => {
      popFullCache.set(year, data);
      return data;
    })
    .finally(() => {
      popFullInFlight.delete(year);
    });
  popFullInFlight.set(year, req);
  return req;
}

export async function fetchPopulationLayer(year: number, onlyBuffer = false): Promise<PopulationLayer> {
  const full = await fetchFullPopulationLayer(year);
  if (!onlyBuffer) return full;
  return {
    ...full,
    features: full.features.filter((f) => f.properties.in_water_buffer_500m === true)
  };
}

export function fetchTimeseries(): Promise<TimeseriesResponse> {
  if (timeseriesCache) return Promise.resolve(timeseriesCache);
  if (timeseriesInFlight) return timeseriesInFlight;
  timeseriesInFlight = withFallback("/api/v1/analytics/timeseries", mock.timeseries)
    .then((data) => {
      timeseriesCache = data;
      return data;
    })
    .finally(() => {
      timeseriesInFlight = null;
    });
  return timeseriesInFlight;
}

/**
 * Tải trước & cache toàn bộ GeoJSON của 5 mốc năm (water + population)
 * để phát timelapse 60 FPS không bị khựng hoặc gọi lại API.
 */
export async function preloadAllLayers(onProgress?: (p: PreloadProgress) => void): Promise<void> {
  if (onProgress) {
    preloadListeners.add(onProgress);
    onProgress(getCurrentPreloadProgress());
  }

  if (isAllLayersCached()) {
    notifyPreload(getCurrentPreloadProgress());
    return;
  }

  if (preloadPromise) {
    return preloadPromise;
  }

  preloadPromise = (async () => {
    try {
      // Thăm dò health trước một lần nếu chưa rõ nguồn dữ liệu,
      // giúp fallback sang mock ngay lập tức mà không chờ 10 timeout song song.
      if (currentSource === "unknown") {
        await fetchHealth().catch(() => undefined);
      }

      notifyPreload(getCurrentPreloadProgress());

      const tasks: Array<Promise<unknown>> = [];
      for (const y of VALID_YEARS) {
        tasks.push(
          fetchWaterLayer(y).then((res) => {
            notifyPreload(getCurrentPreloadProgress());
            return res;
          })
        );
        tasks.push(
          fetchFullPopulationLayer(y).then((res) => {
            notifyPreload(getCurrentPreloadProgress());
            return res;
          })
        );
      }

      await Promise.all(tasks);
      notifyPreload(getCurrentPreloadProgress());
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notifyPreload(getCurrentPreloadProgress(msg));
      throw err;
    } finally {
      preloadPromise = null;
    }
  })();

  return preloadPromise;
}
