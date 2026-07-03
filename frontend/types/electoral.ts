export type Cargo = "concejal" | "core" | "alcalde" | "diputado";
export type Sensibilidad =
  | "izquierda"
  | "centroizquierda"
  | "centro"
  | "centroderecha"
  | "derecha"
  | "independiente";

export interface ManzanaFeature {
  id_manzana: string;
  voto_pct: number;
  voto_abs: number;
  total_votos: number;
  local_votacion: string;
  local_lat: number;
  local_lon: number;
  dist_local_m: number;
  is_fortaleza: boolean;
}

export interface SnapshotStats {
  voto_promedio_pct: number;
  total_votos: number;
  votos_sector_total: number;
  manzanas_total: number;
  manzanas_fortaleza: number;
  manzanas_debilidad: number;
  locales_ganados: number;
  locales_total: number;
  top_candidatos: Array<{ candidato: string; partido: string; votos: number; pct?: number; local?: string }>;
  top_partidos: Array<{ partido: string; votos: number; pct: number }>;
  top_pactos?: Array<{ pacto: string; votos: number; pct: number }>;
  pres_historico_pct: number | null;
  swing: number | null;
  techo_concejal_pct?: number | null;
}

export interface AlternativaSector {
  sensibilidad: Sensibilidad;
  candidatos: number;
  voto_promedio_pct: number;
}

export interface ConcejalProxy {
  voto_promedio_pct: number;
  manzanas_con_datos: number;
  candidatos: number;
}

export interface AlcaldeInsight {
  nombre: string;
  pacto: string;
  estado: string;            // REELECTO / NUEVO / NUEVO-RETORNO
  bancada_achm: string;
  militancia: string;
  cupo: string;
  antigua_militancia: string;
  sensibilidad_real: Sensibilidad;
  es_independiente_reclasificado: boolean;
}

export interface SnapshotResponse {
  comuna?: string;
  cargo: string;
  sensibilidad: Sensibilidad;
  manzanas: ManzanaFeature[];
  stats: SnapshotStats;
  narrative: string;
  no_data?: boolean;
  proxy_sensibilidad?: Sensibilidad | null;
  proxy_cargo?: string | null;
  alternativas?: AlternativaSector[];
  proxy_concejales?: ConcejalProxy | null;
  insights?: AlcaldeInsight | null;
  // Solo presentes cuando se viene del flujo de distrito (cargo=diputado)
  distrito_id?: number;
  distrito?: string;
  comuna_filter?: string | null;
  comunas?: string[];                  // todas las comunas del distrito
  comunas_procesadas?: string[];       // las que tienen votos cargados
}

export type WizardMode = "candidato" | "autoridad";

export interface WizardState {
  mode: WizardMode;
  cargo: Cargo | null;
  sensibilidad: Sensibilidad | null;
  comuna: string | null;
  candidato: string | null;
  distritoId?: number | null;
  distritoNombre?: string | null;
}

export interface CandidatoItem {
  candidato: string;
  partido: string;
  votos_total: number;
}

export const CARGO_LABELS: Record<Cargo, string> = {
  concejal: "Concejal",
  core:     "Consejero Regional (CORE)",
  alcalde:  "Alcalde",
  diputado: "Diputado",
};

export const SENSIBILIDAD_LABELS: Record<Sensibilidad, string> = {
  izquierda:       "Izquierda",
  centroizquierda: "Centroizquierda",
  centro:          "Centro",
  centroderecha:   "Centroderecha",
  derecha:         "Derecha",
  independiente:   "Independiente",
};

// Partidos representativos por sensibilidad — siglas mostradas en el wizard
// para que el usuario sepa qué incluye cada bloque antes de elegir.
// Debe mantenerse consistente con SENSIBILIDAD_PARTIDOS en backend/services/query.py.
export const SENSIBILIDAD_PARTIDOS_DISPLAY: Record<Sensibilidad, string[]> = {
  izquierda:       ["PC", "FA", "CS", "RD", "AH", "FRVS"],
  centroizquierda: ["PS", "PPD", "PR", "PRSD", "DC"],
  centro:          ["PL", "Amarillos"],
  centroderecha:   ["Evópoli", "Demócratas"],
  derecha:         ["UDI", "RN", "Republicanos", "PNL"],
  independiente:   ["IND fuera de pacto", "PDG"],
};

export interface CensusData {
  comuna: string;
  total_personas: number;
  total_viviendas: number;
  total_hogares: number;
  demografia: {
    edad_18_24_pct: number;
    edad_25_44_pct: number;
    edad_45_59_pct: number;
    edad_60_mas_pct: number;
    mujeres_pct: number;
    inmigrantes_pct: number;
    pueblos_orig_pct: number;
    discapacidad_pct: number;
  };
  educacion_clase: {
    prom_escolaridad: number;
    ed_superior_pct: number;
    analfabetismo_pct: number;
    clase_alta_media_pct: number;
    clase_trabajadora_pct: number;
  };
  empleo: {
    ocupados_pct: number;
    desocupados_pct: number;
  };
  vulnerabilidad: {
    hacinamiento_pct: number;
    deficit_cuant_pct: number;
    irrecuperables_pct: number;
    paredes_precarias_pct: number;
    piso_tierra_pct: number;
    indice_vulnerabilidad: number;
  };
  vivienda: {
    propietarios_pct: number;
    arrendatarios_pct: number;
  };
  servicios: {
    internet_pct: number;
    agua_potable_pct: number;
    sin_elect_pct: number;
    auto_pct: number;
    transporte_pub_pct: number;
  };
  hogares: {
    jefatura_mujer_pct: number;
    unipersonales_pct: number;
    con_adulto_mayor_pct: number;
    con_menores_pct: number;
  };
}

export const SENSIBILIDAD_COLORS: Record<Sensibilidad, { main: string; light: string; text: string }> = {
  izquierda:       { main: "#C0392B", light: "#FADBD8", text: "#922B21" },
  centroizquierda: { main: "#E74C3C", light: "#FDECEA", text: "#C0392B" },
  centro:          { main: "#8E44AD", light: "#F4ECF7", text: "#6C3483" },
  centroderecha:   { main: "#2980B9", light: "#EBF5FB", text: "#1A5276" },
  derecha:         { main: "#1A5276", light: "#D6EAF8", text: "#154360" },
  independiente:   { main: "#7F8C8D", light: "#F2F3F4", text: "#566573" },
};
