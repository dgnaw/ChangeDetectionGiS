import React from "react";

interface TimeSliderProps {
  years: number[];
  selectedYear: number;
  onChange: (year: number) => void;
}

export const TimeSlider: React.FC<TimeSliderProps> = ({ years, selectedYear, onChange }) => {
  const idx = years.indexOf(selectedYear);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <label htmlFor="year-slider">
        <strong>Năm: {selectedYear}</strong>
      </label>
      <input
        id="year-slider"
        type="range"
        min={0}
        max={Math.max(years.length - 1, 0)}
        step={1}
        value={idx >= 0 ? idx : 0}
        onChange={(e) => onChange(years[Number(e.target.value)])}
      />
    </div>
  );
};
