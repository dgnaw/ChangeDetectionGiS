import React from "react";

interface LayerControlProps {
  showWater: boolean;
  showPopulation: boolean;
  onlyBuffer: boolean;
  onToggleWater: (v: boolean) => void;
  onTogglePopulation: (v: boolean) => void;
  onToggleOnlyBuffer: (v: boolean) => void;
}

const rowStyle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, cursor: "pointer" };

export const LayerControl: React.FC<LayerControlProps> = ({
  showWater,
  showPopulation,
  onlyBuffer,
  onToggleWater,
  onTogglePopulation,
  onToggleOnlyBuffer
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <strong>Điều khiển lớp bản đồ</strong>
      <label style={rowStyle}>
        <input type="checkbox" checked={showWater} onChange={(e) => onToggleWater(e.target.checked)} />
        <span style={{ width: 12, height: 12, background: "#2563eb", borderRadius: 2 }} />
        Lớp Mặt nước (MNDWI – Otsu)
      </label>
      <label style={rowStyle}>
        <input type="checkbox" checked={showPopulation} onChange={(e) => onTogglePopulation(e.target.checked)} />
        <span style={{ width: 12, height: 12, background: "linear-gradient(90deg,#fdd49e,#b30000)", borderRadius: 2 }} />
        Lớp Dân cư (GHSL 250m)
      </label>
      <label
        style={{ ...rowStyle, paddingLeft: 20, color: showPopulation ? undefined : "#94a3b8" }}
        title="Gọi API với only_buffer=true — chỉ các ô có in_water_buffer_500m = true"
      >
        <input
          type="checkbox"
          disabled={!showPopulation}
          checked={onlyBuffer}
          onChange={(e) => onToggleOnlyBuffer(e.target.checked)}
        />
        Chỉ hiện dân cư trong vùng đệm 500m
      </label>
    </div>
  );
};
