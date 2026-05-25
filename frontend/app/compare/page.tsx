"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { fetchCompare, fetchGeoJSON, fetchCandidatos } from "@/lib/api";
import {
  SnapshotResponse, Cargo, Sensibilidad,
  CandidatoItem, CARGO_LABELS, SENSIBILIDAD_COLORS, SENSIBILIDAD_LABELS,
} from "@/types/electoral";

const ElectoralMap = dynamic(() => import("@/components/map/ElectoralMap"), {
  ssr: false,
  loading: () => <div className="w-full h-full" style={{ background: "#0d1117" }} />,
});

function CompareContent() {
  const router = useRouter();
  const params = useSearchParams();
  const comuna       = params.get("comuna") || "";
  const cargo        = (params.get("cargo") as Cargo) || "concejal";
  const candidatoA   = params.get("a") || "";
  const candidatoB   = params.get("b") || "";

  const [snapA, setSnapA] = useState<SnapshotResponse | null>(null);
  const [snapB, setSnapB] = useState<SnapshotResponse | null>(null);
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [candidatos, setCandidatos] = useState<CandidatoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [picker, setPicker]   = useState<"a" | "b" | null>(null);
  const [query, setQuery]     = useState("");

  useEffect(() => {
    if (!comuna || !cargo) return;
    fetchCandidatos(comuna, cargo).then(setCandidatos).catch(() => {});
  }, [comuna, cargo]);

  useEffect(() => {
    if (!comuna || !cargo || !candidatoA || !candidatoB) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      fetchCompare(comuna, cargo, candidatoA, candidatoB),
      fetchGeoJSON(comuna),
    ])
      .then(([cmp, geo]) => {
        setSnapA(cmp.a);
        setSnapB(cmp.b);
        setGeojson(geo);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [comuna, cargo, candidatoA, candidatoB]);

  function selectCandidato(c: CandidatoItem) {
    const which = picker;
    setPicker(null);
    setQuery("");
    if (!which) return;
    const p = new URLSearchParams(params.toString());
    p.set(which, c.candidato);
    router.replace(`/compare?${p.toString()}`);
  }

  const filteredCandidatos = query
    ? candidatos.filter(c =>
        c.candidato.toUpperCase().includes(query.toUpperCase()) ||
        c.partido.toUpperCase().includes(query.toUpperCase())
      ).slice(0, 12)
    : candidatos.slice(0, 12);

  return (
    <div className="relative w-screen h-screen overflow-hidden flex flex-col"
         style={{ background: "#111114" }}>

      {/* Top bar */}
      <div className="relative z-30 flex items-center justify-between px-5 py-3 glass"
           style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-4">
          <button onClick={() => router.back()}
                  className="text-gray-500 hover:text-gray-300 text-sm transition-colors">
            ← Volver
          </button>
          <div className="w-px h-4 bg-gray-800" />
          <span className="text-xs tracking-[0.2em] text-gray-500 uppercase font-medium">
            Modo comparación · {CARGO_LABELS[cargo]} · {comuna.charAt(0) + comuna.slice(1).toLowerCase()}
          </span>
        </div>
      </div>

      {/* Split layout */}
      <div className="relative flex-1 grid grid-cols-2 gap-px overflow-hidden"
           style={{ background: "rgba(255,255,255,0.08)" }}>

        {/* Side A */}
        <CompareSide
          label="A"
          snapshot={snapA}
          geojson={geojson}
          loading={loading}
          onPick={() => setPicker("a")}
        />

        {/* Side B */}
        <CompareSide
          label="B"
          snapshot={snapB}
          geojson={geojson}
          loading={loading}
          onPick={() => setPicker("b")}
        />
      </div>

      {/* Bottom comparison strip */}
      {snapA && snapB && (
        <div className="relative z-20 glass px-6 py-3 grid grid-cols-3 gap-4 text-sm"
             style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <DiffRow label="Voto promedio" a={snapA.stats.voto_promedio_pct} b={snapB.stats.voto_promedio_pct} unit="%" />
          <DiffRow label="Fortalezas" a={snapA.stats.manzanas_fortaleza} b={snapB.stats.manzanas_fortaleza} unit=" mz" />
          <DiffRow label="Locales ganados" a={snapA.stats.locales_ganados} b={snapB.stats.locales_ganados} unit="" />
        </div>
      )}

      {error && (
        <div className="absolute inset-0 z-40 flex items-center justify-center pointer-events-none">
          <div className="glass rounded-2xl p-6 text-center pointer-events-auto">
            <p className="text-red-400 font-semibold">{error}</p>
          </div>
        </div>
      )}

      {/* Candidato picker modal */}
      {picker && (
        <div className="absolute inset-0 z-50 flex items-center justify-center"
             style={{ background: "rgba(10,10,15,0.85)", backdropFilter: "blur(8px)" }}
             onClick={() => setPicker(null)}>
          <div className="glass rounded-2xl w-full max-w-md p-5"
               onClick={e => e.stopPropagation()}>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">
              Seleccionar candidato {picker.toUpperCase()}
            </p>
            <input
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Buscar..."
              className="w-full px-4 py-3 rounded-xl text-white text-sm outline-none mb-3"
              style={{ background: "#111114", border: "1px solid rgba(255,255,255,0.1)" }}
            />
            <div className="max-h-80 overflow-y-auto flex flex-col gap-1">
              {filteredCandidatos.map((c, i) => (
                <button key={i} onClick={() => selectCandidato(c)}
                        className="text-left px-3 py-2 rounded-lg hover:bg-white hover:bg-opacity-5 transition-colors">
                  <div className="text-white text-sm">
                    {c.candidato.split(" ").map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(" ")}
                  </div>
                  <div className="text-gray-500 text-xs">{c.partido}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CompareSide({
  label, snapshot, geojson, loading, onPick,
}: {
  label: "A" | "B";
  snapshot: SnapshotResponse | null;
  geojson: GeoJSON.FeatureCollection | null;
  loading: boolean;
  onPick: () => void;
}) {
  const sens: Sensibilidad = snapshot?.sensibilidad as Sensibilidad || "independiente";
  const color = SENSIBILIDAD_COLORS[sens].main;
  const candidato = (snapshot as any)?.candidato as string | undefined;
  const partido   = (snapshot as any)?.partido   as string | undefined;

  return (
    <div className="relative flex flex-col overflow-hidden" style={{ background: "#111114" }}>

      {/* Header */}
      <div className="absolute top-3 left-3 right-3 z-20 flex items-center justify-between gap-2">
        <div className="glass rounded-xl px-3 py-2 flex items-center gap-2 flex-1 min-w-0">
          <div className="w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold"
               style={{ background: color, color: "#fff" }}>
            {label}
          </div>
          {candidato ? (
            <div className="flex-1 min-w-0">
              <div className="text-white text-sm font-semibold truncate">
                {candidato.split(" ").map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(" ")}
              </div>
              <div className="text-gray-500 text-xs">{partido} · {SENSIBILIDAD_LABELS[sens]}</div>
            </div>
          ) : (
            <div className="text-gray-500 text-sm">Sin selección</div>
          )}
          <button onClick={onPick}
                  className="text-xs px-2 py-1 rounded text-gray-400 hover:text-white hover:bg-white hover:bg-opacity-10 transition-colors">
            Cambiar
          </button>
        </div>
      </div>

      {/* Stats overlay */}
      {snapshot && (
        <div className="absolute top-16 left-3 z-20 glass rounded-xl px-3 py-2">
          <div className="text-3xl font-bold" style={{ color }}>
            {snapshot.stats.voto_promedio_pct.toFixed(1)}
            <span className="text-base text-gray-500">%</span>
          </div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
            voto promedio
          </div>
        </div>
      )}

      {/* Map */}
      {loading ? (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-gray-600 text-sm animate-pulse">Cargando...</div>
        </div>
      ) : snapshot && geojson ? (
        <ElectoralMap
          geojson={geojson}
          manzanas={snapshot.manzanas}
          sensibilidad={sens}
          activeLayer="choropleth"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <button onClick={onPick}
                  className="text-gray-500 hover:text-white text-sm transition-colors px-4 py-2 rounded-lg"
                  style={{ border: "1px dashed rgba(255,255,255,0.15)" }}>
            + Seleccionar candidato {label}
          </button>
        </div>
      )}
    </div>
  );
}

function DiffRow({ label, a, b, unit }: { label: string; a: number; b: number; unit: string }) {
  const diff = a - b;
  const winner = diff > 0 ? "A" : diff < 0 ? "B" : null;
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500 text-xs uppercase tracking-wider">{label}</span>
      <div className="flex items-center gap-3 text-sm">
        <span className={winner === "A" ? "text-white font-bold" : "text-gray-500"}>
          {typeof a === "number" ? a.toFixed(label.includes("Voto") ? 1 : 0) : "-"}{unit}
        </span>
        <span className="text-gray-700">vs</span>
        <span className={winner === "B" ? "text-white font-bold" : "text-gray-500"}>
          {typeof b === "number" ? b.toFixed(label.includes("Voto") ? 1 : 0) : "-"}{unit}
        </span>
        <span className="text-xs px-1.5 py-0.5 rounded"
              style={{
                background: winner === "A" ? "rgba(192,57,43,0.2)" : winner === "B" ? "rgba(41,128,185,0.2)" : "transparent",
                color: winner === "A" ? "#E74C3C" : winner === "B" ? "#5DADE2" : "#666",
              }}>
          Δ {Math.abs(diff).toFixed(label.includes("Voto") ? 1 : 0)}
        </span>
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="w-screen h-screen" style={{ background: "#111114" }} />}>
      <CompareContent />
    </Suspense>
  );
}
