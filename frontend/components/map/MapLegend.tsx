"use client";

import { Sensibilidad, SENSIBILIDAD_COLORS, SENSIBILIDAD_LABELS } from "@/types/electoral";

interface Props {
  sensibilidad: Sensibilidad;
}

export default function MapLegend({ sensibilidad }: Props) {
  const { main } = SENSIBILIDAD_COLORS[sensibilidad];
  const label = SENSIBILIDAD_LABELS[sensibilidad];

  const stops = [
    { pct: "< 10%",  opacity: 0.08 },
    { pct: "20%",    opacity: 0.30 },
    { pct: "30%",    opacity: 0.55 },
    { pct: "40%",    opacity: 0.75 },
    { pct: "> 50%",  opacity: 0.95 },
  ];

  const r = parseInt(main.slice(1, 3), 16);
  const g = parseInt(main.slice(3, 5), 16);
  const b = parseInt(main.slice(5, 7), 16);

  return (
    <div className="glass rounded-xl p-3 min-w-[160px]">
      <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wider">
        {label}
      </p>
      <div className="flex items-center gap-1 mb-2">
        {stops.map(s => (
          <div key={s.pct}
               className="flex-1 h-3 rounded"
               style={{ background: `rgba(${r},${g},${b},${s.opacity})` }} />
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-gray-600">
        <span>Bajo</span>
        <span>Alto</span>
      </div>
    </div>
  );
}
