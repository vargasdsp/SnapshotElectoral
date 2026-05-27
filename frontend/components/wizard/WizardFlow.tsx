"use client";

import { useState, useEffect, useRef } from "react";
import {
  Cargo, Sensibilidad, WizardState, WizardMode, CandidatoItem,
  CARGO_LABELS, SENSIBILIDAD_LABELS, SENSIBILIDAD_COLORS,
  SENSIBILIDAD_PARTIDOS_DISPLAY,
} from "@/types/electoral";
import {
  fetchComunasByRegion, fetchCandidatos, fetchDistritosByRegion, fetchCandidatosDistrito,
  RegionGroup, DistritoRegionGroup, Distrito,
} from "@/lib/api";

const CARGO_ICONS: Record<Cargo, string> = {
  concejal: "🏛", core: "🗺", alcalde: "🏙", diputado: "🏛",
};

function prettyRegion(name: string): string {
  // "DE LOS LAGOS" → "Los Lagos" / "METROPOLITANA DE SANTIAGO" → "Metropolitana"
  let s = name.replace(/^DE LA /, "").replace(/^DE LOS /, "").replace(/^DE /, "")
              .replace(/^DEL /, "").trim();
  if (s.startsWith("METROPOLITANA")) s = "Metropolitana";
  return s.charAt(0) + s.slice(1).toLowerCase();
}

function prettyComuna(name: string): string {
  return name.split(" ").map(w =>
    w.length > 0 ? w.charAt(0) + w.slice(1).toLowerCase() : w
  ).join(" ");
}
const CARGO_DESC: Record<Cargo, string> = {
  concejal: "Elecciones municipales 2024",
  core:     "Consejo Regional 2024",
  alcalde:  "Alcaldías 2024",
  diputado: "Cámara de Diputados 2025",
};

interface Props {
  mode: WizardMode;
  onComplete: (state: WizardState) => void;
  onBack: () => void;
}

