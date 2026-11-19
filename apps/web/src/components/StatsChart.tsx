import React from "react";
import type { TimeseriesPoint } from "../api/client";

interface StatsChartProps {
  series: TimeseriesPoint[];
}

export const StatsChart: React.FC<StatsChartProps> = ({ series }) => {
  return (
    <div style={{ padding: 12, border: "1px solid #cbd5e1", borderRadius: 8 }}>
      <strong>Biểu đồ Nước vs Dân cư vùng đệm 500m (Recharts)</strong>
      <p style={{ fontSize: 13, color: "#475569" }}>
        Số mốc năm đã nạp: {series.length} (TODO — Người B vẽ Dual-Axis LineChart bằng Recharts ở Tuần 5).
      </p>
    </div>
  );
};
