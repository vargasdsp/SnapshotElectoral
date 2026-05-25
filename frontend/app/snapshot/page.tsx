"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import {
  fetchSnapshot, fetchAutoridadSnapshot, fetchGeoJSON,
  fetchDistritoSnapshot, fetchDistritoGeoJSON, fetchAutoridadDistritoSnapshot,
  fetchCensus, fetchCensusManzanas,
} from "@/lib/api";
import {
  SnapshotResponse, ManzanaFeature, Sensibilidad, CensusData,
  SENSIBILIDAD_COLORS, SENSIBILIDAD_LABELS, CARGO_LABELS, Cargo,
} from "@/types/electoral";
import MapControls from "@/components/map/MapControls";
import MapLegend from "@/components/map/MapLegend";
import EmptySectorOverlay from "@/components/map/EmptySectorOverlay";
import SwingChart from "@/components/charts/SwingChart";
import CensusPanel from "@/components/census/CensusPanel";
import { swingColor } from "@/lib/colors";
import { partidoColor } from "@/lib/partidoColors";
import { ThemeToggle } from "@/components/ThemeToggle";

// Dynamic import — Leaflet must render client-side only
const ElectoralMap = dynamic(() => import("@/components/map/ElectoralMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center"
         style={{ background: "var(--bg-primary)" }}>
      <div className="text-gray-600 text-sm animate-pulse">Cargando mapa...</div>
    </div>
  ),
});

