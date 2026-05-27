"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import WizardFlow from "@/components/wizard/WizardFlow";
import { WizardMode, WizardState } from "@/types/electoral";

export default function Landing() {
  const [mode, setMode] = useState<WizardMode | null>(null);
  const router = useRouter();

  function handleComplete(state: WizardState) {
    const { cargo } = state;
    if (!cargo) return;

    // Flujo de distrito (candidato a diputado): comuna es null y hay distritoId
    if (state.mode === "candidato" && state.sensibilidad && state.distritoId) {
      const params = new URLSearchParams({
        cargo,
        sensibilidad: state.sensibilidad,
        distrito_id: String(state.distritoId),
      });
      router.push(`/snapshot?${params}`);
      return;
    }

    // Autoridad + distrito (diputado)
    if (state.mode === "autoridad" && state.candidato && state.distritoId) {
      const params = new URLSearchParams({
        cargo, candidato: state.candidato,
        distrito_id: String(state.distritoId), mode: "autoridad",
      });
      router.push(`/snapshot?${params}`);
      return;
    }

    // Flujo de comuna (todos los otros casos)
    if (!state.comuna) return;
    if (state.mode === "candidato" && state.sensibilidad) {
      const params = new URLSearchParams({
        cargo, sensibilidad: state.sensibilidad, comuna: state.comuna,
      });
      router.push(`/snapshot?${params}`);
    } else if (state.mode === "autoridad" && state.candidato) {
      const params = new URLSearchParams({
        cargo, candidato: state.candidato, comuna: state.comuna, mode: "autoridad",
      });
      router.push(`/snapshot?${params}`);
    }
  }

  if (mode) {
    return <WizardFlow mode={mode} onComplete={handleComplete} onBack={() => setMode(null)} />;
  }

  return (
    <main className="relative w-screen min-h-[100dvh] flex flex-col items-center justify-center overflow-x-hidden"
          style={{ background: "#111114" }}>

      <div className="absolute inset-0 opacity-[0.03]"
           style={{
             backgroundImage: `linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
                               linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)`,
             backgroundSize: "48px 48px",
           }} />
      <div className="absolute inset-0 pointer-events-none"
           style={{
             background: "radial-gradient(ellipse 80% 60% at 50% 50%, rgba(41,128,185,0.06) 0%, transparent 70%)",
           }} />

      <div className="absolute top-4 left-4 sm:top-8 sm:left-8 flex items-center gap-2 animate-fade-in">
        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        <span className="text-[10px] sm:text-xs font-medium tracking-[0.2em] text-gray-500 uppercase">
          Inteligencia Electoral · Chile
        </span>
      </div>

      <div className="relative z-10 flex flex-col items-center text-center px-5 sm:px-6 animate-slide-up py-16 sm:py-0">
        <p className="text-[10px] sm:text-xs font-medium tracking-[0.3em] text-gray-500 uppercase mb-5 sm:mb-8">
          Plataforma de análisis electoral
        </p>

        <h1 className="text-4xl sm:text-5xl md:text-7xl font-bold leading-none mb-3 sm:mb-4"
            style={{ letterSpacing: "-0.03em", color: "#F0F0F0" }}>
          Snapshot<br />
          <span style={{
            background: "linear-gradient(135deg, #E74C3C 0%, #C0392B 50%, #922B21 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
            electoral
          </span>
        </h1>

        <p className="text-gray-400 text-sm sm:text-lg max-w-lg leading-relaxed mb-6 sm:mb-12 px-2">
          Datos públicos de SERVEL y Censo 2024 integrados en un visualizador territorial para Chile.
        </p>

        {/* Two CTAs */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4 w-full max-w-2xl">

          {/* Candidato */}
          <button
            onClick={() => setMode("candidato")}
            className="group relative p-4 sm:p-6 rounded-xl sm:rounded-2xl text-left overflow-hidden transition-all duration-300 hover:scale-[1.02]"
            style={{
              background: "#202026",
              border: "1px solid rgba(180,70,70,0.45)",
              boxShadow: "0 0 32px rgba(140,40,40,0.12)",
            }}
          >
            <div className="relative z-10">
              <p className="text-[10px] sm:text-xs tracking-[0.2em] uppercase mb-2 sm:mb-3 font-medium"
                 style={{ color: "#C0605060" }}>
                Proyección
              </p>
              <p className="text-xl sm:text-3xl font-bold mb-1.5 sm:mb-2" style={{ color: "#F0F0F0" }}>
                Quiero ser candidato
              </p>
              <p className="text-xs sm:text-sm text-gray-400 leading-snug">
                Explora fortalezas y debilidades de un sector político
                en cualquier comuna del país.
              </p>
              <div className="mt-3 sm:mt-4 text-[11px] sm:text-xs opacity-50 group-hover:opacity-90 transition-opacity"
                   style={{ color: "#CC7070" }}>
                Comenzar análisis territorial →
              </div>
            </div>
            <div className="absolute inset-0 bg-white opacity-0 group-hover:opacity-[0.03] transition-opacity" />
          </button>

          {/* Autoridad */}
          <button
            onClick={() => setMode("autoridad")}
            className="group relative p-4 sm:p-6 rounded-xl sm:rounded-2xl text-left overflow-hidden transition-all duration-300 hover:scale-[1.02]"
            style={{
              background: "#202026",
              border: "1px solid rgba(255,255,255,0.12)",
              boxShadow: "0 0 32px rgba(0,0,0,0.2)",
            }}
          >
            <div className="relative z-10">
              <p className="text-[10px] sm:text-xs tracking-[0.2em] text-gray-500 uppercase mb-2 sm:mb-3 font-medium">
                Diagnóstico
              </p>
              <p className="text-xl sm:text-3xl font-bold mb-1.5 sm:mb-2" style={{ color: "#F0F0F0" }}>
                Soy autoridad
                <span className="block text-sm sm:text-base font-normal text-gray-500 mt-1">
                  o fui candidato
                </span>
              </p>
              <p className="text-xs sm:text-sm text-gray-400 leading-snug mt-2">
                Visualiza tu desempeño territorial real
                y compáralo con tu sector.
              </p>
              <div className="mt-3 sm:mt-4 text-[11px] sm:text-xs text-gray-500 group-hover:text-gray-300 transition-colors">
                ¿Quién eres? →
              </div>
            </div>
            <div className="absolute inset-0 bg-white opacity-0 group-hover:opacity-[0.03] transition-opacity" />
          </button>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 mt-6 sm:mt-10">
          {["4 cargos", "6 sensibilidades", "Mapa territorial", "Histórico"].map(f => (
            <span key={f}
                  className="px-2.5 sm:px-3 py-1 text-[10px] sm:text-xs text-gray-500 border border-gray-800 rounded-full">
              {f}
            </span>
          ))}
        </div>

        <div className="mt-8 sm:hidden text-[10px] text-gray-700 text-center leading-relaxed">
          Por{" "}
          <a href="https://linkedin.com/in/nicolas-vv" target="_blank" rel="noopener noreferrer"
             className="text-gray-500 underline underline-offset-2">
            Nicolás Vargas Venegas
          </a>
          {" "}· SERVEL + Censo INE 2024
        </div>
      </div>

      <div className="hidden sm:block absolute bottom-6 right-6 text-xs text-gray-700 text-right leading-relaxed">
        Herramienta creada por{" "}
        <a href="https://linkedin.com/in/nicolas-vv" target="_blank" rel="noopener noreferrer"
           className="text-gray-500 hover:text-gray-300 transition-colors underline underline-offset-2">
          Nicolás Vargas Venegas
        </a>
        <br />
        Datos: SERVEL · Censo INE 2024
      </div>
    </main>
  );
}
