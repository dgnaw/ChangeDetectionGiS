import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  LngLatBounds,
  Map as MlMap,
  NavigationControl,
  Popup,
  ScaleControl,
  type GeoJSONSource,
  type MapGeoJSONFeature,
  type MapMouseEvent,
  type StyleSpecification,
  type ExpressionSpecification
} from "maplibre-gl";
import { fetchAoi, fetchPopulationLayer, fetchWaterLayer } from "../api/client";

// ───────────────────────────── Cấu hình bản đồ ─────────────────────────────

export const MAP_CENTER: [number, number] = [105.855, 21.08]; // EPSG:4326 — CLAUDE.md
const MAP_ZOOM = 11.5;

export const CHANGE_COLORS = {
  stable: "#2563eb", // xanh dương
  gain: "#16a34a", // xanh lá
  loss: "#f97316" // đỏ cam
} as const;

/** Thang màu Choropleth mật độ dân số (người/km²). */
export const DENSITY_STOPS: Array<[number, string]> = [
  [0, "#fff7ec"],
  [2000, "#fdd49e"],
  [5000, "#fc8d59"],
  [10000, "#e34a33"],
  [15000, "#b30000"],
  [20000, "#7f0000"]
];

const EMPTY_FC: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    basemap: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors"
    }
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#eef2f7" } },
    { id: "basemap", type: "raster", source: "basemap" }
  ]
};

/** Tính bounding box từ FeatureCollection để fitBounds vừa khít AOI. */
function computeBounds(fc: GeoJSON.FeatureCollection): LngLatBounds | null {
  const bounds = new LngLatBounds();
  let hasCoords = false;
  const extendCoords = (coords: unknown): void => {
    if (!Array.isArray(coords) || coords.length === 0) return;
    if (typeof coords[0] === "number" && typeof coords[1] === "number") {
      bounds.extend([coords[0], coords[1]]);
      hasCoords = true;
    } else {
      coords.forEach(extendCoords);
    }
  };
  for (const f of fc.features) {
    if (f.geometry && "coordinates" in f.geometry) {
      extendCoords(f.geometry.coordinates);
    }
  }
  return hasCoords ? bounds : null;
}

const densityColor: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["to-number", ["get", "density_per_km2"], 0],
  ...DENSITY_STOPS.flat()
] as unknown as ExpressionSpecification;

const changeTypeColor: ExpressionSpecification = [
  "match",
  ["get", "change_type"],
  "stable",
  CHANGE_COLORS.stable,
  "gain",
  CHANGE_COLORS.gain,
  "loss",
  CHANGE_COLORS.loss,
  "#64748b"
];

const INTERACTIVE_LAYERS = ["water-fill", "pop-fill"];

// ───────────────────────────── Popup HTML ─────────────────────────────

const esc = (v: unknown) =>
  String(v ?? "—").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

const fmt = (v: unknown, digits = 2) =>
  typeof v === "number" ? v.toLocaleString("vi-VN", { maximumFractionDigits: digits }) : esc(v);

const CHANGE_LABEL: Record<string, string> = { stable: "Ổn định", gain: "Tăng (mới xuất hiện)", loss: "Mất (thu hẹp)" };

function row(label: string, value: string) {
  return `<tr><td style="color:#64748b;padding:1px 8px 1px 0">${label}</td><td style="font-weight:600">${value}</td></tr>`;
}

function waterPopup(p: Record<string, unknown>) {
  const ct = String(p.change_type);
  const color = CHANGE_COLORS[ct as keyof typeof CHANGE_COLORS] ?? "#64748b";
  return `
    <div style="font-size:12px;min-width:200px">
      <div style="font-weight:700;margin-bottom:4px;color:${color}">💧 Mặt nước ${esc(p.water_id)}</div>
      <table>
        ${row("Năm", esc(p.year))}
        ${row("Biến động", `<span style="color:${color}">${esc(CHANGE_LABEL[ct] ?? ct)}</span>`)}
        ${row("Diện tích", `${fmt(p.area_km2, 3)} km²`)}
        ${row("Chu vi", `${fmt(p.perimeter_km, 2)} km`)}
        ${row("MNDWI TB", fmt(p.mean_mndwi, 3))}
        ${row("Ngưỡng Otsu", fmt(p.otsu_threshold, 3))}
      </table>
    </div>`;
}

