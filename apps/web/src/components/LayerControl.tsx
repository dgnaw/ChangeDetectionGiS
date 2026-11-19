import React from "react";

interface LayerControlProps {
  showWater: boolean;
  showPopulation: boolean;
  onlyBuffer: boolean;
  onToggleWater: (v: boolean) => void;
  onTogglePopulation: (v: boolean) => void;
  onToggleOnlyBuffer: (v: boolean) => void;
}

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
      <label>
        <input type="checkbox" checked={showWater} onChange={(e) => onToggleWater(e.target.checked)} /> Lớp Mặt nước (MNDWI)
      </label>
      <label>
        <input type="checkbox" checked={showPopulation} onChange={(e) => onTogglePopulation(e.target.checked)} /> Lớp Dân cư (GHSL 250m)
      </label>
      <label style={{ paddingLeft: 16 }}>
        <input
          type="checkbox"
          disabled={!showPopulation}
          checked={onlyBuffer}
          onChange={(e) => onToggleOnlyBuffer(e.target.checked)}
        />{" "}
        Chỉ hiện vùng đệm 500m
      </label>
    </div>
  );
};