function SnapshotContent() {
  const router = useRouter();
  const params = useSearchParams();
  const comuna      = params.get("comuna") || "";
  const cargo       = params.get("cargo") as Cargo || "concejal";
  const mode        = params.get("mode") === "autoridad" ? "autoridad" : "candidato";
  const candidato   = params.get("candidato") || "";
  const sensibilidadParam = params.get("sensibilidad") as Sensibilidad | null;
  const partidoParam     = params.get("partido") || undefined;
  const distritoIdParam = params.get("distrito_id");
  const distritoId  = distritoIdParam ? parseInt(distritoIdParam, 10) : null;
  const isDistrito  = distritoId !== null && !isNaN(distritoId);

  const [resolvedSens, setResolvedSens] = useState<Sensibilidad>(
    sensibilidadParam || "centroizquierda"
  );
  const sensibilidad = resolvedSens;

  const [snapshot, setSnapshot]     = useState<SnapshotResponse | null>(null);
  const [geojson, setGeojson]       = useState<GeoJSON.FeatureCollection | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<"choropleth" | "heatmap" | "winner" | "debilidades">("choropleth");
  const [hoveredMz, setHoveredMz]   = useState<ManzanaFeature | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab]   = useState<"electoral" | "censo">("electoral");
  const [censusData, setCensusData]   = useState<CensusData | null>(null);
  const [censusLoading, setCensusLoading] = useState(false);
  const [activeCensusVar, setActiveCensusVar] = useState<{ variable: string; label: string; data: Record<string, number> } | null>(null);
  const [censusVarLoading, setCensusVarLoading] = useState(false);

  useEffect(() => {
    if (!cargo) return;
    if (!isDistrito && !comuna) return;
    if (isDistrito && distritoId === null) return;
    setLoading(true);
    setError(null);

    // Flujo distrito: autoridad vs candidato usan endpoints distintos
    const snapshotPromise = isDistrito
      ? (mode === "autoridad" && candidato
          ? fetchAutoridadDistritoSnapshot(distritoId!, candidato, comuna || undefined)
          : fetchDistritoSnapshot(distritoId!, sensibilidad, comuna || undefined))
      : (mode === "autoridad" && candidato
          ? fetchAutoridadSnapshot(comuna, cargo, candidato)
          : fetchSnapshot(comuna, cargo, sensibilidad, partidoParam));

    const geoPromise = isDistrito
      ? fetchDistritoGeoJSON(distritoId!, comuna || undefined)
      : fetchGeoJSON(comuna);

    Promise.all([snapshotPromise, geoPromise])
      .then(([snap, geo]) => {
        setSnapshot(snap as SnapshotResponse);
        setGeojson(geo);
        // Autoridad mode: backend infers sensibilidad from partido
        if (mode === "autoridad" && (snap as SnapshotResponse).sensibilidad) {
          setResolvedSens((snap as SnapshotResponse).sensibilidad);
        }
      })
      .catch(err => setError(err.message || "Error cargando datos"))
      .finally(() => setLoading(false));
  }, [comuna, cargo, sensibilidad, mode, candidato, isDistrito, distritoId, partidoParam]);

  // Load census when tab is selected (only for single-comuna views)
  useEffect(() => {
    const target = snapshot?.comuna_filter || (isDistrito ? null : comuna);
    if (sidebarTab !== "censo" || !target) return;
    if (censusData?.comuna === target.toUpperCase()) return;
    setCensusLoading(true);
    fetchCensus(target)
      .then(d => setCensusData(d))
      .catch(() => setCensusData(null))
      .finally(() => setCensusLoading(false));
  }, [sidebarTab, comuna, snapshot?.comuna_filter, isDistrito, censusData]);

  const handleCensusVarClick = useCallback((variable: string, label: string) => {
    if (!variable) { setActiveCensusVar(null); return; }
    const target = snapshot?.comuna_filter || (isDistrito ? null : comuna);
    if (!target) return;
    setCensusVarLoading(true);
    fetchCensusManzanas(target, variable)
      .then(data => setActiveCensusVar({ variable, label, data }))
      .catch(() => setActiveCensusVar(null))
      .finally(() => setCensusVarLoading(false));
  }, [comuna, snapshot?.comuna_filter, isDistrito]);

  const computedLayer = activeCensusVar
    ? ("censo" as const)
    : activeLayer;

  const handleLayerChange = useCallback((layer: typeof activeLayer) => {
    setActiveLayer(layer);
    setActiveCensusVar(null);
  }, []);

  const handleManzanaHover = useCallback((mz: ManzanaFeature | null) => {
    setHoveredMz(mz);
  }, []);

  const { main: colorMain } = SENSIBILIDAD_COLORS[sensibilidad];
  const stats = snapshot?.stats;

  return (
    <div className="relative w-screen h-screen overflow-hidden flex flex-col"
         style={{ background: "var(--bg-primary)" }}>

      {/* Top bar */}
      <div className="relative z-30 flex items-center justify-between px-5 py-3 glass"
           style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>

        <div className="flex items-center gap-4">
          <button onClick={() => router.push("/")}
                  className="text-gray-500 hover:text-gray-300 text-sm transition-colors">
            ← Inicio
          </button>
          <div className="w-px h-4 bg-gray-800" />
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: colorMain }} />
            {isDistrito && mode === "autoridad" && candidato ? (
              <>
                <span className="text-white font-semibold text-sm">
                  {candidato.split(" ").map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(" ")}
                </span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-400 text-sm">{CARGO_LABELS[cargo]}</span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-400 text-sm">
                  {snapshot?.distrito || `Distrito ${distritoId}`}
                </span>
                {snapshot?.comunas && snapshot.comunas.length > 0 && (
                  <>
                    <span className="text-gray-600">·</span>
                    <select
                      value={comuna || ""}
                      onChange={(e) => {
                        const p = new URLSearchParams({
                          cargo, candidato,
                          distrito_id: String(distritoId),
                          mode: "autoridad",
                        });
                        if (e.target.value) p.set("comuna", e.target.value);
                        router.push(`/snapshot?${p}`);
                      }}
                      className="text-xs bg-transparent border border-gray-700 rounded-lg px-2 py-1 text-gray-300 outline-none cursor-pointer hover:border-gray-500"
                      style={{ background: "rgba(255,255,255,0.02)" }}
                    >
                      <option value="">Distrito completo</option>
                      {snapshot.comunas.map((c) => {
                        const enabled = !snapshot.comunas_procesadas
                          || snapshot.comunas_procesadas.includes(c);
                        return (
                          <option key={c} value={c} disabled={!enabled}
                                  style={{ background: "var(--bg-card)" }}>
                            {c.charAt(0) + c.slice(1).toLowerCase()}
                            {!enabled ? " (sin datos)" : ""}
                          </option>
                        );
                      })}
                    </select>
                  </>
                )}
              </>
            ) : isDistrito ? (
              <>
                <span className="text-white font-semibold text-sm">
                  {snapshot?.distrito || `Distrito ${distritoId}`}
                </span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-400 text-sm">{CARGO_LABELS[cargo]}</span>
                <span className="text-gray-600">·</span>
                <span className="text-sm" style={{ color: colorMain }}>
                  {SENSIBILIDAD_LABELS[sensibilidad]}
                </span>
                {snapshot?.comunas && snapshot.comunas.length > 0 && (
                  <>
                    <span className="text-gray-600">·</span>
                    <select
                      value={comuna || ""}
                      onChange={(e) => {
                        const p = new URLSearchParams({
                          cargo,
                          sensibilidad,
                          distrito_id: String(distritoId),
                        });
                        if (e.target.value) p.set("comuna", e.target.value);
                        router.push(`/snapshot?${p}`);
                      }}
                      className="text-xs bg-transparent border border-gray-700 rounded-lg px-2 py-1 text-gray-300 outline-none cursor-pointer hover:border-gray-500"
                      style={{ background: "rgba(255,255,255,0.02)" }}
                    >
                      <option value="">Distrito completo</option>
                      {snapshot.comunas.map((c) => {
                        const enabled = !snapshot.comunas_procesadas
                          || snapshot.comunas_procesadas.includes(c);
                        return (
                          <option key={c} value={c} disabled={!enabled}
                                  style={{ background: "var(--bg-card)" }}>
                            {c.charAt(0) + c.slice(1).toLowerCase()}
                            {!enabled ? " (sin datos)" : ""}
                          </option>
                        );
                      })}
                    </select>
                  </>
                )}
              </>
            ) : mode === "autoridad" && candidato ? (
              <>
                <span className="text-white font-semibold text-sm">
                  {candidato.split(" ").map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(" ")}
                </span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-400 text-sm">{CARGO_LABELS[cargo]}</span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-400 text-sm">
                  {comuna.charAt(0) + comuna.slice(1).toLowerCase()}
                </span>
              </>
            ) : (
              <>
                <span className="text-white font-semibold text-sm">
                  {comuna.charAt(0) + comuna.slice(1).toLowerCase()}
                </span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-400 text-sm">{CARGO_LABELS[cargo]}</span>
                <span className="text-gray-600">·</span>
                <span className="text-sm" style={{ color: colorMain }}>
                  {SENSIBILIDAD_LABELS[sensibilidad]}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {stats && (
            <div className="hidden md:flex items-center gap-4 text-sm">
              <div className="text-center">
                <div className="text-white font-bold">{stats.voto_promedio_pct.toFixed(1)}%</div>
                <div className="text-gray-600 text-xs">Voto promedio</div>
              </div>
              <div className="w-px h-8 bg-gray-800" />
              <div className="text-center">
                <div className="text-white font-bold">{stats.locales_ganados}/{stats.locales_total}</div>
                <div className="text-gray-600 text-xs">Locales fuertes</div>
              </div>
            </div>
          )}
          {mode === "autoridad" && candidato && !isDistrito && (
            <button
              onClick={() => router.push(
                `/compare?comuna=${comuna}&cargo=${cargo}&a=${encodeURIComponent(candidato)}`
              )}
              className="text-xs px-3 py-2 rounded-lg text-gray-300 hover:text-white transition-colors"
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}
            >
              ⇆ Comparar
            </button>
          )}
          <MapControls activeLayer={activeLayer} onChange={handleLayerChange} />
          <ThemeToggle />
          {censusVarLoading && (
            <div className="text-xs text-gray-500 animate-pulse">Cargando mapa censal…</div>
          )}
        </div>
      </div>

      {/* Main: map + sidebar */}
      <div className="relative flex-1 flex overflow-hidden">

        {/* Map */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 z-20 flex items-center justify-center"
                 style={{ background: "var(--bg-primary)" }}>
              <div className="flex flex-col items-center gap-4">
                <div className="w-8 h-8 border-2 border-gray-800 rounded-full"
                     style={{ borderTopColor: colorMain, animation: "spin 0.8s linear infinite" }} />
                <p className="text-gray-500 text-sm">Analizando territorio...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 z-20 flex items-center justify-center">
              <div className="glass rounded-2xl p-8 max-w-sm text-center">
                <p className="text-red-400 font-semibold mb-2">Error al cargar datos</p>
                <p className="text-gray-500 text-sm mb-4">{error}</p>
                <button onClick={() => router.push("/")}
                        className="text-xs text-gray-400 hover:text-white transition-colors">
                  ← Volver al inicio
                </button>
              </div>
            </div>
          )}

          {!loading && !error && geojson && snapshot && (
            <ElectoralMap
              geojson={geojson}
              manzanas={snapshot.manzanas}
              sensibilidad={sensibilidad}
              activeLayer={computedLayer}
              onManzanaHover={handleManzanaHover}
              censusVarData={activeCensusVar?.data ?? null}
              censusVarLabel={activeCensusVar?.label}
            />
          )}

          {/* Empty sector overlay */}
          {!loading && !error && snapshot?.no_data && (
            <EmptySectorOverlay
              comuna={comuna}
              cargo={cargo}
              sensibilidad={sensibilidad}
              alternativas={snapshot.alternativas || []}
              proxyConcejales={snapshot.proxy_concejales || null}
            />
          )}

          {/* Proxy cargo banner — estimación por concejal cuando no hubo candidato del sector al cargo */}
          {!loading && !error && !snapshot?.no_data && snapshot?.proxy_cargo && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] pointer-events-none animate-fade-in">
              <div className="glass rounded-xl px-4 py-2 flex items-center gap-2 text-sm"
                   style={{ borderColor: SENSIBILIDAD_COLORS[sensibilidad]?.main }}>
                <div className="w-2 h-2 rounded-full flex-shrink-0 opacity-60"
                     style={{ background: SENSIBILIDAD_COLORS[sensibilidad]?.main }} />
                <span className="text-gray-300">Estimación territorial ·</span>
                <span className="font-semibold text-white">
                  datos de {snapshot.proxy_cargo}
                </span>
                <span className="text-gray-400 text-xs">
                  (no hubo candidato de {SENSIBILIDAD_LABELS[sensibilidad]?.toLowerCase()} a {CARGO_LABELS[cargo]?.toLowerCase()})
                </span>
              </div>
            </div>
          )}

          {/* Proxy sensibilidad banner — se muestra cuando se usó un sector adyacente */}
          {!loading && !error && !snapshot?.no_data && snapshot?.proxy_sensibilidad && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] pointer-events-none animate-fade-in">
              <div className="glass rounded-xl px-4 py-2 flex items-center gap-2 text-sm"
                   style={{ borderColor: SENSIBILIDAD_COLORS[snapshot.proxy_sensibilidad as Sensibilidad]?.main || "#888" }}>
                <div className="w-2 h-2 rounded-full flex-shrink-0"
                     style={{ background: SENSIBILIDAD_COLORS[snapshot.proxy_sensibilidad as Sensibilidad]?.main || "#888" }} />
                <span className="text-gray-300">
                  Proxy territorial:
                </span>
                <span className="font-semibold text-white">
                  {SENSIBILIDAD_LABELS[snapshot.proxy_sensibilidad as Sensibilidad] || snapshot.proxy_sensibilidad}
                </span>
                <span className="text-gray-400 text-xs">
                  (no hubo candidatos de {SENSIBILIDAD_LABELS[sensibilidad]?.toLowerCase()} a {CARGO_LABELS[cargo]?.toLowerCase()})
                </span>
              </div>
            </div>
          )}

          {/* Census variable active banner */}
          {activeCensusVar && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] pointer-events-auto animate-fade-in">
              <div className="glass rounded-xl px-4 py-2 flex items-center gap-2 text-sm"
                   style={{ borderColor: "rgba(243,156,18,0.4)" }}>
                <span style={{ color: "#F39C12" }}>◉</span>
                <span className="text-gray-300">Mapa censal:</span>
                <span className="font-semibold text-white">{activeCensusVar.label}</span>
                <button
                  onClick={() => setActiveCensusVar(null)}
                  className="ml-1 text-gray-500 hover:text-white transition-colors text-xs"
                >✕</button>
              </div>
            </div>
          )}

          {/* Map overlays — z-[1000] queda sobre los panes de Leaflet (400-800)
              para que la leyenda no se esconda cuando se hace zoom in. */}
          <div className="absolute bottom-6 left-4 z-[1000] pointer-events-auto">
            <MapLegend sensibilidad={sensibilidad} />
          </div>

          {/* Sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="absolute top-4 right-4 z-[1000] glass rounded-xl w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white transition-colors"
          >
            {sidebarOpen ? "›" : "‹"}
          </button>

          {/* Hover tooltip (manzana info) */}
          {hoveredMz && (
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] glass rounded-xl px-4 py-2 text-center pointer-events-none animate-fade-in">
              <span className="text-white font-bold text-lg">{hoveredMz.voto_pct.toFixed(1)}%</span>
              <span className="text-gray-400 text-sm ml-2">{SENSIBILIDAD_LABELS[sensibilidad]}</span>
              <div className="text-gray-500 text-xs mt-0.5">{hoveredMz.local_votacion || ""}</div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        {sidebarOpen && (
          <div className="relative z-20 w-80 flex flex-col glass overflow-y-auto animate-slide-up"
               style={{ borderLeft: "1px solid rgba(255,255,255,0.06)" }}>

            {/* Sidebar tab switcher */}
            {!loading && !error && stats && (
              <div className="flex border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                {(["electoral", "censo"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setSidebarTab(tab)}
                    className="flex-1 py-2.5 text-xs font-medium transition-all"
                    style={{
                      color: sidebarTab === tab ? "#fff" : "#666",
                      borderBottom: sidebarTab === tab ? `2px solid ${colorMain}` : "2px solid transparent",
                      background: "transparent",
                    }}
                  >
                    {tab === "electoral" ? "Electoral" : "Censo 2024"}
                  </button>
                ))}
              </div>
            )}

          {loading ? (
              <SidebarSkeleton />
            ) : error || !stats ? null : sidebarTab === "censo" ? (
              censusLoading ? (
                <SidebarSkeleton />
              ) : censusData ? (
                <CensusPanel
                  data={censusData}
                  colorMain={colorMain}
                  activeVar={activeCensusVar?.variable ?? null}
                  onVarClick={handleCensusVarClick}
                />
              ) : (
                <div className="p-6 text-center text-gray-600 text-sm">
                  {isDistrito && !snapshot?.comuna_filter
                    ? "Selecciona una comuna del distrito para ver datos censales"
                    : "Sin datos censales para esta unidad"}
                </div>
              )
            ) : (
              <>
                {/* Stats header */}
                <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{ background: colorMain }} />
                    <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                      % votos válidos del sector
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-white mt-2">
                    {stats.voto_promedio_pct.toFixed(1)}
                    <span className="text-lg text-gray-500">%</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1 leading-relaxed">
                    {mode === "autoridad"
                      ? <>
                          Esta candidatura obtuvo en promedio{" "}
                          <span className="text-gray-300 font-medium">{stats.voto_promedio_pct.toFixed(1)}%</span>
                          {" "}del voto válido, equivalente a{" "}
                          <span className="text-gray-300 font-medium">≈ {Math.round(stats.total_votos).toLocaleString("es-CL")} votos</span>
                        </>
                      : <>
                          Las candidaturas de este sector obtienen en promedio{" "}
                          <span className="text-gray-300 font-medium">{stats.voto_promedio_pct.toFixed(1)}%</span>
                          {" "}del voto válido, equivalente a{" "}
                          <span className="text-gray-300 font-medium">≈ {Math.round(stats.total_votos).toLocaleString("es-CL")} votos</span>
                        </>
                    }
                  </div>

                  {stats.swing !== null && (
                    <div className="flex items-center gap-1.5 mt-3">
                      <span className="text-sm font-semibold" style={{ color: swingColor(stats.swing) }}>
                        {stats.swing > 0 ? "+" : ""}{stats.swing.toFixed(1)}pp
                      </span>
                      <span className="text-xs text-gray-500">
                        {mode === "autoridad" ? "marca personal vs. sector" : "vs. presidencial 2024"}
                      </span>
                    </div>
                  )}

                  {/* Techo electoral */}
                  {stats.techo_concejal_pct != null && mode !== "autoridad" && cargo !== "concejal" && (
                    <div className="mt-4 pt-3 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500">Techo electoral</span>
                        <span className="text-xs text-gray-400 font-semibold">
                          {stats.techo_concejal_pct.toFixed(1)}%
                          <span className="text-gray-600 font-normal ml-1">concejal</span>
                        </span>
                      </div>
                      <div className="relative h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
                        {/* Techo bar */}
                        <div className="absolute top-0 left-0 h-full rounded-full opacity-30"
                             style={{ width: `${Math.min(stats.techo_concejal_pct * 2, 100)}%`, background: colorMain }} />
                        {/* Actual bar */}
                        <div className="absolute top-0 left-0 h-full rounded-full"
                             style={{ width: `${Math.min(stats.voto_promedio_pct * 2, 100)}%`, background: colorMain }} />
                      </div>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-[10px] text-gray-600">
                          {stats.voto_promedio_pct < stats.techo_concejal_pct
                            ? `${(stats.techo_concejal_pct - stats.voto_promedio_pct).toFixed(1)}pp por crecer`
                            : `${(stats.voto_promedio_pct - stats.techo_concejal_pct).toFixed(1)}pp sobre la base`}
                        </span>
                        <span className="text-[10px]" style={{
                          color: stats.voto_promedio_pct >= stats.techo_concejal_pct ? "#27AE60" : "#888"
                        }}>
                          {stats.voto_promedio_pct >= stats.techo_concejal_pct ? "▲ Sobre la base" : "▼ Bajo la base"}
                        </span>
                      </div>
                    </div>
                  )}
                </div>



                {/* Partidos más competitivos del sector */}
                {stats.top_partidos && stats.top_partidos.length > 0 && (
                  <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-1">
                      Partidos más competitivos
                    </p>
                    <p className="text-[10px] text-gray-600 mb-3">Clic para ver su desempeño territorial</p>
                    <div className="flex flex-col gap-2">
                      {stats.top_partidos.slice(0, 5).map((pt, i) => (
                        <button
                          key={i}
                          onClick={() => {
                            const p = new URLSearchParams({ cargo, sensibilidad, partido: pt.partido, mode: "candidato" });
                            if (isDistrito) p.set("distrito_id", String(distritoId));
                            else p.set("comuna", comuna);
                            router.push(`/snapshot?${p}`);
                          }}
                          className="flex items-center gap-2 text-xs w-full text-left px-2 py-1.5 -mx-2 rounded-md hover:bg-white hover:bg-opacity-5 transition-colors"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="text-gray-300 truncate">{pt.partido || "—"}</span>
                              <span className="text-gray-400 font-semibold ml-2 flex-shrink-0">{pt.pct.toFixed(1)}%</span>
                            </div>
                            <div className="h-1 rounded-full overflow-hidden" style={{ background: "var(--overlay-soft)" }}>
                              <div className="h-full rounded-full" style={{
                                width: `${Math.min(pt.pct * 2, 100)}%`,
                                background: i === 0 ? colorMain : "rgba(255,255,255,0.25)"
                              }} />
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Subject summary: which candidatures are being visualized */}
                {mode !== "autoridad" && stats.top_candidatos.length > 0 && (
                  <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-1">
                      {cargo === "alcalde"
                        ? `Candidatura${stats.top_candidatos.length > 1 ? "s" : ""} analizada${stats.top_candidatos.length > 1 ? "s" : ""}`
                        : `Visualizando ${stats.top_candidatos.length} candidato${stats.top_candidatos.length > 1 ? "s" : ""}`}
                    </p>
                    <p className="text-[10px] text-gray-600 mb-3">Clic para ver desempeño individual</p>
                    <div className="flex flex-col gap-0.5">
                      {stats.top_candidatos.slice(0, cargo === "alcalde" ? 3 : 8).map((c: any, i) => {
                        const candName = c.candidato || "";
                        const effectiveCargo = snapshot?.proxy_cargo || cargo;
                        return (
                          <button
                            key={i}
                            onClick={() => {
                              const p = new URLSearchParams({ cargo: effectiveCargo, candidato: candName, mode: "autoridad" });
                              if (isDistrito) p.set("distrito_id", String(distritoId));
                              else p.set("comuna", comuna);
                              router.push(`/snapshot?${p}`);
                            }}
                            className="flex items-center gap-2 text-xs px-2 py-1.5 -mx-2 rounded-md hover:bg-white hover:bg-opacity-5 transition-colors text-left"
                          >
                            <span className="w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ background: partidoColor(c.partido) }} />
                            <span className="text-white truncate flex-1 mr-2 group-hover:underline">
                              {candName.split(" ").map((w: string) =>
                                w ? w.charAt(0) + w.slice(1).toLowerCase() : w).join(" ")}
                            </span>
                            <span className="text-gray-500 text-[10px] uppercase tracking-wider">
                              {(c.partido || "").length > 18 ? (c.partido || "").slice(0, 18) + "…" : c.partido}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Top candidates OR top locales (autoridad mode) */}
                {stats.top_candidatos.length > 0 && (
                  <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
                      {mode === "autoridad" ? "Tus mejores locales" : "Ranking interno"}
                    </p>
                    {mode === "autoridad" ? (
                      <div className="flex flex-col gap-2">
                        {stats.top_candidatos.slice(0, 5).map((loc: any, i) => (
                          <div key={i} className="flex items-center justify-between text-xs">
                            <span className="text-gray-300 truncate flex-1 mr-2">
                              {loc.local || loc.candidato || "—"}
                            </span>
                            <span className="font-semibold" style={{ color: colorMain }}>
                              {(loc.pct ?? 0).toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <SwingChart
                        topCandidatos={stats.top_candidatos}
                        sensibilidadColor={colorMain}
                        onCandidatoClick={(name) => {
                          if (!name) return;
                          const effectiveCargo = snapshot?.proxy_cargo || cargo;
                          const p = new URLSearchParams({ cargo: effectiveCargo, candidato: name, mode: "autoridad" });
                          if (isDistrito) p.set("distrito_id", String(distritoId));
                          else p.set("comuna", comuna);
                          router.push(`/snapshot?${p}`);
                        }}
                      />
                    )}
                  </div>
                )}

                {/* Insights político-municipales (solo alcalde, modo autoridad) */}
                {mode === "autoridad" && snapshot?.insights && (
                  <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-1 h-4 rounded" style={{ background: colorMain }} />
                      <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                        Trayectoria política
                      </p>
                    </div>
                    <div className="flex flex-col gap-2 text-xs">
                      {snapshot.insights.estado && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Estado</span>
                          <span className="text-gray-200 font-medium">
                            {snapshot.insights.estado.replace("-", " ").toLowerCase()
                              .replace(/^\w/, c => c.toUpperCase())}
                          </span>
                        </div>
                      )}
                      {snapshot.insights.pacto && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Pacto 2024</span>
                          <span className="text-gray-200 font-medium text-right max-w-[60%]">
                            {snapshot.insights.pacto}
                          </span>
                        </div>
                      )}
                      {snapshot.insights.militancia && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Militancia</span>
                          <span className="text-gray-200 font-medium text-right max-w-[60%]">
                            {snapshot.insights.militancia}
                          </span>
                        </div>
                      )}
                      {snapshot.insights.cupo && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Cupo del pacto</span>
                          <span className="text-gray-200 font-medium text-right max-w-[60%]">
                            {snapshot.insights.cupo}
                          </span>
                        </div>
                      )}
                      {snapshot.insights.antigua_militancia && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Ex-militancia</span>
                          <span className="font-medium text-right max-w-[60%]"
                                style={{ color: colorMain }}>
                            {snapshot.insights.antigua_militancia}
                          </span>
                        </div>
                      )}
                      {snapshot.insights.bancada_achm &&
                        snapshot.insights.bancada_achm !== "#N/A" && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Bancada AChM</span>
                          <span className="text-gray-300 font-medium text-right max-w-[60%]">
                            {snapshot.insights.bancada_achm}
                          </span>
                        </div>
                      )}
                    </div>
                    {snapshot.insights.es_independiente_reclasificado && (
                      <p className="text-[10px] text-gray-500 mt-3 leading-relaxed italic">
                        Reclasificado a {SENSIBILIDAD_LABELS[snapshot.insights.sensibilidad_real]} usando
                        {snapshot.insights.antigua_militancia
                          ? " ex-militancia."
                          : " cupo del pacto."}
                      </p>
                    )}
                  </div>
                )}

                {/* Narrative */}
                {snapshot?.narrative && (
                  <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-1 h-4 rounded" style={{ background: colorMain }} />
                      <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                        Lectura territorial
                      </p>
                    </div>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {snapshot.narrative}
                    </p>
                  </div>
                )}

                {/* Total votes */}
                <div className="p-5">
                  <div className="flex items-center justify-between text-xs text-gray-600">
                    <span>Total votos del sector</span>
                    <span className="text-gray-400 font-medium">
                      {Math.round(stats.total_votos).toLocaleString("es-CL")}
                    </span>
                  </div>
                  {stats.pres_historico_pct !== null && (
                    <div className="flex items-center justify-between text-xs text-gray-600 mt-2">
                      <span>Referencia presidencial</span>
                      <span className="text-gray-400 font-medium">
                        {stats.pres_historico_pct.toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
      `}</style>
    </div>
  );
}

function SidebarSkeleton() {
  return (
    <div className="p-5 flex flex-col gap-4">
      {[80, 120, 60, 200, 100].map((h, i) => (
        <div key={i} className="animate-shimmer rounded-xl bg-white bg-opacity-5"
             style={{ height: h }} />
      ))}
    </div>
  );
}

export default function SnapshotPage() {
  return (
    <Suspense fallback={
      <div className="w-screen h-screen flex items-center justify-center"
           style={{ background: "var(--bg-primary)" }}>
        <div className="text-gray-600 animate-pulse">Cargando...</div>
      </div>
    }>
      <SnapshotContent />
    </Suspense>
  );
}
