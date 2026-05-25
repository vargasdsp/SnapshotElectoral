"""Census data aggregation service — reads manzanas_nacional.parquet."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import unicodedata
import pandas as pd
from .query import _ensure_remote

PARQUET_PATH = Path(__file__).parent.parent.parent / "manzanas_nacional.parquet"

def _ensure_census() -> bool:
    return _ensure_remote(PARQUET_PATH, "manzanas_nacional.parquet")

# Columns allowed for per-manzana map visualization
VALID_MAP_COLS: set[str] = {
    "n_per", "n_hombres", "n_mujeres",
    "n_edad_18_24", "n_edad_25_44", "n_edad_45_59", "n_edad_60_mas",
    "n_inmigrantes", "n_pueblos_orig", "n_discapacidad",
    "prom_escolaridad18",
    "n_cine_terciaria_maestria_doctorado", "n_analfabet",
    "n_ocupado", "n_desocupado", "n_fuera_fuerza_trabajo",
    "n_ciuo_1", "n_ciuo_2", "n_ciuo_3", "n_ciuo_4", "n_ciuo_5",
    "n_ciuo_7", "n_ciuo_8", "n_ciuo_9",
    "n_vp", "n_vp_ocupada",
    "n_viv_hacinadas", "n_deficit_cuantitativo", "n_viv_irrecuperables",
    "n_mat_paredes_precarios", "n_mat_piso_tierra",
    "n_tenencia_propia_pagada", "n_tenencia_arrendada_contrato",
    "n_hog", "n_internet", "n_fuente_agua_publica",
    "n_fuente_elect_no_tiene",
    "n_jefatura_mujer", "n_hog_unipersonales", "n_hog_60", "n_hog_menores",
    "n_transporte_auto", "n_transporte_publico",
}

CENSUS_COLS = [
    "COMUNA", "CUT",
    "n_per", "n_hombres", "n_mujeres",
    "n_edad_18_24", "n_edad_25_44", "n_edad_45_59", "n_edad_60_mas",
    "n_inmigrantes", "n_pueblos_orig", "n_discapacidad",
    "prom_escolaridad18",
    "n_cine_terciaria_maestria_doctorado", "n_analfabet",
    "n_ocupado", "n_desocupado", "n_fuera_fuerza_trabajo",
    # Clase social (CIUO)
    "n_ciuo_1", "n_ciuo_2", "n_ciuo_3", "n_ciuo_4", "n_ciuo_5",
    "n_ciuo_7", "n_ciuo_8", "n_ciuo_9",
    "n_vp", "n_vp_ocupada",
    "n_viv_hacinadas", "n_deficit_cuantitativo", "n_viv_irrecuperables",
    "n_mat_paredes_precarios", "n_mat_piso_tierra",
    "n_tenencia_propia_pagada", "n_tenencia_arrendada_contrato",
    "n_hog", "n_internet", "n_fuente_agua_publica",
    "n_fuente_elect_no_tiene",
    "n_jefatura_mujer", "n_hog_unipersonales", "n_hog_60", "n_hog_menores",
    "n_transporte_auto", "n_transporte_publico",
]


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").upper()


_COMUNA_MAP_CACHE: dict[str, str] = {}

def _build_comuna_map() -> dict[str, str]:
    """Maps normalized (accent-stripped) commune name → actual name stored in parquet."""
    global _COMUNA_MAP_CACHE
    if _COMUNA_MAP_CACHE:
        return _COMUNA_MAP_CACHE
    _ensure_census()
    if not PARQUET_PATH.exists():
        return {}
    df = pd.read_parquet(PARQUET_PATH, columns=["COMUNA"])
    _COMUNA_MAP_CACHE = {_strip_accents(name): name for name in df["COMUNA"].dropna().unique()}
    return _COMUNA_MAP_CACHE


def _resolve_comuna(comuna: str) -> str | None:
    return _build_comuna_map().get(_strip_accents(comuna.strip()))


def _load_parquet() -> pd.DataFrame:
    _ensure_census()
    if not PARQUET_PATH.exists():
        return pd.DataFrame()
    return pd.read_parquet(PARQUET_PATH, columns=CENSUS_COLS)


def get_census_manzanas(comuna: str, variable: str) -> dict[str, float] | None:
    """Return {id_manzana: raw_value} for a given variable, filtered to one commune.
    id_manzana matches the GeoJSON ID_MANZANA property (MANZENT column, formatted as float string).
    """
    if variable not in VALID_MAP_COLS:
        return None
    actual = _resolve_comuna(comuna)
    if actual is None:
        return None
    cols = ["MANZENT", "COMUNA", variable]
    try:
        _ensure_census()
        if not PARQUET_PATH.exists():
            return None
        df = pd.read_parquet(PARQUET_PATH, columns=cols)
    except Exception:
        return None
    sub = df[df["COMUNA"] == actual][["MANZENT", variable]]
    if sub.empty:
        return None
    sub = sub.dropna(subset=[variable])
    # Format key as "NNNNNNNNNNNNNN.0" to match GeoJSON ID_MANZANA
    keys = sub["MANZENT"].apply(lambda v: f"{float(v):.1f}" if pd.notna(v) else None)
    return {k: float(v) for k, v in zip(keys, sub[variable]) if k is not None}


def _pct(num: float, den: float) -> float:
    return round(float(num) / float(den) * 100, 1) if den > 0 else 0.0


def get_census_comuna(comuna: str) -> dict | None:
    actual = _resolve_comuna(comuna)
    if actual is None:
        return None
    df = _load_parquet()
    sub = df[df["COMUNA"] == actual]
    if sub.empty:
        return None

    total_per    = sub["n_per"].sum()
    total_vp_ocu = sub["n_vp_ocupada"].sum()
    total_hog    = sub["n_hog"].sum()
    fuerza_trab  = sub[["n_ocupado", "n_desocupado"]].sum().sum()

    # Escolaridad ponderada por n_per
    prom_esc = round(
        float((sub["prom_escolaridad18"] * sub["n_per"]).sum()) / max(total_per, 1), 1
    )

    # Clase alta/media profesional: directivos(1) + profesionales(2) + técnicos(3)
    clase_alta_media = sub[["n_ciuo_1", "n_ciuo_2", "n_ciuo_3"]].sum().sum()
    # Clase trabajadora: servicios(5) + oficios(7) + operadores(8) + no calificados(9)
    clase_trabajadora = sub[["n_ciuo_5", "n_ciuo_7", "n_ciuo_8", "n_ciuo_9"]].sum().sum()

    return {
        "comuna": _strip_accents(actual),
        "total_personas": int(total_per),
        "total_viviendas": int(sub["n_vp"].sum()),
        "total_hogares": int(total_hog),

        "demografia": {
            "edad_18_24_pct":   _pct(sub["n_edad_18_24"].sum(), total_per),
            "edad_25_44_pct":   _pct(sub["n_edad_25_44"].sum(), total_per),
            "edad_45_59_pct":   _pct(sub["n_edad_45_59"].sum(), total_per),
            "edad_60_mas_pct":  _pct(sub["n_edad_60_mas"].sum(), total_per),
            "mujeres_pct":      _pct(sub["n_mujeres"].sum(), total_per),
            "inmigrantes_pct":  _pct(sub["n_inmigrantes"].sum(), total_per),
            "pueblos_orig_pct": _pct(sub["n_pueblos_orig"].sum(), total_per),
            "discapacidad_pct": _pct(sub["n_discapacidad"].sum(), total_per),
        },

        "educacion_clase": {
            "prom_escolaridad":       prom_esc,
            "ed_superior_pct":        _pct(sub["n_cine_terciaria_maestria_doctorado"].sum(), total_per),
            "analfabetismo_pct":      _pct(sub["n_analfabet"].sum(), total_per),
            # Índice Brahmin Left: % profesionales/directivos/técnicos sobre ocupados
            "clase_alta_media_pct":   _pct(clase_alta_media, total_per),
            # Clase trabajadora precaria
            "clase_trabajadora_pct":  _pct(clase_trabajadora, total_per),
        },

        "empleo": {
            "ocupados_pct":    _pct(sub["n_ocupado"].sum(), fuerza_trab),
            "desocupados_pct": _pct(sub["n_desocupado"].sum(), fuerza_trab),
        },

        "vulnerabilidad": {
            "hacinamiento_pct":    _pct(sub["n_viv_hacinadas"].sum(), total_vp_ocu),
            "deficit_cuant_pct":   _pct(sub["n_deficit_cuantitativo"].sum(), total_vp_ocu),
            "irrecuperables_pct":  _pct(sub["n_viv_irrecuperables"].sum(), total_vp_ocu),
            "paredes_precarias_pct": _pct(sub["n_mat_paredes_precarios"].sum(), total_vp_ocu),
            "piso_tierra_pct":     _pct(sub["n_mat_piso_tierra"].sum(), total_vp_ocu),
            # Índice compuesto (promedio de los 3 principales)
            "indice_vulnerabilidad": round((
                _pct(sub["n_viv_hacinadas"].sum(), total_vp_ocu) +
                _pct(sub["n_viv_irrecuperables"].sum(), total_vp_ocu) +
                _pct(sub["n_deficit_cuantitativo"].sum(), total_vp_ocu)
            ) / 3, 1),
        },

        "vivienda": {
            "propietarios_pct":   _pct(sub["n_tenencia_propia_pagada"].sum(), total_vp_ocu),
            "arrendatarios_pct":  _pct(sub["n_tenencia_arrendada_contrato"].sum(), total_vp_ocu),
        },

        "servicios": {
            "internet_pct":       _pct(sub["n_internet"].sum(), total_hog),
            "agua_potable_pct":   _pct(sub["n_fuente_agua_publica"].sum(), total_vp_ocu),
            "sin_elect_pct":      _pct(sub["n_fuente_elect_no_tiene"].sum(), total_vp_ocu),
            "auto_pct":           _pct(sub["n_transporte_auto"].sum(), total_per),
            "transporte_pub_pct": _pct(sub["n_transporte_publico"].sum(), total_per),
        },

        "hogares": {
            "jefatura_mujer_pct":    _pct(sub["n_jefatura_mujer"].sum(), total_hog),
            "unipersonales_pct":     _pct(sub["n_hog_unipersonales"].sum(), total_hog),
            "con_adulto_mayor_pct":  _pct(sub["n_hog_60"].sum(), total_hog),
            "con_menores_pct":       _pct(sub["n_hog_menores"].sum(), total_hog),
        },
    }