function popPopup(p: Record<string, unknown>) {
  // queryRenderedFeatures có thể trả boolean dưới dạng chuỗi
  const inBuffer = p.in_water_buffer_500m === true || p.in_water_buffer_500m === "true";
  return `
    <div style="font-size:12px;min-width:200px">
      <div style="font-weight:700;margin-bottom:4px;color:#b30000">🏘️ Ô dân cư ${esc(p.grid_id)}</div>
      <table>
        ${row("Năm", esc(p.year))}
        ${row("Dân số", `${fmt(p.pop_count, 0)} người`)}
        ${row("Mật độ", `${fmt(p.density_per_km2, 0)} người/km²`)}
        ${row("Vùng đệm 500m", inBuffer ? "✅ Có" : "❌ Không")}
        ${row("K/c tới mặt nước", `${fmt(p.dist_to_water_m, 0)} m`)}
      </table>
    </div>`;
}

function locationPopup(lng: number, lat: number) {
  return `<div style="font-size:12px"><b>📍 Tọa độ (EPSG:4326)</b><br/>Kinh độ: ${lng.toFixed(5)}<br/>Vĩ độ: ${lat.toFixed(5)}<br/><span style="color:#64748b">Không có đối tượng tại điểm này</span></div>`;
}

// ───────────────────────────── Đồng bộ camera giữa 2 bản đồ ─────────────────────────────

interface SyncGroup {
  maps: Set<MlMap>;
  syncing: boolean;
}

interface CameraState {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
}

// ───────────────────────────── 1 khung bản đồ ─────────────────────────────

const lineOpacity = (fillOpacity: number) => (fillOpacity === 0 ? 0 : Math.min(1, fillOpacity + 0.2));

interface MapViewProps {
  year: number;
  compareMode: boolean;
  showWater: boolean;
  showPopulation: boolean;
  onlyBuffer: boolean;
  waterOpacity: number;
  popOpacity: number;
  aoi: GeoJSON.FeatureCollection | null;
  label?: string;
  syncGroup: SyncGroup;
  cameraRef: React.MutableRefObject<CameraState>;
  hasFittedAoiRef: React.MutableRefObject<boolean>;
}

