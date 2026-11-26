import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  LngLatBounds,
  Map as MlMap,
  NavigationControl,
  Popup,
  ScaleControl,
  type ExpressionSpecification,
  type FilterSpecification,
  type GeoJSONSource,
  type MapGeoJSONFeature,
  type MapMouseEvent,
  type StyleSpecification
} from "maplibre-gl";
import {
  VALID_YEARS,
  fetchAoi,
  fetchPopulationLayer,
  fetchWaterLayer,
  getCachedPopulationLayer,
  getCachedWaterLayer
} from "../api/client";
import {
  computeCrossfadeOpacities,
  formatTimelineLabel,
  getTimelineBracket,
  lerp
} from "../utils/timeline";

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

const BUFFER_FILTER: FilterSpecification = ["==", ["get", "in_water_buffer_500m"], true];
const ZERO_TRANSITION = { duration: 0, delay: 0 };

const ALL_INTERACTIVE_LAYERS = [
  ...VALID_YEARS.map((y) => `water-fill-${y}`),
  ...VALID_YEARS.map((y) => `pop-fill-${y}`)
];

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

interface YearCounts {
  water: number;
  popTotal: number;
  popBuffer: number;
}

interface MapViewProps {
  timelineValue: number;
  playing: boolean;
  preloadReady: boolean;
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
  timelineValue,
  playing,
  preloadReady,
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
  const popupOpenedAtRef = useRef<number | null>(null);
  const timelineRef = useRef<number>(timelineValue);
  timelineRef.current = timelineValue;

  const loadedYearsRef = useRef<Set<number>>(new Set());
  const yearCountsRef = useRef<Record<number, YearCounts>>({});
  const prevVisRef = useRef<Map<string, "visible" | "none">>(new Map());

  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [, setDataTick] = useState(0);

  // Khởi tạo MapLibre với sẵn 5 bộ source + layer (2016..2024) để cross-fade GPU 60 FPS
  useEffect(() => {
    if (!containerRef.current) return;
    loadedYearsRef.current.clear();
    yearCountsRef.current = {};
    prevVisRef.current.clear();

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

      for (const y of VALID_YEARS) {
        map.addSource(`pop-${y}`, { type: "geojson", data: EMPTY_FC });
        map.addSource(`water-${y}`, { type: "geojson", data: EMPTY_FC });
      }

      // 1) Lớp lưới dân cư 5 năm (dưới cùng)
      for (const y of VALID_YEARS) {
        map.addLayer({
          id: `pop-fill-${y}`,
          type: "fill",
          source: `pop-${y}`,
          layout: { visibility: "none" },
          paint: {
            "fill-color": densityColor,
            "fill-opacity": 0
          }
        });
        map.setPaintProperty(`pop-fill-${y}`, "fill-opacity-transition", ZERO_TRANSITION);
        map.addLayer({
          id: `pop-outline-${y}`,
          type: "line",
          source: `pop-${y}`,
          layout: { visibility: "none" },
          paint: {
            "line-color": ["case", ["==", ["get", "in_water_buffer_500m"], true], "#7c3aed", "#ffffff"],
            "line-width": ["case", ["==", ["get", "in_water_buffer_500m"], true], 1.2, 0.5],
            "line-opacity": 0
          }
        });
        map.setPaintProperty(`pop-outline-${y}`, "line-opacity-transition", ZERO_TRANSITION);
      }

      // 2) Lớp mặt nước 5 năm (ở giữa)
      for (const y of VALID_YEARS) {
        map.addLayer({
          id: `water-fill-${y}`,
          type: "fill",
          source: `water-${y}`,
          layout: { visibility: "none" },
          paint: {
            "fill-color": changeTypeColor,
            "fill-opacity": 0
          }
        });
        map.setPaintProperty(`water-fill-${y}`, "fill-opacity-transition", ZERO_TRANSITION);
        map.addLayer({
          id: `water-line-${y}`,
          type: "line",
          source: `water-${y}`,
          layout: { visibility: "none" },
          paint: {
            "line-color": changeTypeColor,
            "line-width": 1.2,
            "line-opacity": 0
          }
        });
        map.setPaintProperty(`water-line-${y}`, "line-opacity-transition", ZERO_TRANSITION);
      }

      // 3) Viền đỏ AOI (trên cùng)
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi",
        paint: { "line-color": "#dc2626", "line-width": 2.5 }
      });

