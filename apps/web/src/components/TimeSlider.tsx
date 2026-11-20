import React, { useEffect, useState } from "react";

interface TimeSliderProps {
  years: number[];
  selectedYear: number;
  onChange: (year: number) => void;
  disabled?: boolean;
  /** Thời gian dừng ở mỗi mốc năm khi Play (ms). */
  intervalMs?: number;
}

export const TimeSlider: React.FC<TimeSliderProps> = ({
  years,
  selectedYear,
  onChange,
  disabled = false,
  intervalMs = 1500
}) => {
  const [playing, setPlaying] = useState(false);
  const idx = Math.max(years.indexOf(selectedYear), 0);

  // Play/Pause: tự chạy 2016 → 2024 rồi quay vòng
  useEffect(() => {
    if (!playing || disabled || years.length === 0) return;
    const t = setTimeout(() => onChange(years[(idx + 1) % years.length]), intervalMs);
    return () => clearTimeout(t);
  }, [playing, disabled, idx, years, onChange, intervalMs]);

  useEffect(() => {
    if (disabled) setPlaying(false);
  }, [disabled]);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, opacity: disabled ? 0.5 : 1 }}>
      <button
        onClick={() => setPlaying((p) => !p)}
        disabled={disabled}
        title={playing ? "Tạm dừng" : "Phát chuỗi thời gian"}
        style={{
          width: 34,
          height: 34,
          borderRadius: "50%",
          border: "none",
          background: playing ? "#f97316" : "#2563eb",
          color: "#fff",
          fontSize: 14,
          cursor: disabled ? "not-allowed" : "pointer"
        }}
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <div style={{ display: "flex", flexDirection: "column", width: 260 }}>
        <input
          id="year-slider"
          type="range"
          min={0}
          max={Math.max(years.length - 1, 0)}
          step={1}
          value={idx}
          disabled={disabled}
          onChange={(e) => onChange(years[Number(e.target.value)])}
          style={{ width: "100%", accentColor: "#38bdf8" }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
          {years.map((y) => (
            <span
              key={y}
              onClick={() => !disabled && onChange(y)}
              style={{
                cursor: disabled ? "default" : "pointer",
                fontWeight: y === selectedYear ? 700 : 400,
                color: y === selectedYear ? "#38bdf8" : "#cbd5e1"
              }}
            >
              {y}
            </span>
          ))}
        </div>
      </div>
      <label htmlFor="year-slider" style={{ minWidth: 80 }}>
        <strong>Năm: {selectedYear}</strong>
      </label>
    </div>
  );
};
