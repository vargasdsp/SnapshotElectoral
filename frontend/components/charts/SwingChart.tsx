"use client";

import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { partidoColor } from "@/lib/partidoColors";

interface Props {
  topCandidatos: Array<{ candidato: string; partido: string; votos: number }>;
  sensibilidadColor: string;
  onCandidatoClick?: (candidato: string) => void;
}

export default function SwingChart({ topCandidatos, sensibilidadColor, onCandidatoClick }: Props) {
  if (!topCandidatos.length) return null;

  const maxVotos = Math.max(...topCandidatos.map(c => c.votos));
  const data = topCandidatos.map(c => ({
    name: c.candidato.split(" ").slice(-1)[0], // last name only
    fullName: c.candidato,
    partido: c.partido,
    votos: Math.round(c.votos),
    pct: (c.votos / maxVotos * 100).toFixed(1),
    color: partidoColor(c.partido),
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}
                layout="vertical">
        <XAxis type="number" tick={false} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" tick={{ fill: "#888", fontSize: 11 }}
               axisLine={false} tickLine={false} width={70} />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload;
            return (
              <div className="glass rounded-xl px-3 py-2 text-xs">
                <p className="text-white font-semibold">{d.fullName}</p>
                <p className="text-gray-400">{d.partido}</p>
                <p className="text-white mt-1">{d.votos.toLocaleString("es-CL")} votos</p>
              </div>
            );
          }}
        />
        <Bar dataKey="votos" radius={[0, 4, 4, 0]}
             cursor={onCandidatoClick ? "pointer" : undefined}
             onClick={(d: any) => onCandidatoClick?.(d?.fullName)}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.color} opacity={1 - i * 0.08} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
