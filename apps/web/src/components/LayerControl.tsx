import React from "react";

interface LayerControlProps {
  showWater: boolean;
  showPopulation: boolean;
  onlyBuffer: boolean;
  waterOpacity: number;
  popOpacity: number;
  onToggleWater: (v: boolean) => void;
  onTogglePopulation: (v: boolean) => void;
  onToggleOnlyBuffer: (v: boolean) => void;
  onChangeWaterOpacity: (v: number) => void;
  onChangePopOpacity: (v: number) => void;
}

const rowStyle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, cursor: "pointer" };

interface OpacitySliderProps {
  label: string;
  value: number;
  disabled: boolean;
  onChange: (v: number) => void;
}

const OpacitySlider: React.FC<OpacitySliderProps> = ({ label, value, disabled, onChange }) => {
  const pct = Math.round(value * 100);
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        paddingLeft: 20,
        fontSize: 12,
        color: disabled ? "#94a3b8" : "#475569"
      }}
    >
      <span style={{ minWidth: 74 }}>Độ mờ: {pct}%</span>
      <input
        type="range"
        aria-label={label}
        min={0}
        max={100}
        step={5}
        value={pct}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        style={{ flex: 1, cursor: disabled ? "not-allowed" : "pointer" }}
      />
    </label>
  );
};

export const LayerControl: React.FC<LayerControlProps> = ({
  showWater,
  showPopulation,
  onlyBuffer,
  waterOpacity,
  popOpacity,
  onToggleWater,
  onTogglePopulation,
  onToggleOnlyBuffer,
  onChangeWaterOpacity,
  onChangePopOpacity
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <strong>Điều khiển lớp bản đồ</strong>
      <label style={rowStyle}>
        <input type="checkbox" checked={showWater} onChange={(e) => onToggleWater(e.target.checked)} />
        <span style={{ width: 12, height: 12, background: "#2563eb", borderRadius: 2 }} />
        Lớp Mặt nước (MNDWI – Otsu)
      </label>
      <OpacitySlider label="Độ mờ lớp Mặt nước" value={waterOpacity} disabled={!showWater} onChange={onChangeWaterOpacity} />
      <label style={rowStyle}>
        <input type="checkbox" checked={showPopulation} onChange={(e) => onTogglePopulation(e.target.checked)} />
        <span style={{ width: 12, height: 12, background: "linear-gradient(90deg,#fdd49e,#b30000)", borderRadius: 2 }} />
        Lớp Dân cư (GHSL 250m)
      </label>
      <OpacitySlider label="Độ mờ lớp Dân cư" value={popOpacity} disabled={!showPopulation} onChange={onChangePopOpacity} />
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
