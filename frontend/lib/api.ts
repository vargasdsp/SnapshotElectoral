import { SnapshotResponse, CandidatoItem, CensusData } from "@/types/electoral";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchComunas(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/communes/`);
  if (!res.ok) throw new Error("Failed to fetch communes");
  const data = await res.json();
  return data.comunas as string[];
}

export interface RegionGroup { region: string; comunas: string[] }

export async function fetchComunasByRegion(): Promise<RegionGroup[]> {
  const res = await fetch(`${API_BASE}/api/communes/by-region`);
  if (!res.ok) throw new Error("Failed to fetch communes by region");
  const data = await res.json();
  return data.regiones as RegionGroup[];
}

export interface DistritoComuna { comuna: string; procesada: boolean }
export interface Distrito {
  distrito_id: number;
  distrito: string;
  comunas: DistritoComuna[];
}
export interface DistritoRegionGroup { region: string; distritos: Distrito[] }

export async function fetchDistritosByRegion(): Promise<DistritoRegionGroup[]> {
  const res = await fetch(`${API_BASE}/api/communes/distritos-by-region`);
  if (!res.ok) throw new Error("Failed to fetch distritos by region");
  const data = await res.json();
  return data.regiones as DistritoRegionGroup[];
}

export async function fetchDistritoSnapshot(
  distritoId: number,
  sensibilidad: string,
  comunaFilter?: string,
): Promise<any> {
  const params = new URLSearchParams({
    distrito_id: String(distritoId),
    sensibilidad,
  });
  if (comunaFilter) params.set("comuna", comunaFilter);
  const res = await fetch(`${API_BASE}/api/electoral/snapshot-distrito?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to fetch distrito snapshot");
  }
  return res.json();
}

export async function fetchCandidatosDistrito(
  distritoId: number,
  electosOnly: boolean = false,
): Promise<CandidatoItem[]> {
  const params = new URLSearchParams({ distrito_id: String(distritoId) });
  if (electosOnly) params.set("electos_only", "true");
  const res = await fetch(`${API_BASE}/api/electoral/candidatos-distrito?${params}`);
  if (!res.ok) throw new Error("Failed to fetch candidatos distrito");
  const data = await res.json();
  return data.candidatos as CandidatoItem[];
}

export async function fetchAutoridadDistritoSnapshot(
  distritoId: number,
  candidato: string,
  comunaFilter?: string,
): Promise<any> {
  const params = new URLSearchParams({
    distrito_id: String(distritoId),
    candidato,
  });
  if (comunaFilter) params.set("comuna", comunaFilter);
  const res = await fetch(`${API_BASE}/api/electoral/snapshot-autoridad-distrito?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to fetch autoridad distrito snapshot");
  }
  return res.json();
}

export async function fetchDistritoGeoJSON(
  distritoId: number,
  comunaFilter?: string,
): Promise<GeoJSON.FeatureCollection> {
  const url = comunaFilter
    ? `${API_BASE}/api/geo/distrito/${distritoId}?comuna=${encodeURIComponent(comunaFilter)}`
    : `${API_BASE}/api/geo/distrito/${distritoId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`No GeoJSON for distrito ${distritoId}`);
  return res.json();
}

export async function fetchSnapshot(
  comuna: string,
  cargo: string,
  sensibilidad: string,
  partido?: string,
  pacto?: string,
): Promise<SnapshotResponse> {
  const params = new URLSearchParams({ comuna, cargo, sensibilidad });
  if (partido) params.set("partido", partido);
  if (pacto) params.set("pacto", pacto);
  const res = await fetch(`${API_BASE}/api/electoral/snapshot?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to fetch snapshot");
  }
  return res.json();
}

export async function fetchCandidatos(
  comuna: string,
  cargo: string,
  electosOnly: boolean = false,
): Promise<CandidatoItem[]> {
  const params = new URLSearchParams({ comuna, cargo });
  if (electosOnly) params.set("electos_only", "true");
  const res = await fetch(`${API_BASE}/api/electoral/candidatos?${params}`);
  if (!res.ok) throw new Error("Failed to fetch candidatos");
  const data = await res.json();
  return data.candidatos as CandidatoItem[];
}

export async function fetchAutoridadSnapshot(
  comuna: string,
  cargo: string,
  candidato: string
): Promise<SnapshotResponse & { candidato: string; partido: string }> {
  const params = new URLSearchParams({ comuna, cargo, candidato });
  const res = await fetch(`${API_BASE}/api/electoral/snapshot-autoridad?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to fetch autoridad snapshot");
  }
  return res.json();
}

export async function fetchCompare(
  comuna: string,
  cargo: string,
  candidatoA: string,
  candidatoB: string
): Promise<{ a: SnapshotResponse; b: SnapshotResponse }> {
  const params = new URLSearchParams({
    comuna, cargo,
    candidato_a: candidatoA,
    candidato_b: candidatoB,
  });
  const res = await fetch(`${API_BASE}/api/electoral/compare?${params}`);
  if (!res.ok) throw new Error("Failed to fetch comparison");
  return res.json();
}

export async function fetchGeoJSON(comuna: string): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(`${API_BASE}/api/geo/${encodeURIComponent(comuna)}`);
  if (!res.ok) throw new Error(`No GeoJSON for ${comuna}`);
  return res.json();
}

export async function fetchCensus(comuna: string): Promise<CensusData> {
  const res = await fetch(`${API_BASE}/api/census/${encodeURIComponent(comuna)}`);
  if (!res.ok) throw new Error(`No census data for ${comuna}`);
  return res.json();
}

export async function fetchCensusManzanas(
  comuna: string,
  variable: string,
): Promise<Record<string, number>> {
  const res = await fetch(
    `${API_BASE}/api/census/manzanas/${encodeURIComponent(comuna)}?variable=${encodeURIComponent(variable)}`,
  );
  if (!res.ok) throw new Error(`No census manzana data for ${variable}`);
  const data = await res.json();
  return data.manzanas as Record<string, number>;
}