export default function WizardFlow({ mode, onComplete, onBack }: Props) {
  const [step, setStep] = useState(0);
  const [cargo, setCargo] = useState<Cargo | null>(null);
  const [sensibilidad, setSensibilidad] = useState<Sensibilidad | null>(null);
  const [comuna, setComuna] = useState<string | null>(null);
  const [candidato, setCandidato] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [regionGroups, setRegionGroups] = useState<RegionGroup[]>([]);
  const [distritoGroups, setDistritoGroups] = useState<DistritoRegionGroup[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [distritoId, setDistritoId] = useState<number | null>(null);
  const [distritoNombre, setDistritoNombre] = useState<string | null>(null);

  const [candidatosList, setCandidatosList] = useState<CandidatoItem[]>([]);
  const [candidatoQuery, setCandidatoQuery] = useState("");
  const [filteredCandidatos, setFilteredCandidatos] = useState<CandidatoItem[]>([]);
  const [loadingCandidatos, setLoadingCandidatos] = useState(false);
  const [showAllCandidatos, setShowAllCandidatos] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  // Steps depend on mode:
  // candidato: 0=cargo, 1=sensibilidad, 2=comuna (o distrito si cargo=diputado)
  // autoridad: 0=cargo, 1=comuna, 2=candidato
  const usesDistrito = cargo === "diputado";
  const territorioLabel = usesDistrito ? "Distrito" : "Comuna";
  const steps = mode === "candidato"
    ? ["Cargo", "Sensibilidad", territorioLabel]
    : ["Cargo", territorioLabel, "¿Quién eres?"];

  // Load comunas (o distritos) when arriving at territorio step
  const comunaStepIdx = mode === "candidato" ? 2 : 1;
  useEffect(() => {
    if (step !== comunaStepIdx) return;
    setLoading(true);
    setLoadError(null);

    // Para diputado en modo candidato cargamos distritos en vez de comunas
    const loader = usesDistrito
      ? fetchDistritosByRegion().then(groups => {
          setDistritoGroups(groups);
          setRegionGroups([]);  // no usar comunas aquí
          if (groups.length === 0) {
            setLoadError("No hay distritos en el backend. Corre preprocessing/05_build_distritos.py.");
          }
        })
      : fetchComunasByRegion().then(groups => {
          setRegionGroups(groups);
          setDistritoGroups([]);
          if (groups.length === 0) {
            setLoadError("El backend respondió pero no hay comunas procesadas. Corre el pipeline en preprocessing/.");
          }
        });

    loader
      .catch((err) => {
        setRegionGroups([]); setDistritoGroups([]);
        setLoadError(
          `No se pudo conectar al backend (${err?.message || "error de red"}). ` +
          `Asegúrate de que esté corriendo en ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}.`
        );
      })
      .finally(() => setLoading(false));
  }, [step, comunaStepIdx, usesDistrito]);

  useEffect(() => {
    if (selectedRegion) setTimeout(() => inputRef.current?.focus(), 100);
  }, [selectedRegion]);

  // Comunas of the currently selected region, filtered by query
  const filteredComunas = (() => {
    if (!selectedRegion) return [];
    const group = regionGroups.find(g => g.region === selectedRegion);
    if (!group) return [];
    if (!query) return group.comunas;
    const q = query.toUpperCase();
    return group.comunas.filter(c => c.includes(q));
  })();

  // Global search across all regions (typing without picking region first)
  const globalSearchResults = (() => {
    if (!query || selectedRegion) return [];
    const q = query.toUpperCase();
    const matches: { region: string; comuna: string }[] = [];
    for (const g of regionGroups) {
      for (const c of g.comunas) {
        if (c.includes(q)) matches.push({ region: g.region, comuna: c });
        if (matches.length >= 12) return matches;
      }
    }
    return matches;
  })();

  // Load candidatos when arriving at candidato step (autoridad mode only)
  useEffect(() => {
    if (mode !== "autoridad" || step !== 2 || !cargo) return;
    if (usesDistrito && !distritoId) return;
    if (!usesDistrito && !comuna) return;
    setLoadingCandidatos(true);
    const fetchFn = usesDistrito
      ? fetchCandidatosDistrito(distritoId!, !showAllCandidatos)
      : fetchCandidatos(comuna!, cargo, !showAllCandidatos);
    fetchFn
      .then(list => { setCandidatosList(list); setFilteredCandidatos(list.slice(0, 20)); })
      .catch(() => setCandidatosList([]))
      .finally(() => setLoadingCandidatos(false));
    setTimeout(() => inputRef.current?.focus(), 100);
  }, [mode, step, cargo, comuna, distritoId, usesDistrito, showAllCandidatos]);

  useEffect(() => {
    if (!candidatoQuery) { setFilteredCandidatos(candidatosList.slice(0, 20)); return; }
    const q = candidatoQuery.toUpperCase();
    setFilteredCandidatos(
      candidatosList.filter(c =>
        c.candidato.includes(q) || c.partido.toUpperCase().includes(q)
      ).slice(0, 15)
    );
  }, [candidatoQuery, candidatosList]);

  function emit(finalState: Partial<WizardState>) {
    onComplete({
      mode,
      cargo: finalState.cargo ?? cargo,
      sensibilidad: finalState.sensibilidad ?? sensibilidad,
      comuna: finalState.comuna ?? comuna,
      candidato: finalState.candidato ?? candidato,
      distritoId: finalState.distritoId ?? distritoId ?? undefined,
      distritoNombre: finalState.distritoNombre ?? distritoNombre ?? undefined,
    });
  }

  function selectCargo(c: Cargo) { setCargo(c); setStep(1); }
  function selectSensibilidad(s: Sensibilidad) { setSensibilidad(s); setStep(2); }
  function selectComuna(c: string) {
    setComuna(c);
    if (mode === "candidato") {
      emit({ comuna: c });
    } else {
      setStep(2);
    }
  }
  function selectDistrito(d: Distrito) {
    if (mode === "candidato") {
      emit({ distritoId: d.distrito_id, distritoNombre: d.distrito, comuna: null });
    } else {
      // autoridad: guardar distrito y avanzar al paso de candidato
      setDistritoId(d.distrito_id);
      setDistritoNombre(d.distrito);
      setStep(2);
    }
  }
  function selectCandidato(c: CandidatoItem) {
    setCandidato(c.candidato);
    emit({ candidato: c.candidato });
  }

  function handleBack() {
    if (step === 0) onBack();
    else setStep(s => s - 1);
  }

  const accentColor = mode === "autoridad" ? "#2980B9" : "#C0392B";

  return (
    <div className="relative w-screen min-h-[100dvh] flex flex-col items-center justify-start pt-24 pb-10 sm:justify-center sm:pt-0 sm:pb-0"
         style={{ background: "#111114" }}>

      {/* Mode badge */}
      <div className="absolute top-3 sm:top-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 sm:gap-3">
        <div className="px-3 py-1 rounded-full text-[10px] tracking-[0.25em] uppercase font-semibold"
             style={{
               background: mode === "autoridad" ? "rgba(41,128,185,0.15)" : "rgba(192,57,43,0.15)",
               color: mode === "autoridad" ? "#5DADE2" : "#E74C3C",
               border: `1px solid ${mode === "autoridad" ? "rgba(41,128,185,0.3)" : "rgba(192,57,43,0.3)"}`,
             }}>
          {mode === "autoridad" ? "Modo autoridad" : "Modo candidato"}
        </div>

        <div className="flex items-center gap-1.5 sm:gap-3">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-1.5 sm:gap-3">
              <div className={`flex items-center gap-2 transition-all duration-300 ${i === step ? "opacity-100" : "opacity-30"}`}>
                <div className={`w-5 h-5 sm:w-6 sm:h-6 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-bold text-white`}
                     style={{
                       background: i <= step ? accentColor : "#28282E",
                     }}>
                  {i < step ? "✓" : i + 1}
                </div>
                <span className="text-xs text-gray-400 font-medium hidden sm:block">{s}</span>
              </div>
              {i < steps.length - 1 && (
                <div className="w-5 sm:w-12 h-px"
                     style={{ background: i < step ? accentColor : "#28282E" }} />
              )}
            </div>
          ))}
        </div>
      </div>

      <button onClick={handleBack}
              className="absolute top-3 left-3 sm:top-8 sm:left-8 text-gray-500 hover:text-gray-300 text-xs sm:text-sm transition-colors flex items-center gap-2 z-10">
        ← Volver
      </button>

      <div className="w-full max-w-4xl px-4 sm:px-6 animate-slide-up">

        {/* Step 0: Cargo (both modes) */}
        {step === 0 && (
          <div>
            <p className="text-center text-[10px] sm:text-xs tracking-[0.3em] text-gray-500 uppercase mb-3 sm:mb-4">Paso 1 de 3</p>
            <h2 className="text-center text-2xl sm:text-4xl font-bold text-white mb-2 leading-tight">
              {mode === "autoridad" ? "¿Qué cargo ocupas?" : "¿Para qué cargo?"}
            </h2>
            <p className="text-center text-sm sm:text-base text-gray-500 mb-6 sm:mb-10 px-2">
              {mode === "autoridad"
                ? "Selecciona el cargo en el que fuiste electo"
                : "Selecciona el tipo de elección que quieres analizar"}
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
              {(Object.keys(CARGO_LABELS) as Cargo[]).map(c => (
                <button key={c} onClick={() => selectCargo(c)}
                        className="group p-4 sm:p-6 rounded-xl sm:rounded-2xl border text-left transition-all duration-200 hover:scale-105"
                        style={{ background: "#202026", borderColor: "rgba(255,255,255,0.08)" }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLElement).style.borderColor = accentColor;
                          (e.currentTarget as HTMLElement).style.boxShadow = `0 0 24px ${accentColor}33`;
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.08)";
                          (e.currentTarget as HTMLElement).style.boxShadow = "none";
                        }}>
                  <div className="text-2xl sm:text-3xl mb-2 sm:mb-4">{CARGO_ICONS[c]}</div>
                  <div className="font-semibold text-white text-base sm:text-lg mb-1">{CARGO_LABELS[c]}</div>
                  <div className="text-[11px] sm:text-xs text-gray-500 leading-snug">{CARGO_DESC[c]}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 1 (candidato): Sensibilidad */}
        {mode === "candidato" && step === 1 && (
          <div>
            <p className="text-center text-[10px] sm:text-xs tracking-[0.3em] text-gray-500 uppercase mb-3 sm:mb-4">Paso 2 de 3</p>
            <h2 className="text-center text-2xl sm:text-4xl font-bold text-white mb-2 leading-tight">¿Qué sector político?</h2>
            <p className="text-center text-sm sm:text-base text-gray-500 mb-6 sm:mb-10 px-2">
              Selecciona la sensibilidad que quieres analizar en el territorio
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
              {(Object.keys(SENSIBILIDAD_LABELS) as Sensibilidad[]).map(s => {
                const { main } = SENSIBILIDAD_COLORS[s];
                const partidos = SENSIBILIDAD_PARTIDOS_DISPLAY[s];
                return (
                  <button key={s} onClick={() => selectSensibilidad(s)}
                          className="group p-4 sm:p-6 rounded-xl sm:rounded-2xl border text-left transition-all duration-200 hover:scale-105 flex flex-col"
                          style={{ background: "#202026", borderColor: "rgba(255,255,255,0.08)" }}
                          onMouseEnter={e => {
                            (e.currentTarget as HTMLElement).style.borderColor = main;
                            (e.currentTarget as HTMLElement).style.boxShadow = `0 0 24px ${main}33`;
                          }}
                          onMouseLeave={e => {
                            (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.08)";
                            (e.currentTarget as HTMLElement).style.boxShadow = "none";
                          }}>
                    <div className="w-3.5 h-3.5 sm:w-4 sm:h-4 rounded-full mb-3 sm:mb-4" style={{ background: main }} />
                    <div className="font-semibold text-white text-base sm:text-xl mb-2 sm:mb-3 leading-tight">{SENSIBILIDAD_LABELS[s]}</div>
                    <div className="flex flex-wrap gap-1 mt-auto">
                      {partidos.map(p => (
                        <span key={p}
                              className="text-[9px] sm:text-[10px] px-1.5 sm:px-2 py-0.5 rounded-full"
                              style={{
                                background: `${main}1A`,
                                color: main,
                                border: `1px solid ${main}33`,
                              }}>
                          {p}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Comuna/Distrito step: cascade region → (comuna | distrito) */}
        {step === comunaStepIdx && (
          <div className="max-w-3xl mx-auto">
            <p className="text-center text-[10px] sm:text-xs tracking-[0.3em] text-gray-500 uppercase mb-3 sm:mb-4">
              Paso {comunaStepIdx + 1} de 3
            </p>
            <h2 className="text-center text-2xl sm:text-4xl font-bold text-white mb-2 leading-tight">
              {selectedRegion
                ? prettyRegion(selectedRegion)
                : mode === "autoridad" ? "¿En qué región ejerces?" : "¿En qué región?"}
            </h2>
            <p className="text-center text-sm sm:text-base text-gray-500 mb-5 sm:mb-8 px-2">
              {selectedRegion
                ? (usesDistrito ? "Selecciona el distrito en el que vas a competir" : "Selecciona tu comuna")
                : (usesDistrito
                    ? "Empieza por la región para ver sus distritos"
                    : "Empieza por la región o busca directamente por nombre de comuna")}
            </p>

            {/* Search input (oculto en flujo de distrito porque no tenemos search global) */}
            {!usesDistrito && (
              <div className="relative max-w-lg mx-auto mb-3 sm:mb-4">
                <input
                  ref={inputRef}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder={selectedRegion ? "Filtrar comunas..." : "Buscar comuna en todo Chile..."}
                  className="w-full px-4 sm:px-5 py-2.5 sm:py-3 rounded-xl text-white placeholder-gray-600 text-sm sm:text-base outline-none"
                  style={{ background: "#202026", border: "1px solid rgba(255,255,255,0.1)" }}
                />
                {loading && (
                  <div className="absolute right-4 top-1/2 -translate-y-1/2">
                    <div className="w-4 h-4 border-2 border-gray-600 rounded-full animate-spin"
                         style={{ borderTopColor: accentColor }} />
                  </div>
                )}
              </div>
            )}

            {/* Region breadcrumb when one is selected */}
            {selectedRegion && (
              <div className="text-center mb-4">
                <button onClick={() => { setSelectedRegion(null); setQuery(""); }}
                        className="text-xs text-gray-500 hover:text-white transition-colors">
                  ← Cambiar región
                </button>
              </div>
            )}

            {/* Global search results (when typing without a region selected) */}
            {!selectedRegion && globalSearchResults.length > 0 && (
              <div className="max-w-lg mx-auto rounded-2xl overflow-hidden"
                   style={{ border: "1px solid rgba(255,255,255,0.08)" }}>
                {globalSearchResults.map((r, i) => (
                  <button key={r.region + r.comuna} onClick={() => selectComuna(r.comuna)}
                          className="w-full px-5 py-3 text-left flex items-center justify-between hover:bg-white hover:bg-opacity-5 transition-colors"
                          style={{
                            background: "#202026",
                            borderBottom: i < globalSearchResults.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                          }}>
                    <span className="text-white text-sm">{prettyComuna(r.comuna)}</span>
                    <span className="text-gray-500 text-[10px] uppercase tracking-wider">
                      {prettyRegion(r.region)}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Region grid (initial state) */}
            {!selectedRegion && !query && (regionGroups.length > 0 || distritoGroups.length > 0) && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 sm:gap-3 mt-3 sm:mt-4">
                {(usesDistrito ? distritoGroups : regionGroups).map((g: any) => {
                  const items = usesDistrito ? g.distritos : g.comunas;
                  const itemLabel = usesDistrito ? "distrito" : "comuna";
                  return (
                    <button key={g.region} onClick={() => setSelectedRegion(g.region)}
                            className="px-3 py-2.5 sm:px-4 sm:py-3 rounded-lg sm:rounded-xl text-left transition-all duration-200 hover:scale-[1.02]"
                            style={{ background: "#202026", border: "1px solid rgba(255,255,255,0.08)" }}
                            onMouseEnter={e => {
                              (e.currentTarget as HTMLElement).style.borderColor = accentColor;
                            }}
                            onMouseLeave={e => {
                              (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.08)";
                            }}>
                      <div className="text-[13px] sm:text-sm font-semibold text-white leading-tight">
                        {prettyRegion(g.region)}
                      </div>
                      <div className="text-[10px] text-gray-500 mt-0.5">
                        {items.length} {itemLabel}{items.length !== 1 ? "s" : ""}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Comunas of selected region (modo comuna) */}
            {!usesDistrito && selectedRegion && filteredComunas.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[55vh] overflow-y-auto px-1">
                {filteredComunas.map(c => (
                  <button key={c} onClick={() => selectComuna(c)}
                          className="px-4 py-2.5 rounded-lg text-left text-white text-sm hover:bg-white hover:bg-opacity-5 transition-colors"
                          style={{ background: "#202026", border: "1px solid rgba(255,255,255,0.06)" }}>
                    {prettyComuna(c)}
                  </button>
                ))}
              </div>
            )}

            {/* Distritos of selected region (modo diputado) */}
            {usesDistrito && selectedRegion && (() => {
              const group = distritoGroups.find(g => g.region === selectedRegion);
              const distritos = group?.distritos || [];
              if (!distritos.length) return null;
              return (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[60vh] overflow-y-auto px-1">
                  {distritos.map(d => {
                    const procs = d.comunas.filter(c => c.procesada).length;
                    return (
                      <button key={d.distrito_id} onClick={() => selectDistrito(d)}
                              className="p-4 rounded-xl text-left transition-all duration-200 hover:scale-[1.02] flex flex-col"
                              style={{ background: "#202026", border: "1px solid rgba(255,255,255,0.08)" }}
                              onMouseEnter={e => {
                                (e.currentTarget as HTMLElement).style.borderColor = accentColor;
                                (e.currentTarget as HTMLElement).style.boxShadow = `0 0 24px ${accentColor}22`;
                              }}
                              onMouseLeave={e => {
                                (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.08)";
                                (e.currentTarget as HTMLElement).style.boxShadow = "none";
                              }}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-base font-semibold text-white">
                            {d.distrito}
                          </div>
                          <div className="text-[10px] text-gray-500">
                            {procs}/{d.comunas.length} con datos
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {d.comunas.map(c => (
                            <span key={c.comuna}
                                  className="text-[10px] px-2 py-0.5 rounded-full"
                                  style={{
                                    background: c.procesada ? `${accentColor}1A` : "rgba(255,255,255,0.04)",
                                    color: c.procesada ? accentColor : "#666",
                                    border: `1px solid ${c.procesada ? accentColor + "33" : "rgba(255,255,255,0.06)"}`,
                                  }}>
                              {prettyComuna(c.comuna)}
                            </span>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
              );
            })()}

            {/* Error state */}
            {loadError && !loading && (
              <div className="max-w-lg mx-auto mt-6 px-4 py-3 rounded-xl text-sm text-center"
                   style={{
                     background: "rgba(192,57,43,0.08)",
                     border: "1px solid rgba(192,57,43,0.3)",
                     color: "#E74C3C",
                   }}>
                {loadError}
              </div>
            )}

            {/* Empty state */}
            {!loadError && ((selectedRegion && filteredComunas.length === 0) ||
              (!selectedRegion && query && globalSearchResults.length === 0)) && !loading && (
              <p className="text-center text-gray-600 mt-6 text-sm">
                Sin resultados.
              </p>
            )}
          </div>
        )}

        {/* Step 2 (autoridad): Candidato selection */}
        {mode === "autoridad" && step === 2 && (
          <div className="max-w-2xl mx-auto">
            <p className="text-center text-[10px] sm:text-xs tracking-[0.3em] text-gray-500 uppercase mb-3 sm:mb-4">Paso 3 de 3</p>
            <h2 className="text-center text-2xl sm:text-4xl font-bold text-white mb-2 leading-tight">¿Quién eres?</h2>
            <p className="text-center text-sm sm:text-base text-gray-500 mb-5 sm:mb-6 px-2">
              {(() => {
                const lugar = usesDistrito
                  ? distritoNombre
                  : (comuna ? prettyComuna(comuna) : "");
                if (showAllCandidatos) {
                  return `Lista completa de candidatos a ${CARGO_LABELS[cargo!].toLowerCase()} en ${lugar}`;
                }
                if (cargo === "alcalde") return `Alcalde electo de ${lugar}`;
                return `${CARGO_LABELS[cargo!]}es electos en ${lugar}`;
              })()}
            </p>

            {/* Toggle electos / todos */}
            <div className="flex justify-center mb-4">
              <div className="inline-flex rounded-full p-1"
                   style={{ background: "#202026", border: "1px solid rgba(255,255,255,0.08)" }}>
                <button
                  onClick={() => setShowAllCandidatos(false)}
                  className="px-4 py-1.5 rounded-full text-xs font-medium transition-all"
                  style={{
                    background: !showAllCandidatos ? "rgba(41,128,185,0.2)" : "transparent",
                    color: !showAllCandidatos ? "#5DADE2" : "#888",
                  }}
                >
                  Soy autoridad
                </button>
                <button
                  onClick={() => setShowAllCandidatos(true)}
                  className="px-4 py-1.5 rounded-full text-xs font-medium transition-all"
                  style={{
                    background: showAllCandidatos ? "rgba(41,128,185,0.2)" : "transparent",
                    color: showAllCandidatos ? "#5DADE2" : "#888",
                  }}
                >
                  Fui candidato
                </button>
              </div>
            </div>

            <div className="relative mb-2">
              <input
                ref={inputRef}
                value={candidatoQuery}
                onChange={e => setCandidatoQuery(e.target.value)}
                placeholder="Busca por nombre o partido..."
                className="w-full px-5 py-4 rounded-2xl text-white placeholder-gray-600 text-lg outline-none"
                style={{ background: "#202026", border: "1px solid rgba(255,255,255,0.1)" }}
              />
              {loadingCandidatos && (
                <div className="absolute right-4 top-1/2 -translate-y-1/2">
                  <div className="w-4 h-4 border-2 border-gray-600 rounded-full animate-spin"
                       style={{ borderTopColor: accentColor }} />
                </div>
              )}
            </div>

            <div className="max-h-[50vh] overflow-y-auto rounded-2xl"
                 style={{ border: "1px solid rgba(255,255,255,0.08)" }}>
              {filteredCandidatos.length > 0 ? (
                filteredCandidatos.map((c, i) => (
                  <button key={c.candidato + i} onClick={() => selectCandidato(c)}
                          className="w-full px-5 py-3 text-left hover:bg-white hover:bg-opacity-5 transition-colors flex items-center justify-between"
                          style={{
                            background: "#202026",
                            borderBottom: i < filteredCandidatos.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                          }}>
                    <div>
                      <div className="text-white text-sm font-medium">
                        {c.candidato.split(" ").map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(" ")}
                      </div>
                      <div className="text-gray-500 text-xs mt-0.5">{c.partido}</div>
                    </div>
                    <div className="text-gray-400 text-xs">
                      {Math.round(c.votos_total).toLocaleString("es-CL")} votos
                    </div>
                  </button>
                ))
              ) : !loadingCandidatos && (
                <div className="px-5 py-8 text-center text-gray-600 text-sm" style={{ background: "#202026" }}>
                  {candidatoQuery
                    ? "No se encontraron resultados."
                    : "Cargando candidatos..."}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