const MapView: React.FC<MapViewProps> = ({
  year,
  compareMode,
  showWater,
  showPopulation,
  onlyBuffer,
  waterOpacity,
  popOpacity,
  aoi,
  label,
  syncGroup,
  cameraRef,
  hasFittedAoiRef
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const opacityRef = useRef({ waterOpacity, popOpacity });
  opacityRef.current = { waterOpacity, popOpacity };
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [counts, setCounts] = useState<{ water: number; pop: number }>({ water: 0, pop: 0 });

  // Khởi tạo MapLibre
  useEffect(() => {
    if (!containerRef.current) return;
    const cam = cameraRef.current;
    const map = new MlMap({
      container: containerRef.current,
      style: BASE_STYLE,
      center: cam.center,
      zoom: cam.zoom,
      bearing: cam.bearing,
      pitch: cam.pitch,
      attributionControl: { compact: true }
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-right");

    map.on("load", () => {
      map.addSource("aoi", { type: "geojson", data: EMPTY_FC });
      map.addSource("population", { type: "geojson", data: EMPTY_FC });
      map.addSource("water", { type: "geojson", data: EMPTY_FC });

      // Lưới dân cư Choropleth (dưới cùng)
      const { waterOpacity: initWaterOp, popOpacity: initPopOp } = opacityRef.current;
      map.addLayer({
        id: "pop-fill",
        type: "fill",
        source: "population",
        paint: { "fill-color": densityColor, "fill-opacity": initPopOp }
      });
      map.addLayer({
        id: "pop-outline",
        type: "line",
        source: "population",
        paint: {
          "line-color": ["case", ["==", ["get", "in_water_buffer_500m"], true], "#7c3aed", "#ffffff"],
          "line-width": ["case", ["==", ["get", "in_water_buffer_500m"], true], 1.2, 0.5],
          "line-opacity": lineOpacity(initPopOp)
        }
      });

      // Mặt nước theo change_type
      map.addLayer({
        id: "water-fill",
        type: "fill",
        source: "water",
        paint: { "fill-color": changeTypeColor, "fill-opacity": initWaterOp }
      });
      map.addLayer({
        id: "water-line",
        type: "line",
        source: "water",
        paint: {
          "line-color": changeTypeColor,
          "line-width": 1.2,
          "line-opacity": lineOpacity(initWaterOp)
        }
      });

      // Viền đỏ AOI (trên cùng)
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi",
        paint: { "line-color": "#dc2626", "line-width": 2.5 }
      });

      setReady(true);
    });

    // Popup khi click
    const popup = new Popup({ closeButton: true, maxWidth: "300px" });
    popupRef.current = popup;
    const onClick = (e: MapMouseEvent) => {
      const layers = INTERACTIVE_LAYERS.filter((id) => map.getLayer(id));
      const features: MapGeoJSONFeature[] = layers.length ? map.queryRenderedFeatures(e.point, { layers }) : [];
      const water = features.find((f) => f.layer.id === "water-fill");
      const pop = features.find((f) => f.layer.id === "pop-fill");
      let html: string;
      if (water && pop) html = waterPopup(water.properties) + "<hr style='margin:6px 0'/>" + popPopup(pop.properties);
      else if (water) html = waterPopup(water.properties);
      else if (pop) html = popPopup(pop.properties);
      else html = locationPopup(e.lngLat.lng, e.lngLat.lat);
      popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
    };
    const onMouseMove = (e: MapMouseEvent) => {
      const layers = INTERACTIVE_LAYERS.filter((id) => map.getLayer(id));
      const hit = layers.length > 0 && map.queryRenderedFeatures(e.point, { layers }).length > 0;
      map.getCanvas().style.cursor = hit ? "pointer" : "";
    };
    map.on("click", onClick);
    map.on("mousemove", onMouseMove);

    // Đồng bộ camera (Compare Mode) + ghi nhớ vị trí khi chuyển chế độ
    const onMove = () => {
      const c = map.getCenter();
      cameraRef.current = {
        center: [c.lng, c.lat],
        zoom: map.getZoom(),
        bearing: map.getBearing(),
        pitch: map.getPitch()
      };
      if (syncGroup.syncing) return;
      syncGroup.syncing = true;
      syncGroup.maps.forEach((other) => {
        if (other !== map) other.jumpTo(cameraRef.current);
      });
      syncGroup.syncing = false;
    };
    map.on("move", onMove);
    syncGroup.maps.add(map);

    return () => {
      syncGroup.maps.delete(map);
      popup.remove();
      popupRef.current = null;
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, [syncGroup, cameraRef]);

  // Tự động đóng Popup mỗi khi year hoặc compareMode thay đổi
  useEffect(() => {
    popupRef.current?.remove();
  }, [year, compareMode]);

  // AOI + tự động fitBounds vừa khít ranh giới AOI khi tải xong lần đầu
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !aoi || !map) return;
    (map.getSource("aoi") as GeoJSONSource | undefined)?.setData(aoi);
    if (!hasFittedAoiRef.current) {
      const bounds = computeBounds(aoi);
      if (bounds) {
        hasFittedAoiRef.current = true;
        map.fitBounds(bounds, { padding: 40, duration: 600 });
      }
    }
  }, [ready, aoi, hasFittedAoiRef]);

  // Lớp mặt nước theo năm
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setLoading((n) => n + 1);
    fetchWaterLayer(year)
      .then((fc) => {
        if (cancelled) return;
        (mapRef.current?.getSource("water") as GeoJSONSource | undefined)?.setData(fc);
        setCounts((c) => ({ ...c, water: fc.features.length }));
        setError(null);
      })
      .catch((err) => !cancelled && setError(String(err?.message ?? err)))
      .finally(() => setLoading((n) => n - 1));
    return () => {
      cancelled = true;
    };
  }, [ready, year]);

  // Lớp dân cư theo năm + lọc vùng đệm 500m
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setLoading((n) => n + 1);
    fetchPopulationLayer(year, onlyBuffer)
      .then((fc) => {
        if (cancelled) return;
        (mapRef.current?.getSource("population") as GeoJSONSource | undefined)?.setData(fc);
        setCounts((c) => ({ ...c, pop: fc.features.length }));
        setError(null);
      })
      .catch((err) => !cancelled && setError(String(err?.message ?? err)))
      .finally(() => setLoading((n) => n - 1));
    return () => {
      cancelled = true;
    };
  }, [ready, year, onlyBuffer]);

  // Bật/tắt lớp
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const vis = (on: boolean) => (on ? "visible" : "none");
    ["water-fill", "water-line"].forEach((id) => map.setLayoutProperty(id, "visibility", vis(showWater)));
    ["pop-fill", "pop-outline"].forEach((id) => map.setLayoutProperty(id, "visibility", vis(showPopulation)));
  }, [ready, showWater, showPopulation]);

  // Cập nhật độ mờ (Opacity) lớp Mặt nước & Dân cư
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setPaintProperty("water-fill", "fill-opacity", waterOpacity);
    map.setPaintProperty("water-line", "line-opacity", lineOpacity(waterOpacity));
    map.setPaintProperty("pop-fill", "fill-opacity", popOpacity);
    map.setPaintProperty("pop-outline", "line-opacity", lineOpacity(popOpacity));
  }, [ready, waterOpacity, popOpacity]);

  return (
    <div style={{ position: "relative", flex: 1, minWidth: 0, height: "100%" }}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      <div style={badgeStyle}>
        <strong style={{ fontSize: 15 }}>{label ?? `Năm ${year}`}</strong>
        <div style={{ fontSize: 11, color: "#475569" }}>
          {counts.water} đa giác nước · {counts.pop} ô dân cư{onlyBuffer ? " (≤500m)" : ""}
        </div>
        {loading > 0 && <div style={{ fontSize: 11, color: "#2563eb" }}>Đang tải dữ liệu…</div>}
        {error && <div style={{ fontSize: 11, color: "#dc2626" }}>Lỗi: {error}</div>}
      </div>
    </div>
  );
};

