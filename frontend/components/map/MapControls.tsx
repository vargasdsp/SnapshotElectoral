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
    <div className="glass rounded-2xl p-1 flex gap-1">
      {LAYERS.map(l => (
        <button
          key={l.id}
          onClick={() => onChange(l.id)}
          className="px-4 py-2 rounded-xl text-xs font-medium transition-all duration-200 flex items-center gap-1.5"
          style={{
            background: activeLayer === l.id ? "rgba(255,255,255,0.1)" : "transparent",
            color: activeLayer === l.id ? "#fff" : "#666",
          }}
        >
          <span>{l.icon}</span>
          {l.label}
        </button>
      ))}
    </div>
  );
}
