import React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { TimeseriesPoint } from "../api/client";

interface StatsChartProps {
  series: TimeseriesPoint[];
  /** Năm đang chọn trên TimeSlider (vẽ đường tham chiếu). */
  selectedYear?: number;
  /** Các năm đang so sánh (Compare Mode). */
  highlightYears?: number[];
}

const WATER_COLOR = "#2563eb";
const POP_COLOR = "#dc2626";

const fmtPop = (v: number) => (v >= 1000 ? `${(v / 1000).toLocaleString("vi-VN", { maximumFractionDigits: 0 })}k` : `${v}`);

function pctChange(a?: number, b?: number) {
  if (a === undefined || b === undefined || a === 0) return null;
  return ((b - a) / a) * 100;
}

export const StatsChart: React.FC<StatsChartProps> = ({ series, selectedYear, highlightYears = [] }) => {
  const data = [...series].sort((a, b) => a.year - b.year);
  const first = data[0];
  const last = data[data.length - 1];
  const waterDelta = pctChange(first?.water_area_km2, last?.water_area_km2);
  const popDelta = pctChange(first?.pop_in_buffer_500m, last?.pop_in_buffer_500m);
  const refYears = highlightYears.length ? highlightYears : selectedYear !== undefined ? [selectedYear] : [];

  return (
    <div style={{ padding: 12, border: "1px solid #cbd5e1", borderRadius: 8, background: "#fff" }}>
      <strong>Mặt nước vs Dân cư vùng đệm 500m</strong>
      {data.length === 0 ? (
        <p style={{ fontSize: 13, color: "#475569" }}>Đang tải chuỗi thời gian…</p>
      ) : (
        <>
          <div style={{ width: "100%", height: 260, marginTop: 8 }}>
            <ResponsiveContainer>
              <LineChart data={data} margin={{ top: 8, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis
                  yAxisId="water"
                  orientation="left"
                  stroke={WATER_COLOR}
                  tick={{ fontSize: 11 }}
                  domain={[(min: number) => Math.floor(min - 0.5), (max: number) => Math.ceil(max + 0.5)]}
                  label={{ value: "km²", angle: -90, position: "insideLeft", offset: 18, fontSize: 11, fill: WATER_COLOR }}
                />
                <YAxis
                  yAxisId="pop"
                  orientation="right"
                  stroke={POP_COLOR}
                  tick={{ fontSize: 11 }}
                  tickFormatter={fmtPop}
                  domain={["auto", "auto"]}
                  label={{ value: "người", angle: 90, position: "insideRight", offset: 10, fontSize: 11, fill: POP_COLOR }}
                />
                <Tooltip
                  labelFormatter={(y) => `Năm ${y}`}
                  formatter={(value: number, name: string) =>
                    name.startsWith("Diện tích")
                      ? [`${value.toLocaleString("vi-VN")} km²`, name]
                      : [`${value.toLocaleString("vi-VN")} người`, name]
                  }
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {refYears.map((y) => (
                  <ReferenceLine key={y} x={y} yAxisId="water" stroke="#f59e0b" strokeDasharray="4 2" />
                ))}
                <Line
                  yAxisId="water"
                  type="monotone"
                  dataKey="water_area_km2"
                  name="Diện tích mặt nước (km²)"
                  stroke={WATER_COLOR}
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
                <Line
                  yAxisId="pop"
                  type="monotone"
                  dataKey="pop_in_buffer_500m"
                  name="Dân số vùng đệm 500m"
                  stroke={POP_COLOR}
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {first && last && waterDelta !== null && popDelta !== null && (
            <div style={{ fontSize: 12, color: "#334155", marginTop: 6, lineHeight: 1.6 }}>
              {first.year} → {last.year}: mặt nước{" "}
              <b style={{ color: WATER_COLOR }}>
                {waterDelta >= 0 ? "+" : ""}
                {waterDelta.toFixed(1)}%
              </b>{" "}
              ({first.water_area_km2} → {last.water_area_km2} km²), dân số vùng đệm{" "}
              <b style={{ color: POP_COLOR }}>
                {popDelta >= 0 ? "+" : ""}
                {popDelta.toFixed(1)}%
              </b>
              .
            </div>
          )}
        </>
      )}
    </div>
  );
};
