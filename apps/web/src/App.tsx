import React, { useEffect, useState } from "react";
import { MapCanvas } from "./components/MapCanvas";
import { TimeSlider } from "./components/TimeSlider";
import { CompareToggle } from "./components/CompareToggle";
import { LayerControl } from "./components/LayerControl";
import { StatsChart } from "./components/StatsChart";
import {
  VALID_YEARS,
  fetchHealth,
  fetchTimeseries,
  getDataSource,
  subscribeDataSource,
  type DataSource,
  type TimeseriesPoint,
  type TimeseriesResponse
} from "./api/client";

const YEARS: number[] = [...VALID_YEARS];

const SOURCE_BADGE: Record<DataSource, { text: string; bg: string; title: string }> = {
  unknown: { text: "Đang kết nối…", bg: "#475569", title: "Đang kiểm tra Backend" },
  api: { text: "● API FastAPI", bg: "#16a34a", title: "Dữ liệu từ http://localhost:8000" },
  mock: {
    text: "● Mock contracts/",
    bg: "#d97706",
    title: "Backend chưa chạy — đang đọc dữ liệu mẫu từ contracts/mock và contracts/aoi.geojson"
  }
};

export default function App() {
  const [year, setYear] = useState<number>(2020);
  const [showWater, setShowWater] = useState<boolean>(true);
  const [showPopulation, setShowPopulation] = useState<boolean>(true);
  const [onlyBuffer, setOnlyBuffer] = useState<boolean>(false);
  const [waterOpacity, setWaterOpacity] = useState<number>(0.7);
  const [popOpacity, setPopOpacity] = useState<number>(0.65);
  const [compareMode, setCompareMode] = useState<boolean>(false);
  const [compareYears, setCompareYears] = useState<[number, number]>([2016, 2024]);
  const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null);
  const [source, setSource] = useState<DataSource>(getDataSource());

  useEffect(() => subscribeDataSource(setSource), []);

  useEffect(() => {
    fetchHealth().catch(() => undefined);
    fetchTimeseries()
      .then(setTimeseries)
      .catch((err) => console.error("Không tải được chuỗi thời gian", err));
  }, []);

  const series: TimeseriesPoint[] = timeseries?.series ?? [];
  const current = series.find((s) => s.year === year);
  const badge = SOURCE_BADGE[source];

  return (
    <div style={{ display: "flex", height: "100vh", flexDirection: "column" }}>
      <header
        style={{
          padding: "8px 20px",
          background: "#0f172a",
          color: "#f8fafc",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div>
            <strong>GIS Change Detection</strong> — Hành lang Sông Hồng · Hồ Tây · Đông Anh (2016–2024)
          </div>
          <span
            title={badge.title}
            style={{ background: badge.bg, padding: "2px 8px", borderRadius: 10, fontSize: 11, whiteSpace: "nowrap" }}
          >
            {badge.text}
          </span>
        </div>
        <TimeSlider years={YEARS} selectedYear={year} onChange={setYear} disabled={compareMode} />
      </header>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <aside
          style={{
            width: 380,
            padding: 16,
            borderRight: "1px solid #cbd5e1",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            overflowY: "auto",
            background: "#f8fafc"
          }}
        >
          <LayerControl
            showWater={showWater}
            showPopulation={showPopulation}
            onlyBuffer={onlyBuffer}
            waterOpacity={waterOpacity}
            popOpacity={popOpacity}
            onToggleWater={setShowWater}
            onTogglePopulation={setShowPopulation}
            onToggleOnlyBuffer={setOnlyBuffer}
            onChangeWaterOpacity={setWaterOpacity}
            onChangePopOpacity={setPopOpacity}
          />
          <CompareToggle
            enabled={compareMode}
            onToggle={setCompareMode}
            years={YEARS}
            compareYears={compareYears}
            onChangeYears={setCompareYears}
          />

          {current && !compareMode && (
            <div style={{ fontSize: 13, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              <Kpi label="Mặt nước" value={`${current.water_area_km2} km²`} sub={`${current.water_ratio_pct}% AOI`} />
              <Kpi
                label="Dân số vùng đệm"
                value={current.pop_in_buffer_500m.toLocaleString("vi-VN")}
                sub={`${current.pop_buffer_ratio_pct}% tổng dân`}
              />
              <Kpi label="Nước tăng / mất" value={`+${current.water_gain_km2} / −${current.water_loss_km2}`} sub="km²" />
              <Kpi
                label="Otsu · IoU JRC"
                value={`${current.otsu_threshold}`}
                sub={current.jrc_iou_score !== null ? `IoU ${current.jrc_iou_score}` : "IoU: n/a"}
              />
            </div>
          )}

          <StatsChart series={series} selectedYear={year} highlightYears={compareMode ? compareYears : []} />
          <small style={{ color: "#64748b" }}>
            CRS hiển thị: EPSG:4326 · Tính toán: EPSG:32648 · Click vào bản đồ để xem thuộc tính.
          </small>
        </aside>

        <MapCanvas
          year={year}
          showWater={showWater}
          showPopulation={showPopulation}
          onlyBuffer={onlyBuffer}
          waterOpacity={waterOpacity}
          popOpacity={popOpacity}
          compareMode={compareMode}
          compareYears={compareYears}
        />
      </div>
    </div>
  );
}

const Kpi: React.FC<{ label: string; value: string; sub: string }> = ({ label, value, sub }) => (
  <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 6, padding: "6px 8px" }}>
    <div style={{ color: "#64748b", fontSize: 11 }}>{label}</div>
    <div style={{ fontWeight: 700 }}>{value}</div>
    <div style={{ color: "#94a3b8", fontSize: 11 }}>{sub}</div>
  </div>
);
