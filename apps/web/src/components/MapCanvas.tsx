import React from "react";

interface MapCanvasProps {
  year: number;
  showWater: boolean;
  showPopulation: boolean;
  onlyBuffer: boolean;
  compareMode: boolean;
}

export const MapCanvas: React.FC<MapCanvasProps> = ({
  year,
  showWater,
  showPopulation,
  onlyBuffer,
  compareMode
}) => {
  return (
    <div
      style={{
        flex: 1,
        background: "#e2e8f0",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        padding: 24
      }}
    >
      <h2 style={{ margin: 0 }}>MapLibre GL JS Canvas (PA3: Sông Hồng – Hồ Tây – Đông Anh)</h2>
      <p style={{ color: "#334155" }}>
        Năm hiện tại: <strong>{year}</strong> | Mặt nước: {showWater ? "Bật" : "Tắt"} | Dân cư:{" "}
        {showPopulation ? (onlyBuffer ? "Chỉ vùng đệm 500m" : "Toàn AOI") : "Tắt"} | Compare:{" "}
        {compareMode ? "Bật" : "Tắt"}
      </p>
      <small style={{ color: "#64748b" }}>
        TODO (Người B — Tuần 4): Tích hợp MapLibre GL JS với center [105.855, 21.08] và gọi API từ client.ts.
      </small>
    </div>
  );
};
