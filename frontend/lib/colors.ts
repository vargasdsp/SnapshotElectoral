import { Sensibilidad, SENSIBILIDAD_COLORS } from "@/types/electoral";

export function choroplethColor(
  pct: number,
  sensibilidad: Sensibilidad,
  range?: { min: number; max: number },
): string {
  const { main } = SENSIBILIDAD_COLORS[sensibilidad];

  const r = parseInt(main.slice(1, 3), 16);
  const g = parseInt(main.slice(3, 5), 16);
  const b = parseInt(main.slice(5, 7), 16);

  // Relative scale: map the dataset's actual min..max to opacity 0.18..1.0.
  // Falls back to absolute 0..50 if no range provided.
  const lo = range?.min ?? 0;
  const hi = range?.max ?? 50;
  const span = Math.max(hi - lo, 1);
  const normalised = Math.min(Math.max((pct - lo) / span, 0), 1);
  const curved = Math.pow(normalised, 0.7);
  const opacity = 0.18 + curved * 0.82;
  return `rgba(${r},${g},${b},${opacity})`;
}

export function heatmapGradient(sensibilidad: Sensibilidad): Record<string, string> {
  const { main } = SENSIBILIDAD_COLORS[sensibilidad];
  return {
    "0.0": "rgba(0,0,0,0)",
    "0.4": `${main}55`,
    "0.7": `${main}99`,
    "1.0": main,
  };
}

export function swingColor(swing: number): string {
  if (swing > 3)  return "#27AE60";
  if (swing > 0)  return "#82E0AA";
  if (swing > -3) return "#F1948A";
  return "#C0392B";
}

export function censusColor(val: number, min: number, max: number): string {
  const span = Math.max(max - min, 1);
  const t = Math.min(Math.max((val - min) / span, 0), 1);
  const curved = Math.pow(t, 0.6);
  // Dark blue-grey → amber → red-orange
  const r = Math.round(44 + curved * (230 - 44));
  const g = Math.round(62 + curved * (126 - 62) * (1 - curved * 0.8));
  const b = Math.round(80 * (1 - curved));
  return `rgba(${r},${g},${b},${0.2 + curved * 0.8})`;
}

export function participationColor(pct: number): string {
  if (pct > 70) return "#1A5276";
  if (pct > 55) return "#2980B9";
  if (pct > 40) return "#AED6F1";
  return "#EBF5FB";
}