      setReady(true);
    });

    // Popup khi click (ưu tiên lớp của mốc năm nổi bật hiện tại)
    const popup = new Popup({ closeButton: true, maxWidth: "300px" });
    popupRef.current = popup;
    const onClick = (e: MapMouseEvent) => {
      const layers = ALL_INTERACTIVE_LAYERS.filter((id) => map.getLayer(id));
      const features: MapGeoJSONFeature[] = layers.length ? map.queryRenderedFeatures(e.point, { layers }) : [];
      const bracket = getTimelineBracket(timelineRef.current, VALID_YEARS);
      const dominantYear = bracket.rawAlpha >= 0.5 ? bracket.yearB : bracket.yearA;

      const water =
        features.find((f) => f.layer.id === `water-fill-${dominantYear}`) ??
        features.find((f) => f.layer.id.startsWith("water-fill-"));
      const pop =
        features.find((f) => f.layer.id === `pop-fill-${dominantYear}`) ??
        features.find((f) => f.layer.id.startsWith("pop-fill-"));

      let html: string;
      if (water && pop) html = waterPopup(water.properties) + "<hr style='margin:6px 0'/>" + popPopup(pop.properties);
      else if (water) html = waterPopup(water.properties);
      else if (pop) html = popPopup(pop.properties);
      else html = locationPopup(e.lngLat.lng, e.lngLat.lat);

      popupOpenedAtRef.current = timelineRef.current;
      popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
    };
    const onMouseMove = (e: MapMouseEvent) => {
      const layers = ALL_INTERACTIVE_LAYERS.filter((id) => map.getLayer(id));
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

  // Đóng popup khi bật Compare Mode, bấm Play, hoặc tua đáng kể khỏi vị trí mở popup
  useEffect(() => {
    popupRef.current?.remove();
    popupOpenedAtRef.current = null;
  }, [compareMode]);

  useEffect(() => {
    if (playing) {
      popupRef.current?.remove();
      popupOpenedAtRef.current = null;
    }
  }, [playing]);

  useEffect(() => {
    if (popupOpenedAtRef.current !== null && Math.abs(timelineValue - popupOpenedAtRef.current) > 0.05) {
      popupRef.current?.remove();
      popupOpenedAtRef.current = null;
    }
  }, [timelineValue]);

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

  // Nạp dữ liệu GeoJSON 5 mốc năm vào MapLibre source 1 lần duy nhất từ cache
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    let cancelled = false;

    for (const y of VALID_YEARS) {
      if (loadedYearsRef.current.has(y)) continue;

      const cachedWater = getCachedWaterLayer(y);
      const cachedPop = getCachedPopulationLayer(y);

      if (cachedWater && cachedPop) {
        (map.getSource(`water-${y}`) as GeoJSONSource | undefined)?.setData(cachedWater);
        (map.getSource(`pop-${y}`) as GeoJSONSource | undefined)?.setData(cachedPop);
        loadedYearsRef.current.add(y);
        yearCountsRef.current[y] = {
          water: cachedWater.features.length,
          popTotal: cachedPop.features.length,
          popBuffer: cachedPop.features.filter((f) => f.properties.in_water_buffer_500m === true).length
        };
        setDataTick((t) => t + 1);
        continue;
      }

      setLoading((n) => n + 1);
      Promise.all([fetchWaterLayer(y), fetchPopulationLayer(y, false)])
        .then(([waterFc, popFc]) => {
          if (cancelled || !mapRef.current) return;
          (mapRef.current.getSource(`water-${y}`) as GeoJSONSource | undefined)?.setData(waterFc);
          (mapRef.current.getSource(`pop-${y}`) as GeoJSONSource | undefined)?.setData(popFc);
          loadedYearsRef.current.add(y);
          yearCountsRef.current[y] = {
            water: waterFc.features.length,
            popTotal: popFc.features.length,
            popBuffer: popFc.features.filter((f) => f.properties.in_water_buffer_500m === true).length
          };
          setError(null);
          setDataTick((t) => t + 1);
        })
        .catch((err) => {
          if (!cancelled) setError(String(err?.message ?? err));
        })
        .finally(() => setLoading((n) => n - 1));
    }

    return () => {
      cancelled = true;
    };
  }, [ready, preloadReady]);

  // Lọc vùng đệm 500m bằng GPU filter trên MapLibre (không setData lại)
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const filter = onlyBuffer ? BUFFER_FILTER : null;
    for (const y of VALID_YEARS) {
      if (map.getLayer(`pop-fill-${y}`)) map.setFilter(`pop-fill-${y}`, filter);
      if (map.getLayer(`pop-outline-${y}`)) map.setFilter(`pop-outline-${y}`, filter);
    }
  }, [ready, onlyBuffer]);

  // Cross-fade 2 bộ layer gối đầu (Year A -> Year B) ở 60 FPS bằng setPaintProperty
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;

    const bracket = getTimelineBracket(timelineValue, VALID_YEARS);
    const baseWaterLine = lineOpacity(waterOpacity);
    const basePopLine = lineOpacity(popOpacity);

    const waterOps =
      bracket.yearA === bracket.yearB
        ? { opA: waterOpacity, opB: 0 }
        : computeCrossfadeOpacities(waterOpacity, bracket.easedAlpha);
    const waterLineOps =
      bracket.yearA === bracket.yearB
        ? { opA: baseWaterLine, opB: 0 }
        : computeCrossfadeOpacities(baseWaterLine, bracket.easedAlpha);
    const popOps =
      bracket.yearA === bracket.yearB
        ? { opA: popOpacity, opB: 0 }
        : computeCrossfadeOpacities(popOpacity, bracket.easedAlpha);
    const popLineOps =
      bracket.yearA === bracket.yearB
        ? { opA: basePopLine, opB: 0 }
        : computeCrossfadeOpacities(basePopLine, bracket.easedAlpha);

    const setVisIfChanged = (layerId: string, visible: boolean) => {
      const next: "visible" | "none" = visible ? "visible" : "none";
      if (prevVisRef.current.get(layerId) !== next && map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", next);
        prevVisRef.current.set(layerId, next);
      }
    };

    for (const y of VALID_YEARS) {
      const isA = y === bracket.yearA;
      const isB = y === bracket.yearB && bracket.yearB !== bracket.yearA;
      const isActiveYear = isA || isB;

      const waterVisible = showWater && isActiveYear;
      const popVisible = showPopulation && isActiveYear;

      setVisIfChanged(`water-fill-${y}`, waterVisible);
      setVisIfChanged(`water-line-${y}`, waterVisible);
      setVisIfChanged(`pop-fill-${y}`, popVisible);
      setVisIfChanged(`pop-outline-${y}`, popVisible);

      if (waterVisible) {
        const fillOp = isA ? waterOps.opA : waterOps.opB;
        const lnOp = isA ? waterLineOps.opA : waterLineOps.opB;
        map.setPaintProperty(`water-fill-${y}`, "fill-opacity", fillOp);
        map.setPaintProperty(`water-line-${y}`, "line-opacity", lnOp);
      }

      if (popVisible) {
        const fillOp = isA ? popOps.opA : popOps.opB;
        const lnOp = isA ? popLineOps.opA : popLineOps.opB;
        map.setPaintProperty(`pop-fill-${y}`, "fill-opacity", fillOp);
        map.setPaintProperty(`pop-outline-${y}`, "line-opacity", lnOp);
      }
    }
  }, [ready, timelineValue, showWater, showPopulation, waterOpacity, popOpacity]);

  const bracket = getTimelineBracket(timelineValue, VALID_YEARS);
  const countsA = yearCountsRef.current[bracket.yearA];
  const countsB = yearCountsRef.current[bracket.yearB];
  const waterCount =
    countsA && countsB
      ? Math.round(lerp(countsA.water, countsB.water, bracket.rawAlpha))
      : (countsA?.water ?? countsB?.water ?? 0);
  const popCountA = countsA ? (onlyBuffer ? countsA.popBuffer : countsA.popTotal) : 0;
  const popCountB = countsB ? (onlyBuffer ? countsB.popBuffer : countsB.popTotal) : 0;
  const popCount =
    countsA && countsB ? Math.round(lerp(popCountA, popCountB, bracket.rawAlpha)) : (popCountA || popCountB);

  return (
    <div style={{ position: "relative", flex: 1, minWidth: 0, height: "100%" }}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      <div style={badgeStyle}>
        <strong style={{ fontSize: 15, fontVariantNumeric: "tabular-nums" }}>
          {label ?? formatTimelineLabel(timelineValue)}
        </strong>
        <div style={{ fontSize: 11, color: "#475569", fontVariantNumeric: "tabular-nums" }}>
          {waterCount} đa giác nước · {popCount} ô dân cư{onlyBuffer ? " (≤500m)" : ""}
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
  timelineValue: number;
  playing: boolean;
  preloadReady: boolean;
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
  timelineValue,
  playing,
  preloadReady,
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
    playing,
    preloadReady,
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
          <MapView key="cmp-left" {...common} timelineValue={compareYears[0]} label={`◀ ${compareYears[0]}`} />
          <div style={{ width: 3, background: "#0f172a", zIndex: 1 }} />
          <MapView key="cmp-right" {...common} timelineValue={compareYears[1]} label={`${compareYears[1]} ▶`} />
        </>
      ) : (
        <MapView key="single" {...common} timelineValue={timelineValue} />
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