const badgeStyle: React.CSSProperties = {
  position: "absolute",
  top: 10,
  left: 10,
  background: "rgba(255,255,255,0.92)",
  padding: "6px 10px",
  borderRadius: 6,
  boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
  pointerEvents: "none"
};

// ───────────────────────────── Chú giải ─────────────────────────────

const Legend: React.FC<{ showWater: boolean; showPopulation: boolean }> = ({ showWater, showPopulation }) => (
  <div
    style={{
      position: "absolute",
      bottom: 30,
      left: 10,
      background: "rgba(255,255,255,0.94)",
      padding: "8px 12px",
      borderRadius: 6,
      boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
      fontSize: 12,
      zIndex: 2,
      display: "flex",
      flexDirection: "column",
      gap: 4
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 16, height: 0, borderTop: "3px solid #dc2626" }} /> Ranh giới AOI
    </div>
    {showWater && (
      <>
        <strong style={{ marginTop: 4 }}>Mặt nước (change_type)</strong>
        {(
          [
            ["stable", "Ổn định"],
            ["gain", "Tăng"],
            ["loss", "Mất"]
          ] as const
        ).map(([k, t]) => (
          <div key={k} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 14, height: 14, background: CHANGE_COLORS[k], opacity: 0.8, borderRadius: 2 }} />
            {t} ({k})
          </div>
        ))}
      </>
    )}
    {showPopulation && (
      <>
        <strong style={{ marginTop: 4 }}>Mật độ dân số (người/km²)</strong>
        <div style={{ display: "flex" }}>
          {DENSITY_STOPS.map(([v, c]) => (
            <div key={v} style={{ textAlign: "center", width: 36 }}>
              <div style={{ height: 10, background: c, opacity: 0.8 }} />
              <div style={{ fontSize: 10 }}>{v >= 1000 ? `${v / 1000}k` : v}</div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 14, border: "2px solid #7c3aed" }} /> Ô trong vùng đệm 500m
        </div>
      </>
    )}
  </div>
);

