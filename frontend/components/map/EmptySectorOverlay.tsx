"use client";

import { useRouter } from "next/navigation";
import {
  AlternativaSector, ConcejalProxy, Sensibilidad,
  SENSIBILIDAD_COLORS, SENSIBILIDAD_LABELS, CARGO_LABELS, Cargo,
} from "@/types/electoral";

interface Props {
  comuna: string;
  cargo: Cargo;
  sensibilidad: Sensibilidad;
  alternativas: AlternativaSector[];
  proxyConcejales: ConcejalProxy | null;
}

export default function EmptySectorOverlay({
  comuna, cargo, sensibilidad, alternativas, proxyConcejales,
}: Props) {
  const router = useRouter();
  const colorMain = SENSIBILIDAD_COLORS[sensibilidad].main;

  function switchTo(opts: { newSens?: Sensibilidad; newCargo?: Cargo }) {
    const params = new URLSearchParams({
      comuna,
      cargo: opts.newCargo ?? cargo,
      sensibilidad: opts.newSens ?? sensibilidad,
    });
    router.replace(`/snapshot?${params.toString()}`);
  }

  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-none">
      <div className="glass rounded-2xl p-6 max-w-md w-full mx-6 pointer-events-auto animate-fade-in"
           style={{ borderColor: colorMain }}>

        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full" style={{ background: colorMain }} />
          <p className="text-xs uppercase tracking-wider text-gray-500 font-medium">
            Sin candidatos del sector
          </p>
        </div>

        <h3 className="text-lg font-bold text-white leading-tight mb-2">
          La <span style={{ color: colorMain }}>{SENSIBILIDAD_LABELS[sensibilidad].toLowerCase()}</span> no
          presentó candidatos a {CARGO_LABELS[cargo].toLowerCase()} en {comuna.charAt(0) + comuna.slice(1).toLowerCase()}.
        </h3>

        <p className="text-sm text-gray-400 mb-4 leading-snug">
          Pero hay alternativas para leer el territorio:
        </p>

        {/* Adjacent sensibilidades */}
        {alternativas.length > 0 && (
          <div className="mb-4">
            <p className="text-[10px] uppercase tracking-wider text-gray-600 mb-2 font-medium">
              Sectores con candidatos en {CARGO_LABELS[cargo].toLowerCase()}
            </p>
            <div className="flex flex-col gap-1.5">
              {alternativas.slice(0, 4).map(a => {
                const c = SENSIBILIDAD_COLORS[a.sensibilidad].main;
                return (
                  <button key={a.sensibilidad}
                          onClick={() => switchTo({ newSens: a.sensibilidad })}
                          className="flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors hover:bg-white hover:bg-opacity-5"
                          style={{ background: "#16161E", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: c }} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white">
                        {SENSIBILIDAD_LABELS[a.sensibilidad]}
                      </div>
                      <div className="text-[10px] text-gray-500">
                        {a.candidatos} candidato{a.candidatos !== 1 ? "s" : ""}
                      </div>
                    </div>
                    <div className="text-sm font-bold text-white">
                      {a.voto_promedio_pct.toFixed(1)}%
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Concejal proxy */}
        {proxyConcejales && cargo !== "concejal" && (
          <div className="border-t pt-4 mt-4" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
            <p className="text-[10px] uppercase tracking-wider text-gray-600 mb-2 font-medium">
              Proyección desde concejales
            </p>
            <button onClick={() => switchTo({ newCargo: "concejal" })}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors hover:bg-white hover:bg-opacity-5"
                    style={{
                      background: "#16161E",
                      border: `1px solid ${colorMain}40`,
                    }}>
              <div className="flex-1 text-left">
                <div className="text-sm text-white">
                  Ver desempeño en concejales
                </div>
                <div className="text-[10px] text-gray-500">
                  {proxyConcejales.candidatos} candidato{proxyConcejales.candidatos !== 1 ? "s" : ""} del sector · {proxyConcejales.manzanas_con_datos} manzanas
                </div>
              </div>
              <div className="text-right">
                <div className="text-base font-bold" style={{ color: colorMain }}>
                  {proxyConcejales.voto_promedio_pct.toFixed(1)}%
                </div>
                <div className="text-[9px] text-gray-600">como proxy</div>
              </div>
            </button>
            <p className="text-[10px] text-gray-600 mt-2 leading-snug">
              Los concejales reflejan mejor la distribución territorial de las fuerzas
              políticas, ya que compiten más listas por elección.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
