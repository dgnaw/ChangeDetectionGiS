import type { TimeseriesPoint } from "../api/client";

export interface TimelineBracket {
  yearA: number;
  yearB: number;
  rawAlpha: number;
  easedAlpha: number;
  nearestYear: number;
  isExactMilestone: boolean;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Easing nhẹ giúp chuyển cảnh mượt mà nhưng không bị khựng tại các mốc năm trung gian. */
export function easeGentle(t: number): number {
  const clamped = Math.max(0, Math.min(1, t));
  const smooth = clamped * clamped * (3 - 2 * clamped);
  return 0.5 * clamped + 0.5 * smooth;
}

export function getTimelineBracket(value: number, years: readonly number[]): TimelineBracket {
  if (years.length === 0) {
    return { yearA: 2016, yearB: 2016, rawAlpha: 0, easedAlpha: 0, nearestYear: 2016, isExactMilestone: true };
  }
  const minY = years[0];
  const maxY = years[years.length - 1];
  const v = Math.max(minY, Math.min(maxY, value));

  for (const y of years) {
    if (Math.abs(v - y) <= 1e-4) {
      return {
        yearA: y,
        yearB: y,
        rawAlpha: 0,
        easedAlpha: 0,
        nearestYear: y,
        isExactMilestone: true
      };
    }
  }

  for (let i = 0; i < years.length - 1; i++) {
    const yearA = years[i];
    const yearB = years[i + 1];
    if (v >= yearA && v <= yearB) {
      const rawAlpha = yearB === yearA ? 0 : (v - yearA) / (yearB - yearA);
      const easedAlpha = easeGentle(rawAlpha);
      const nearestYear = rawAlpha < 0.5 ? yearA : yearB;
      return {
        yearA,
        yearB,
        rawAlpha,
        easedAlpha,
        nearestYear,
        isExactMilestone: false
      };
    }
  }

  return {
    yearA: maxY,
    yearB: maxY,
    rawAlpha: 0,
    easedAlpha: 0,
    nearestYear: maxY,
    isExactMilestone: true
  };
}

/**
 * Tính cặp độ mờ (opA, opB) theo công thức Porter-Duff giữ độ phủ không đổi:
 * - Vùng giao nhau (ổn định) luôn giữ độ mờ ổn định gần `baseOpacity`, tránh chớp trắng ở giữa.
 * - Vùng mới xuất hiện (gain) nổi dần từ 0 → baseOpacity.
 * - Vùng biến mất (loss) mờ dần từ baseOpacity → 0.
 */
export function computeCrossfadeOpacities(baseOpacity: number, alpha: number): { opA: number; opB: number } {
  const base = Math.max(0, Math.min(1, baseOpacity));
  const t = Math.max(0, Math.min(1, alpha));
  if (base === 0) return { opA: 0, opB: 0 };
  if (t <= 0) return { opA: base, opB: 0 };
  if (t >= 1) return { opA: 0, opB: base };
  const opB = base * t;
  const denom = 1 - opB;
  const opA = denom > 1e-6 ? Math.min(base, (base - opB) / denom) : base;
  return { opA, opB };
}

export function formatTimelineLabel(value: number): string {
  const v = Math.max(2016, Math.min(2024, value));
  const wholeYear = Math.floor(v + 1e-6);
  const frac = Math.max(0, v - wholeYear);
  const month = Math.min(12, Math.max(1, Math.floor(frac * 12) + 1));
  return `Năm ${wholeYear} · Tháng ${String(month).padStart(2, "0")}`;
}

export function interpolateTimeseries(series: TimeseriesPoint[], timelineValue: number): TimeseriesPoint | null {
  if (series.length === 0) return null;
  const sorted = [...series].sort((a, b) => a.year - b.year);
  const years = sorted.map((s) => s.year);
  const { yearA, yearB, rawAlpha } = getTimelineBracket(timelineValue, years);

  const pointA = sorted.find((s) => s.year === yearA);
  const pointB = sorted.find((s) => s.year === yearB);
  if (!pointA) return null;
  if (yearA === yearB || !pointB) return pointA;

  const jrcIou =
    pointA.jrc_iou_score !== null && pointB.jrc_iou_score !== null
      ? lerp(pointA.jrc_iou_score, pointB.jrc_iou_score, rawAlpha)
      : rawAlpha < 0.5
        ? pointA.jrc_iou_score
        : pointB.jrc_iou_score;

  return {
    year: timelineValue,
    water_area_km2: lerp(pointA.water_area_km2, pointB.water_area_km2, rawAlpha),
    water_ratio_pct: lerp(pointA.water_ratio_pct, pointB.water_ratio_pct, rawAlpha),
    water_gain_km2: lerp(pointA.water_gain_km2, pointB.water_gain_km2, rawAlpha),
    water_loss_km2: lerp(pointA.water_loss_km2, pointB.water_loss_km2, rawAlpha),
    otsu_threshold: lerp(pointA.otsu_threshold, pointB.otsu_threshold, rawAlpha),
    cloud_cover_pct: lerp(pointA.cloud_cover_pct, pointB.cloud_cover_pct, rawAlpha),
    total_pop: Math.round(lerp(pointA.total_pop, pointB.total_pop, rawAlpha)),
    pop_in_buffer_500m: Math.round(lerp(pointA.pop_in_buffer_500m, pointB.pop_in_buffer_500m, rawAlpha)),
    pop_buffer_ratio_pct: lerp(pointA.pop_buffer_ratio_pct, pointB.pop_buffer_ratio_pct, rawAlpha),
    jrc_iou_score: jrcIou
  };
}
