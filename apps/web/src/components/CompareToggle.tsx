import React from "react";

interface CompareToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}

export const CompareToggle: React.FC<CompareToggleProps> = ({ enabled, onToggle }) => {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
      <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
      <span>Chế độ So sánh 2016 vs 2024</span>
    </label>
  );
};
