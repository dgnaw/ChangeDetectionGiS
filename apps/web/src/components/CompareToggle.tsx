import React from "react";

interface CompareToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  years?: number[];
  /** Cặp năm so sánh [trái, phải] — mặc định 2016 vs 2024. */
  compareYears?: [number, number];
  onChangeYears?: (years: [number, number]) => void;
}

export const CompareToggle: React.FC<CompareToggleProps> = ({
  enabled,
  onToggle,
  years = [2016, 2018, 2020, 2022, 2024],
  compareYears = [2016, 2024],
  onChangeYears
}) => {
  const [left, right] = compareYears;
  const select = (value: number, onChange: (v: number) => void) => (
    <select
      value={value}
      disabled={!enabled || !onChangeYears}
      onChange={(e) => onChange(Number(e.target.value))}
      style={{ padding: "2px 4px" }}
    >
      {years.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </select>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
        <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
        <strong>
          Chế độ So sánh {left} vs {right}
        </strong>
      </label>
      {enabled && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, paddingLeft: 22, fontSize: 13 }}>
          Trái {select(left, (v) => onChangeYears?.([v, right]))} ⇄ Phải{" "}
          {select(right, (v) => onChangeYears?.([left, v]))}
        </div>
      )}
      {enabled && (
        <small style={{ paddingLeft: 22, color: "#64748b" }}>
          2 bản đồ được đồng bộ vị trí/zoom. Thanh thời gian tạm khóa.
        </small>
      )}
    </div>
  );
};
