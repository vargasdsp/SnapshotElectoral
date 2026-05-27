"use client";

interface Props {
  activeLayer: "choropleth" | "heatmap" | "winner" | "debilidades";
  onChange: (layer: "choropleth" | "heatmap" | "winner" | "debilidades") => void;
}

const LAYERS = [
  { id: "choropleth"  as const, label: "Intensidad",   icon: "▦" },
  { id: "winner"      as const, label: "Fortalezas",   icon: "▲" },
  { id: "debilidades" as const, label: "Debilidades",  icon: "▽" },
];

export default function MapControls({ activeLayer, onChange }: Props) {
  return (
    <div className="glass rounded-xl sm:rounded-2xl p-1 flex gap-0.5 sm:gap-1">
      {LAYERS.map(l => (
        <button
          key={l.id}
          onClick={() => onChange(l.id)}
          className="px-2 sm:px-4 py-1.5 sm:py-2 rounded-lg sm:rounded-xl text-[11px] sm:text-xs font-medium transition-all duration-200 flex items-center gap-1 sm:gap-1.5"
          style={{
            background: activeLayer === l.id ? "rgba(255,255,255,0.1)" : "transparent",
            color: activeLayer === l.id ? "#fff" : "#666",
          }}
          aria-label={l.label}
        >
          <span>{l.icon}</span>
          <span className="hidden sm:inline">{l.label}</span>
        </button>
      ))}
    </div>
  );
}