// ───────────────────────────── MapCanvas ─────────────────────────────

interface MapCanvasProps {
  year: number;
  showWater: boolean;
  showPopulation: boolean;
  onlyBuffer: boolean;
  waterOpacity?: number;
  popOpacity?: number;
  compareMode: boolean;
  /** Cặp năm so sánh [trái, phải], mặc định [2016, 2024]. */
  compareYears?: [number, number];
}

export const MapCanvas: React.FC<MapCanvasProps> = ({
  year,
  showWater,
  showPopulation,
  onlyBuffer,
  waterOpacity = 0.7,
  popOpacity = 0.65,
  compareMode,
  compareYears = [2016, 2024]
}) => {
  const [aoi, setAoi] = useState<GeoJSON.FeatureCollection | null>(null);
  const syncGroupRef = useRef<SyncGroup>({ maps: new Set(), syncing: false });
  const cameraRef = useRef<CameraState>({ center: MAP_CENTER, zoom: MAP_ZOOM, bearing: 0, pitch: 0 });
  const hasFittedAoiRef = useRef<boolean>(false);

  useEffect(() => {
    fetchAoi()
      .then(setAoi)
      .catch((err) => console.error("Không tải được AOI", err));
  }, []);

  const common = {
    compareMode,
    showWater,
    showPopulation,
    onlyBuffer,
    waterOpacity,
    popOpacity,
    aoi,
    syncGroup: syncGroupRef.current,
    cameraRef,
    hasFittedAoiRef
  };

  const resetView = useCallback(() => {
    const bounds = aoi ? computeBounds(aoi) : null;
    syncGroupRef.current.maps.forEach((m) => {
      if (bounds) {
        m.fitBounds(bounds, { padding: 40, bearing: 0, pitch: 0 });
      } else {
        m.flyTo({ center: MAP_CENTER, zoom: MAP_ZOOM, bearing: 0, pitch: 0 });
      }
    });
  }, [aoi]);

  return (
    <div style={{ position: "relative", flex: 1, display: "flex", minWidth: 0 }}>
      {compareMode ? (
        <>
          <MapView key="cmp-left" {...common} year={compareYears[0]} label={`◀ ${compareYears[0]}`} />
          <div style={{ width: 3, background: "#0f172a", zIndex: 1 }} />
          <MapView key="cmp-right" {...common} year={compareYears[1]} label={`${compareYears[1]} ▶`} />
        </>
      ) : (
        <MapView key="single" {...common} year={year} />
      )}
      <Legend showWater={showWater} showPopulation={showPopulation} />
      <button
        onClick={resetView}
        title="Về tâm AOI [105.855, 21.08]"
        style={{
          position: "absolute",
          top: 120,
          right: 10,
          zIndex: 2,
          padding: "4px 8px",
          fontSize: 12,
          borderRadius: 4,
          border: "1px solid #cbd5e1",
          background: "#fff",
          cursor: "pointer"
        }}
      >
        ⌖ AOI
      </button>
    </div>
  );
};
