import React, { useEffect, useRef, useState } from "react";
import type { PreloadProgress } from "../api/client";
import { formatTimelineLabel, getTimelineBracket } from "../utils/timeline";

export type PlaybackSpeed = 0.5 | 1 | 2;

const SPEEDS: PlaybackSpeed[] = [0.5, 1, 2];
/** Tốc độ chuẩn 1x: ~2.2 giây cho mỗi chặng 2 năm (8.8 giây cho toàn bộ 2016 → 2024). */
const YEARS_PER_SECOND_1X = 2 / 2.2;

interface TimeSliderProps {
  years: number[];
  timelineValue: number;
  onChange: (value: number) => void;
  playing: boolean;
  onPlayingChange: (playing: boolean) => void;
  disabled?: boolean;
  preloadStatus: PreloadProgress;
  onRequestPreload?: () => void;
}

export const TimeSlider: React.FC<TimeSliderProps> = ({
  years,
  timelineValue,
  onChange,
  playing,
  onPlayingChange,
  disabled = false,
  preloadStatus,
  onRequestPreload
}) => {
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);
  const [loop, setLoop] = useState<boolean>(true);
  const [pendingPlay, setPendingPlay] = useState<boolean>(false);

  const minYear = years[0] ?? 2016;
  const maxYear = years[years.length - 1] ?? 2024;
  const valueRef = useRef<number>(timelineValue);
  valueRef.current = timelineValue;

  // Vòng lặp 60 FPS bằng requestAnimationFrame
  useEffect(() => {
    if (!playing || disabled || !preloadStatus.ready || years.length < 2) return;
    let rafId = 0;
    let lastTs = performance.now();

    const step = (now: number) => {
      const dt = Math.min((now - lastTs) / 1000, 0.1);
      lastTs = now;

      let next = valueRef.current + dt * YEARS_PER_SECOND_1X * speed;
      if (next >= maxYear) {
        if (loop) {
          const span = maxYear - minYear;
          next = span > 0 ? minYear + ((next - maxYear) % span) : minYear;
        } else {
          valueRef.current = maxYear;
          onChange(maxYear);
          onPlayingChange(false);
          return;
        }
      }

      valueRef.current = next;
      onChange(next);
      rafId = requestAnimationFrame(step);
    };

    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [playing, disabled, preloadStatus.ready, speed, loop, minYear, maxYear, years.length, onChange, onPlayingChange]);

  // Tự động phát khi preload xong nếu người dùng vừa bấm Play
  useEffect(() => {
    if (pendingPlay && preloadStatus.ready && !disabled) {
      setPendingPlay(false);
      onPlayingChange(true);
    }
  }, [pendingPlay, preloadStatus.ready, disabled, onPlayingChange]);

  // Tự động tạm dừng khi bị khóa (Compare Mode)
  useEffect(() => {
    if (disabled) {
      setPendingPlay(false);
      if (playing) onPlayingChange(false);
    }
  }, [disabled, playing, onPlayingChange]);

  const handleTogglePlay = () => {
    if (disabled) return;
    if (playing) {
      setPendingPlay(false);
      onPlayingChange(false);
      return;
    }
    if (timelineValue >= maxYear - 0.01) {
      valueRef.current = minYear;
      onChange(minYear);
    }
    if (!preloadStatus.ready) {
      onRequestPreload?.();
      setPendingPlay(true);
    } else {
      onPlayingChange(true);
    }
  };

  const handleJumpYear = (y: number) => {
    if (disabled) return;
    valueRef.current = y;
    onChange(y);
  };

  const bracket = getTimelineBracket(timelineValue, years);
  const progressPct = maxYear > minYear ? ((timelineValue - minYear) / (maxYear - minYear)) * 100 : 0;
  const preloadPct = preloadStatus.total > 0 ? Math.round((preloadStatus.loaded / preloadStatus.total) * 100) : 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", opacity: disabled ? 0.5 : 1 }}>
      {/* Nút Play / Pause */}
      <button
        type="button"
        onClick={handleTogglePlay}
        disabled={disabled}
        title={playing ? "Tạm dừng timelapse" : pendingPlay ? "Đang tải dữ liệu 5 năm…" : "Phát video timelapse"}
        style={{
          width: 34,
          height: 34,
          borderRadius: "50%",
          border: "none",
          background: playing ? "#f97316" : pendingPlay ? "#eab308" : "#2563eb",
          color: "#fff",
          fontSize: 13,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: disabled ? "not-allowed" : "pointer",
          flexShrink: 0
        }}
      >
        {playing ? "❚❚" : pendingPlay ? "⏳" : "▶"}
      </button>

      {/* Thanh tua liên tục 2016.0 → 2024.0 */}
      <div style={{ display: "flex", flexDirection: "column", width: 250, gap: 2 }}>
        <input
          id="year-slider"
          type="range"
          min={minYear}
          max={maxYear}
          step={0.01}
          value={timelineValue}
          disabled={disabled}
          onChange={(e) => {
            const v = Number(e.target.value);
            valueRef.current = v;
            onChange(v);
          }}
          style={{
            width: "100%",
            height: 6,
            cursor: disabled ? "not-allowed" : "pointer",
            accentColor: "#38bdf8",
            background: `linear-gradient(to right, #38bdf8 0%, #38bdf8 ${progressPct}%, #334155 ${progressPct}%, #334155 100%)`,
            borderRadius: 999
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
          {years.map((y) => {
            const isNearest = y === bracket.nearestYear;
            return (
              <span
                key={y}
                onClick={() => handleJumpYear(y)}
                title={`Nhảy tới mốc năm ${y}`}
                style={{
                  cursor: disabled ? "default" : "pointer",
                  fontWeight: isNearest ? 700 : 400,
                  color: isNearest ? "#38bdf8" : "#cbd5e1",
                  userSelect: "none"
                }}
              >
                {y}
              </span>
            );
          })}
        </div>
      </div>

      {/* Nhãn thời gian liên tục */}
      <label
        htmlFor="year-slider"
        style={{
          minWidth: 148,
          fontSize: 13,
          fontWeight: 700,
          fontVariantNumeric: "tabular-nums",
          color: "#f8fafc",
          whiteSpace: "nowrap"
        }}
      >
        {formatTimelineLabel(timelineValue)}
      </label>

      {/* Tốc độ phát 0.5x / 1x / 2x */}
      <div
        role="group"
        aria-label="Tốc độ phát"
        style={{ display: "flex", background: "#1e293b", borderRadius: 6, padding: 2, gap: 2 }}
      >
        {SPEEDS.map((s) => {
          const active = speed === s;
          return (
            <button
              key={s}
              type="button"
              disabled={disabled}
              onClick={() => setSpeed(s)}
              title={`Tốc độ ${s}x`}
              style={{
                border: "none",
                borderRadius: 4,
                padding: "3px 7px",
                fontSize: 11,
                fontWeight: active ? 700 : 500,
                background: active ? "#2563eb" : "transparent",
                color: active ? "#fff" : "#cbd5e1",
                cursor: disabled ? "not-allowed" : "pointer"
              }}
            >
              {s}x
            </button>
          );
        })}
      </div>

      {/* Nút Lặp lại (Loop) */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setLoop((l) => !l)}
        aria-pressed={loop}
        title={loop ? "Đang bật lặp lại (Loop)" : "Đang tắt lặp lại (Loop)"}
        style={{
          border: loop ? "1px solid #38bdf8" : "1px solid #334155",
          borderRadius: 6,
          padding: "3px 8px",
          fontSize: 11,
          fontWeight: 600,
          background: loop ? "#0369a1" : "#1e293b",
          color: loop ? "#fff" : "#94a3b8",
          cursor: disabled ? "not-allowed" : "pointer",
          whiteSpace: "nowrap"
        }}
      >
        ↻ Lặp
      </button>

      {/* Trạng thái preload cache 5 năm */}
      {preloadStatus.error ? (
        <span
          title={preloadStatus.error}
          style={{
            fontSize: 11,
            padding: "2px 8px",
            borderRadius: 10,
            background: "#991b1b",
            color: "#fecaca",
            whiteSpace: "nowrap"
          }}
        >
          ⚠ Lỗi tải cache
        </span>
      ) : preloadStatus.ready ? (
        <span
          title="Đã tải trước và cache toàn bộ 5 mốc năm (2016–2024)"
          style={{
            fontSize: 11,
            padding: "2px 8px",
            borderRadius: 10,
            background: "#14532d",
            color: "#bbf7d0",
            whiteSpace: "nowrap"
          }}
        >
          ✓ Cache 5 năm
        </span>
      ) : (
        <span
          title={`Đang tải trước dữ liệu 5 năm (${preloadStatus.loaded}/${preloadStatus.total})`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            padding: "2px 8px",
            borderRadius: 10,
            background: "#1e293b",
            color: "#bae6fd",
            whiteSpace: "nowrap",
            fontVariantNumeric: "tabular-nums"
          }}
        >
          <span>
            Đang đệm {preloadStatus.loaded}/{preloadStatus.total}
          </span>
          <span
            style={{
              width: 34,
              height: 4,
              background: "#334155",
              borderRadius: 999,
              overflow: "hidden",
              display: "inline-block"
            }}
          >
            <span
              style={{
                display: "block",
                width: `${preloadPct}%`,
                height: "100%",
                background: "#38bdf8"
              }}
            />
          </span>
        </span>
      )}
    </div>
  );
};
