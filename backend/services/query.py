"""
DuckDB query layer for pre-processed electoral Parquet files.
All heavy computation is done at preprocessing time; this layer only reads.
"""
from __future__ import annotations
import json
import os
import threading
import duckdb
import numpy as np
import pandas as pd
import requests as _req
from pathlib import Path
from functools import lru_cache
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "processed"

# Hugging Face lazy download — set HF_DATASET_REPO=owner/repo in env
_HF_REPO = os.environ.get("HF_DATASET_REPO", "")
_HF_BASE = "https://huggingface.co/datasets"
_dl_locks: dict[str, threading.Lock] = {}
_dl_mu = threading.Lock()


def _ensure_remote(path: Path, hf_relpath: str) -> bool:
    """Download file from Hugging Face if not present locally. Thread-safe."""
    if path.exists():
        return True
    if not _HF_REPO:
        return False
    with _dl_mu:
        key = str(path)
        if key not in _dl_locks:
            _dl_locks[key] = threading.Lock()
        lock = _dl_locks[key]
    with lock:
        if path.exists():
            return True
        url = f"{_HF_BASE}/{_HF_REPO}/resolve/main/{hf_relpath}"
        try:
            r = _req.get(url, timeout=120, stream=True)
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            return True
        except Exception:
            return False

SENSIBILIDAD_PARTIDOS = {
    "izquierda":       ["PC", "FA", "FREVS", "PCCH",
                        "FRENTE AMPLIO", "CONVERGENCIA SOCIAL", "ACCION HUMANISTA",
                        "PARTIDO COMUNISTA", "PARTIDO COMUNISTA DE CHILE",
                        "REVOLUCION DEMOCRATICA", "FEDERACION REGIONALISTA VERDE SOCIAL",
                        "IND-IZQUIERDA"],
    "centroizquierda": ["PS", "PPD", "PR", "PRSD", "PDC", "DC",
                        "PARTIDO SOCIALISTA", "PARTIDO SOCIALISTA DE CHILE",
                        "PARTIDO POR LA DEMOCRACIA",
                        "PARTIDO RADICAL", "PARTIDO RADICAL DE CHILE",
                        "PARTIDO DEMOCRATA CRISTIANO", "DEMOCRACIA CRISTIANA",
                        "IND-CENTROIZQUIERDA"],
    "centro":          ["PL", "PARTIDO LIBERAL", "AMARILLOS",
                        "AMARILLOS POR CHILE",
                        "IND-CENTRO"],
    "centroderecha":   ["EVO", "EVOPOLI", "EVOLUCION POLITICA",
                        "DEMOCRATAS",
                        "IND-CENTRODERECHA"],
    "derecha":         ["UDI", "RN", "REP", "PLR", "PNL",
                        "UNION DEMOCRATA INDEPENDIENTE",
                        "UNION DEMOCRATICA INDEPENDIENTE",
                        "RENOVACION NACIONAL", "PARTIDO REPUBLICANO",
                        "PARTIDO REPUBLICANO DE CHILE",
                        "PARTIDO NACIONAL LIBERTARIO",
                        "IND-DERECHA"],
    "independiente":   ["IND", "INDEPENDIENTE", "INDEPENDIENTES",
                        "PDG", "PARTIDO DE LA GENTE"],
}

DIRECTIONAL_SENSIBILIDADES = {
    "izquierda":       ["izquierda", "centroizquierda"],
    "centroizquierda": ["izquierda", "centroizquierda", "centro"],
    "centro":          ["centroizquierda", "centro", "centroderecha"],
    "centroderecha":   ["centro", "centroderecha", "derecha"],
    "derecha":         ["centroderecha", "derecha"],
    "independiente":   ["independiente"],
}

# Sensibilidades adyacentes para fallback cuando no hay candidatos del sector pedido.
# El orden importa: se prueba de más cercano a más lejano.
SENSIBILIDAD_ADJACENTES = {
    "izquierda":       ["centroizquierda", "centro"],
    "centroizquierda": ["izquierda", "centro", "centroderecha"],
    "centro":          ["centroizquierda", "centroderecha", "izquierda", "derecha"],
    "centroderecha":   ["centro", "derecha", "centroizquierda"],
    "derecha":         ["centroderecha", "centro"],
    "independiente":   ["centro", "centroizquierda", "centroderecha"],
}


@lru_cache(maxsize=64)
def _get_connection():
    return duckdb.connect(":memory:")


@lru_cache(maxsize=1)
def _load_insights_alcaldes() -> pd.DataFrame:
    """Carga el parquet de insights de alcaldes; vacío si no fue generado todavía."""
    path = DATA_DIR / "insights_alcaldes.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def get_alcalde_insight(comuna: str) -> dict | None:
    """Metadata política del alcalde electo de una comuna (None si no hay datos)."""
    df = _load_insights_alcaldes()
    if df.empty:
        return None
    row = df[df["comuna_norm"] == comuna.upper().strip()]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "nombre": r["nombre"],
        "pacto": r["pacto"],
        "estado": r["estado"],  # REELECTO / NUEVO / NUEVO-RETORNO
        "bancada_achm": r["bancada_achm"],
        "militancia": r["militancia"],
        "cupo": r["cupo"],
        "antigua_militancia": r["antigua_militancia"],
        "sensibilidad_real": r["sensibilidad_real"],
        "es_independiente_reclasificado": bool(r["es_independiente_reclasificado"]),
    }


def _build_alcalde_sensibilidad_lookup() -> dict[tuple[str, str], str]:
    """
    Construye un diccionario (comuna_norm, candidato_normalizado) -> sensibilidad_real
    para reclasificar alcaldes IND en get_snapshot_data sin tocar el resto del flujo.

    Match por similitud relajada del nombre: comparamos sets de tokens uppercase
    sin tildes para tolerar diferencias de orden o partículas omitidas.
    """
    df = _load_insights_alcaldes()
    if df.empty:
        return {}
    out: dict[tuple[str, str], str] = {}
    for _, r in df.iterrows():
        key = (str(r["comuna_norm"]).upper().strip(),
               str(r["nombre"]).upper().strip())
        out[key] = r["sensibilidad_real"]
    return out


def _top_breakdown(df: pd.DataFrame, col: str, total_votos: float, n: int = 6) -> list[dict]:
    """Ranking de votos agrupados por `col` (partido o pacto). Vacío si la
    columna no existe todavía (parquets generados antes de agregar `pacto`)."""
    if col not in df.columns:
        return []
    g = (
        df.groupby(col)["votos_manzana"].sum()
        .reset_index().sort_values("votos_manzana", ascending=False).head(n)
    )
    g = g[g[col].astype(str).str.strip() != ""]
    g["pct"] = g["votos_manzana"] / max(total_votos, 1) * 100
    return g.rename(columns={"votos_manzana": "votos"})[[col, "votos", "pct"]].to_dict("records")


def get_available_comunas() -> list[str]:
    pesos_dir = DATA_DIR / "pesos"
    if not pesos_dir.exists():
        return []
    return sorted([p.stem for p in pesos_dir.glob("*.parquet")])


@lru_cache(maxsize=1)
def get_comunas_by_region() -> list[dict]:
    """
    Return processed communes grouped by region.
    Region is taken from the locales.parquet (built from TODOSLOCALES).
    """
    locales_path = DATA_DIR / "locales.parquet"
    if not locales_path.exists():
        # Fallback: flat list with unknown region
        return [{
            "region": "Sin región",
            "comunas": get_available_comunas(),
        }]

    locales = pd.read_parquet(locales_path)
    available = set(get_available_comunas())

    # Region column name varies; auto-detect
    region_col = next(
        (c for c in locales.columns if c.lower() == "region"),
        next((c for c in locales.columns if "region" in c.lower()), None),
    )
    if region_col is None or "comuna_norm" not in locales.columns:
        return [{"region": "Sin región", "comunas": sorted(available)}]

    # Map normalized commune name to its region (first occurrence)
    com_to_region = (
        locales.dropna(subset=[region_col])
               .groupby("comuna_norm")[region_col]
               .first()
               .to_dict()
    )

    by_region: dict[str, list[str]] = {}
    for c in available:
        region = com_to_region.get(c, "Sin región")
        # Clean region name ("DE LA ARAUCANIA" → "La Araucanía", etc.)
        region_clean = str(region).strip()
        by_region.setdefault(region_clean, []).append(c)

    return [
        {"region": region, "comunas": sorted(comunas)}
        for region, comunas in sorted(by_region.items())
    ]


@lru_cache(maxsize=1)
def _load_distritos() -> pd.DataFrame:
    path = DATA_DIR / "distritos.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def get_distritos_by_region() -> list[dict]:
    """
    Devuelve distritos agrupados por región para el flujo de diputado en el wizard.
    Cada distrito incluye las comunas que lo componen y una marca de cuáles están
    procesadas (para que la UI las muestre como navegables vs. solo informativas).
    """
    df = _load_distritos()
    if df.empty:
        return []
    available = set(get_available_comunas())

    out: dict[tuple[str, int, str], list[dict]] = {}
    for _, r in df.iterrows():
        key = (str(r["region_norm"]), int(r["distrito_id"]), str(r["distrito"]))
        out.setdefault(key, []).append({
            "comuna": str(r["comuna_norm"]),
            "procesada": str(r["comuna_norm"]) in available,
        })

    by_region: dict[str, list[dict]] = {}
    for (region, did, dname), comunas in out.items():
        by_region.setdefault(region, []).append({
            "distrito_id": did,
            "distrito": dname,
            "comunas": sorted(comunas, key=lambda c: c["comuna"]),
        })

    return [
        {"region": region, "distritos": sorted(distritos, key=lambda d: d["distrito_id"])}
        for region, distritos in sorted(by_region.items())
    ]


def get_distrito_info(distrito_id: int) -> dict | None:
    """Metadata mínima de un distrito: nombre, region, comunas que lo componen."""
    df = _load_distritos()
    if df.empty:
        return None
    sub = df[df["distrito_id"] == distrito_id]
    if sub.empty:
        return None
    return {
        "distrito_id": int(distrito_id),
        "distrito": str(sub["distrito"].iloc[0]),
        "region": str(sub["region_norm"].iloc[0]),
        "comunas": sorted(sub["comuna_norm"].astype(str).unique().tolist()),
    }


def get_available_cargos(comuna: str) -> list[str]:
    cargos = []
    for cargo in ["concejal", "core", "alcalde", "diputado"]:
        path = DATA_DIR / "votos" / cargo / f"{comuna}.parquet"
        _ensure_remote(path, f"votos/{cargo}/{comuna}.parquet")
        if path.exists():
            cargos.append(cargo)
    return cargos


def get_snapshot_data(
    comuna: str, cargo: str, sensibilidad: str,
    partido: str | None = None, pacto: str | None = None,
) -> dict | None:
    votos_path = DATA_DIR / "votos" / cargo / f"{comuna}.parquet"
    pesos_path = DATA_DIR / "pesos" / f"{comuna}.parquet"
    geo_path   = DATA_DIR / "geojson" / f"{comuna}.geojson"

    _ensure_remote(votos_path, f"votos/{cargo}/{comuna}.parquet")
    if not votos_path.exists():
        return None

    con = duckdb.connect(":memory:")

    # Load votos for this commune
    votos = con.execute(
        f"SELECT * FROM read_parquet('{votos_path}')"
    ).df()

    if votos.empty:
        return None

    # Build partido filter for this sensibilidad (or a specific partido)
    partidos = SENSIBILIDAD_PARTIDOS.get(sensibilidad, [])
    partidos_upper = [p.upper() for p in partidos]

    if pacto and "pacto" in votos.columns:
        # Filtro directo por pacto específico — ignora sensibilidad para el filtro
        mask = votos["pacto"].str.upper() == pacto.strip().upper()
    elif partido:
        # Filtro directo por partido específico — ignora sensibilidad para el filtro
        mask = votos["partido"].str.upper() == partido.strip().upper()
    else:
        # Filter to matching parties of the sensibilidad
        mask = votos["partido"].str.upper().isin(partidos_upper)

        # Para alcaldes: enriquecer la máscara incluyendo candidatos IND cuya
        # sensibilidad reclasificada (vía InsightsAlcaldes) coincida con la pedida.
        # Esto rescata IND-FP ex-PS como centroizquierda, IND-CHV con cupo UDI como
        # derecha, etc.
        if cargo == "alcalde":
            insight = get_alcalde_insight(comuna)
            if insight and insight.get("sensibilidad_real") == sensibilidad:
                nombre_insight = (insight.get("nombre") or "").upper().strip()
                insight_tokens = set(nombre_insight.split())
                cand_tokens_series = votos["candidato"].astype(str).str.upper().str.strip()
                extra_mask = cand_tokens_series.apply(
                    lambda c: len(set(c.split()) & insight_tokens) >= 2
                )
                mask = mask | extra_mask

    votos_sens = votos[mask].copy()
    proxy_sens: str | None = None
    proxy_cargo: str | None = None

    if votos_sens.empty and cargo != "concejal":
        # Antes de buscar sectores adyacentes, intentamos los votos de concejal
        # para el mismo sector: si izquierda no tuvo alcalde pero sí tuvo concejales,
        # esos votos son la mejor estimación territorial del sector en la comuna.
        concejal_path = DATA_DIR / "votos" / "concejal" / f"{comuna}.parquet"
        _ensure_remote(concejal_path, f"votos/concejal/{comuna}.parquet")
        if concejal_path.exists():
            votos_conce = pd.read_parquet(concejal_path)
            conce_mask = votos_conce["partido"].str.upper().isin(partidos_upper)
            if conce_mask.any():
                votos_sens = votos_conce[conce_mask].copy()
                votos = votos_conce
                proxy_cargo = "concejal"

    if votos_sens.empty:
        # Try adjacent sensibilidades before declaring no_data.
        for adj in SENSIBILIDAD_ADJACENTES.get(sensibilidad, []):
            adj_partidos = [p.upper() for p in SENSIBILIDAD_PARTIDOS.get(adj, [])]
            adj_mask = votos["partido"].str.upper().isin(adj_partidos)
            if adj_mask.any():
                votos_sens = votos[adj_mask].copy()
                proxy_sens = adj
                break

        if votos_sens.empty:
            # Still no data — fall back to concejal proxy metadata only.
            empty_manzanas = (
                votos.groupby("ID_MANZANA", as_index=False)
                .agg(
                    local_votacion=("local_norm", "first"),
                    local_lat=("local_lat", "first"),
                    local_lon=("local_lon", "first"),
                    dist_local_m=("dist_local_m", "first"),
                )
            )
            empty_manzanas["voto_abs"]     = 0.0
            empty_manzanas["total_votos"]  = 0.0
            empty_manzanas["voto_pct"]     = 0.0
            empty_manzanas["is_fortaleza"] = False

            alternativas = _compute_sector_alternatives(votos, exclude=sensibilidad)
            proxy = _compute_concejal_proxy(comuna, sensibilidad) if cargo != "concejal" else None

            return {
                "comuna": comuna, "cargo": cargo, "sensibilidad": sensibilidad,
                "manzanas": empty_manzanas.rename(columns={"ID_MANZANA": "id_manzana"})
                                           .to_dict("records"),
                "stats": {
                    "voto_promedio_pct": 0.0, "total_votos": 0.0,
                    "votos_sector_total": float(votos["votos_manzana"].sum()),
                    "manzanas_total": len(empty_manzanas),
                    "manzanas_fortaleza": 0, "manzanas_debilidad": len(empty_manzanas),
                    "locales_ganados": 0,
                    "locales_total": votos["local_norm"].nunique(),
                    "top_candidatos": [], "top_partidos": [],
                    "pres_historico_pct": None, "swing": None,
                },
                "narrative": f"El sector {sensibilidad} no presentó candidatos a "
                              f"{cargo} en {comuna.title()} en esta elección.",
                "no_data": True,
                "alternativas": alternativas,
                "proxy_concejales": proxy,
            }

    # Aggregate by manzana: sum all matching candidates
    mz_agg = (
        votos_sens
        .groupby("ID_MANZANA", as_index=False)
        .agg(
            voto_abs=("votos_manzana", "sum"),
            local_votacion=("local_norm", "first"),
            local_lat=("local_lat", "first"),
            local_lon=("local_lon", "first"),
            dist_local_m=("dist_local_m", "first"),
        )
    )

    # Total votos per manzana (all parties)
    total_per_mz = (
        votos.groupby("ID_MANZANA")["votos_manzana"].sum()
        .rename("total_votos")
    )
    mz_agg = mz_agg.merge(total_per_mz, on="ID_MANZANA", how="left")
    mz_agg["total_votos"] = mz_agg["total_votos"].fillna(0)
    mz_agg["voto_pct"] = np.where(
        mz_agg["total_votos"] > 0,
        mz_agg["voto_abs"] / mz_agg["total_votos"] * 100,
        0.0
    )

    # Only inhabited manzanas (total_votos > 0) count for stats.
    # Uninhabited manzanas (plazas, parks) have peso=0 → votos=0 for all candidates.
    mz_activas = mz_agg[mz_agg["total_votos"] > 0]

    # Fortalezas threshold computed only on inhabited manzanas
    threshold = mz_activas["voto_pct"].quantile(0.6) if len(mz_activas) > 0 else 0.0
    mz_agg["is_fortaleza"] = (mz_agg["total_votos"] > 0) & (mz_agg["voto_pct"] >= threshold)

    # Weighted vote share = SERVEL-equivalent %  (sum votos / sum total)
    voto_pct_ponderado = (
        float(mz_activas["voto_abs"].sum() / mz_activas["total_votos"].sum() * 100)
        if mz_activas["total_votos"].sum() > 0 else 0.0
    )

    # Top candidates
    top = (
        votos_sens.groupby(["candidato", "partido"])["votos_manzana"]
        .sum()
        .reset_index()
        .sort_values("votos_manzana", ascending=False)
        .head(5)
    )
    top_list = top.rename(columns={"votos_manzana": "votos"}).to_dict("records")

    _votos_total_sector = float(votos["votos_manzana"].sum())
    top_partidos_list = _top_breakdown(votos, "partido", _votos_total_sector)
    top_pactos_list   = _top_breakdown(votos, "pacto", _votos_total_sector)

    # Local-level results: "won" = local share above sector's commune-wide average
    local_totals = votos.groupby("local_norm")["votos_manzana"].sum()
    local_sens   = votos_sens.groupby("local_norm")["votos_manzana"].sum()
    local_share  = (local_sens / local_totals.reindex(local_sens.index)).fillna(0)
    locales_total   = int((local_totals > 0).sum())
    commune_avg     = local_sens.sum() / max(local_totals.sum(), 1)
    locales_ganados = int((local_share > commune_avg).sum())

    # Historical presidential comparison (also use weighted pct)
    pres_path = DATA_DIR / "votos" / "presidencial" / f"{comuna}.parquet"
    _ensure_remote(pres_path, f"votos/presidencial/{comuna}.parquet")
    pres_pct = None
    swing = None
    if pres_path.exists():
        pres = pd.read_parquet(pres_path)
        pres_sens = pres[pres["partido"].str.upper().isin(partidos_upper)]
        if not pres_sens.empty:
            pres_total = pres["votos_manzana"].sum()
            pres_pct = float(pres_sens["votos_manzana"].sum() / max(pres_total, 1) * 100)
            swing = voto_pct_ponderado - pres_pct

    # Techo electoral: concejal vote for same sensibilidad = party base ceiling
    techo_concejal_pct: float | None = None
    if cargo != "concejal" and not proxy_cargo:
        techo_ref = _compute_concejal_proxy(comuna, sensibilidad)
        if techo_ref:
            techo_concejal_pct = techo_ref["voto_promedio_pct"]

    stats = {
        "voto_promedio_pct": voto_pct_ponderado,
        "total_votos": float(mz_agg["voto_abs"].sum()),
        "votos_sector_total": _votos_total_sector,
        "manzanas_total": int(len(mz_activas)),
        "manzanas_fortaleza": int(mz_agg["is_fortaleza"].sum()),
        "manzanas_debilidad": int(((mz_agg["total_votos"] > 0) & (~mz_agg["is_fortaleza"])).sum()),
        "locales_ganados": locales_ganados,
        "locales_total": locales_total,
        "top_candidatos": top_list,
        "top_partidos": top_partidos_list,
        "top_pactos": top_pactos_list,
        "pres_historico_pct": pres_pct,
        "swing": swing,
        "techo_concejal_pct": techo_concejal_pct,
    }

    manzanas_out = mz_agg.rename(columns={
        "ID_MANZANA": "id_manzana",
    }).to_dict("records")

    narrative = generate_narrative(
        sensibilidad, cargo, comuna, stats, mz_agg
    )

    out = {
        "comuna": comuna,
        "cargo": cargo,
        "sensibilidad": sensibilidad,
        "manzanas": manzanas_out,
        "stats": stats,
        "narrative": narrative,
    }
    if proxy_sens:
        out["proxy_sensibilidad"] = proxy_sens
    if proxy_cargo:
        out["proxy_cargo"] = proxy_cargo
    return out


ELECTOS_POR_CARGO = {
    "alcalde":  1,
    "concejal": 8,
    "core":     6,
    "diputado": 8,
}

@lru_cache(maxsize=8)
def _load_electos(cargo: str) -> set[tuple[str, str]]:
    """
    Returns a set of (comuna_norm, candidato_norm) tuples for elected candidates.
    Built by 06_build_electos.py using proper D'Hondt. Falls back to empty set.
    """
    path = DATA_DIR / "electos" / f"{cargo}.parquet"
    if not path.exists():
        return set()
    df = pd.read_parquet(path)
    if df.empty or "comuna_norm" not in df.columns or "candidato" not in df.columns:
        return set()
    return {
        (str(row["comuna_norm"]).upper().strip(), str(row["candidato"]).upper().strip())
        for _, row in df.iterrows()
    }


def _is_electo(cargo: str, comuna: str, candidato: str) -> bool:
    """Check if a candidate is officially elected for this cargo × commune."""
    electos = _load_electos(cargo)
    if not electos:
        return False
    return (
        str(comuna).upper().strip(),
        str(candidato).upper().strip(),
    ) in electos


def get_candidatos_distrito(distrito_id: int, electos_only: bool = False) -> list[dict] | None:
    """
    Lista candidatos a diputado agregados a nivel distrito (suma de votos
    en todas las comunas del distrito). Cuando electos_only, devuelve los
    top N según ELECTOS_POR_CARGO['diputado'].
    """
    info = get_distrito_info(distrito_id)
    if not info:
        return None
    available = set(get_available_comunas())
    dfs = []
    for c in info["comunas"]:
        if c not in available:
            continue
        path = DATA_DIR / "votos" / "diputado" / f"{c}.parquet"
        _ensure_remote(path, f"votos/diputado/{c}.parquet")
        if not path.exists():
            continue
        sub = pd.read_parquet(path)
        if not sub.empty:
            dfs.append(sub)
    if not dfs:
        return None
    votos = pd.concat(dfs, ignore_index=True)
    agg = (
        votos.groupby(["candidato", "partido"], as_index=False)["votos_manzana"]
             .sum()
             .sort_values("votos_manzana", ascending=False)
    )
    agg = agg.rename(columns={"votos_manzana": "votos_total"})
    if electos_only:
        electos_set = _load_electos("diputado")
        if electos_set and info["comunas"]:
            sample_comuna = next(
                (c for c in info["comunas"] if c in available), None
            )
            if sample_comuna:
                mask = agg["candidato"].apply(
                    lambda c: (str(sample_comuna).upper().strip(), str(c).upper().strip()) in electos_set
                )
                agg = agg[mask]
            else:
                agg = agg.head(ELECTOS_POR_CARGO.get("diputado", 8))
        else:
            agg = agg.head(ELECTOS_POR_CARGO.get("diputado", 8))
    return agg.to_dict("records")


def get_autoridad_distrito_snapshot(
    distrito_id: int, candidato: str, comuna_filter: str | None = None
) -> dict | None:
    """
    Snapshot territorial de un diputado, agregando todas las comunas de su
    distrito (o filtrando a una si comuna_filter está presente).
    """
    info = get_distrito_info(distrito_id)
    if not info:
        return None
    comunas = [comuna_filter] if comuna_filter else info["comunas"]
    available = set(get_available_comunas())
    comunas_procesadas = [c for c in comunas if c in available]

    dfs = []
    for c in comunas_procesadas:
        path = DATA_DIR / "votos" / "diputado" / f"{c}.parquet"
        _ensure_remote(path, f"votos/diputado/{c}.parquet")
        if not path.exists():
            continue
        sub = pd.read_parquet(path)
        if not sub.empty:
            sub["comuna"] = c
            dfs.append(sub)
    if not dfs:
        return None
    votos = pd.concat(dfs, ignore_index=True)

    candidato_norm = candidato.upper().strip()
    votos["candidato"] = votos["candidato"].astype(str).str.upper().str.strip()
    mz_cand = votos[votos["candidato"] == candidato_norm].copy()
    if mz_cand.empty:
        mz_cand = votos[votos["candidato"].str.contains(candidato_norm, na=False, regex=False)].copy()
    if mz_cand.empty:
        return None

    partido = mz_cand["partido"].iloc[0]
    sensibilidad = infer_sensibilidad(partido)

    mz_agg = (
        mz_cand.groupby("ID_MANZANA", as_index=False)
        .agg(
            voto_abs=("votos_manzana", "sum"),
            local_votacion=("local_norm", "first"),
            local_lat=("local_lat", "first"),
            local_lon=("local_lon", "first"),
            dist_local_m=("dist_local_m", "first"),
        )
    )
    total_per_mz = (
        votos.groupby("ID_MANZANA")["votos_manzana"].sum().rename("total_votos")
    )
    mz_agg = mz_agg.merge(total_per_mz, on="ID_MANZANA", how="left")
    mz_agg["total_votos"] = mz_agg["total_votos"].fillna(0)
    mz_agg["voto_pct"] = np.where(
        mz_agg["total_votos"] > 0,
        mz_agg["voto_abs"] / mz_agg["total_votos"] * 100, 0.0
    )

    mz_activas_dist = mz_agg[mz_agg["total_votos"] > 0]
    threshold = mz_activas_dist["voto_pct"].quantile(0.6) if len(mz_activas_dist) > 0 else 0.0
    mz_agg["is_fortaleza"] = (mz_agg["total_votos"] > 0) & (mz_agg["voto_pct"] >= threshold)
    voto_ponderado_dist = (
        float(mz_activas_dist["voto_abs"].sum() / mz_activas_dist["total_votos"].sum() * 100)
        if mz_activas_dist["total_votos"].sum() > 0 else 0.0
    )

    partidos_sens = [p.upper() for p in SENSIBILIDAD_PARTIDOS.get(sensibilidad, [])]
    votos_sector = votos[votos["partido"].str.upper().isin(partidos_sens)]
    pct_sector = float(votos_sector["votos_manzana"].sum() /
                       max(votos["votos_manzana"].sum(), 1) * 100)
    pct_propio = float(mz_cand["votos_manzana"].sum() /
                       max(votos["votos_manzana"].sum(), 1) * 100)

    local_totals = votos.groupby("local_norm")["votos_manzana"].sum()
    local_propio = mz_cand.groupby("local_norm")["votos_manzana"].sum()
    locales_total = int((local_totals > 0).sum())
    locales_ganados = int(
        (local_propio / local_totals.reindex(local_propio.index) > 0.2).sum()
    )

    top_locales = (
        (local_propio / local_totals.reindex(local_propio.index) * 100)
        .dropna().sort_values(ascending=False).head(5)
    )
    top_locales_list = [
        {"local": loc, "pct": float(pct)} for loc, pct in top_locales.items()
    ]

    _votos_total_sector_dist = float(votos["votos_manzana"].sum())
    top_partidos_dist_list = _top_breakdown(votos, "partido", _votos_total_sector_dist)
    top_pactos_dist_list   = _top_breakdown(votos, "pacto", _votos_total_sector_dist)

    stats = {
        "voto_promedio_pct": voto_ponderado_dist,
        "total_votos": float(mz_agg["voto_abs"].sum()),
        "votos_sector_total": _votos_total_sector_dist,
        "manzanas_total": int(len(mz_activas_dist)),
        "manzanas_fortaleza": int(mz_agg["is_fortaleza"].sum()),
        "manzanas_debilidad": int(((mz_agg["total_votos"] > 0) & (~mz_agg["is_fortaleza"])).sum()),
        "locales_ganados": locales_ganados,
        "locales_total": locales_total,
        "top_candidatos": top_locales_list,
        "top_partidos": top_partidos_dist_list,
        "top_pactos": top_pactos_dist_list,
        "pres_historico_pct": pct_sector,
        "swing": pct_propio - pct_sector,
        "partido": partido,
        "sensibilidad_inferida": sensibilidad,
    }
    manzanas_out = mz_agg.rename(columns={"ID_MANZANA": "id_manzana"}).to_dict("records")

    label = info["distrito"] + (f" — {comuna_filter.title()}" if comuna_filter else "")
    pct = stats["voto_promedio_pct"]
    narrative = (
        f"{candidato.title()} ({partido}) obtuvo en promedio {pct:.1f}% del voto "
        f"territorial en {label}, con zonas fuertes en "
        f"{stats['manzanas_fortaleza']} de {stats['manzanas_total']} manzanas."
    )
    if stats["swing"] > 0:
        narrative += (
            f" Su rendimiento personal supera en {abs(stats['swing']):.1f}pp al desempeño "
            f"de su sector ({sensibilidad}) en el distrito."
        )

    return {
        "distrito_id": distrito_id,
        "distrito": info["distrito"],
        "comuna_filter": comuna_filter,
        "comunas": info["comunas"],
        "comunas_procesadas": comunas_procesadas,
        "cargo": "diputado",
        "sensibilidad": sensibilidad,
        "candidato": candidato_norm,
        "partido": partido,
        "manzanas": manzanas_out,
        "stats": stats,
        "narrative": narrative,
    }


def get_candidatos(comuna: str, cargo: str, electos_only: bool = False) -> list[dict] | None:
    """List candidates for a given commune × cargo, sorted by total votos.
    If electos_only, returns only the top N (heuristic) presumed to be elected.
    """
    votos_path = DATA_DIR / "votos" / cargo / f"{comuna}.parquet"
    _ensure_remote(votos_path, f"votos/{cargo}/{comuna}.parquet")
    if not votos_path.exists():
        return None
    votos = pd.read_parquet(votos_path)
    if votos.empty:
        return None
    agg = (
        votos.groupby(["candidato", "partido"], as_index=False)["votos_manzana"]
             .sum()
             .sort_values("votos_manzana", ascending=False)
    )
    agg = agg.rename(columns={"votos_manzana": "votos_total"})
    if electos_only:
        electos_set = _load_electos(cargo)
        if electos_set:
            comuna_key = str(comuna).upper().strip()
            mask = agg["candidato"].apply(
                lambda c: (comuna_key, str(c).upper().strip()) in electos_set
            )
            agg = agg[mask]
        else:
            n = ELECTOS_POR_CARGO.get(cargo, 8)
            agg = agg.head(n)
    return agg.to_dict("records")


def infer_sensibilidad(partido: str) -> str:
    import re
    p = (partido or "").upper().strip()
    if not p:
        return "independiente"
    tokens = set(re.findall(r"[A-ZÁÉÍÓÚÑ]+", p))
    for sens, partidos in SENSIBILIDAD_PARTIDOS.items():
        for prt in partidos:
            prt_u = prt.upper().strip()
            if prt_u == p:
                return sens
            # short sigla: require it to be a full token
            if len(prt_u) <= 5 and prt_u in tokens:
                return sens
            # long name: require full phrase match
            if len(prt_u) > 5 and prt_u in p:
                return sens
    return "independiente"


def get_autoridad_snapshot(comuna: str, cargo: str, candidato: str) -> dict | None:
    """Snapshot focused on a single elected authority's territorial performance."""
    votos_path = DATA_DIR / "votos" / cargo / f"{comuna}.parquet"
    _ensure_remote(votos_path, f"votos/{cargo}/{comuna}.parquet")
    if not votos_path.exists():
        return None

    votos = pd.read_parquet(votos_path)
    if votos.empty:
        return None

    candidato_norm = candidato.upper().strip()
    votos["candidato"] = votos["candidato"].astype(str).str.upper().str.strip()
    mz_cand = votos[votos["candidato"] == candidato_norm].copy()
    if mz_cand.empty:
        # Fallback: partial match
        mz_cand = votos[votos["candidato"].str.contains(candidato_norm, na=False, regex=False)].copy()
    if mz_cand.empty:
        return None

    partido = mz_cand["partido"].iloc[0]
    sensibilidad = infer_sensibilidad(partido)

    # Para alcaldes, intentar reclasificar usando InsightsAlcaldes
    # (un IND-FP ex-PS debería aparecer como centroizquierda, no como independiente).
    insight = get_alcalde_insight(comuna) if cargo == "alcalde" else None
    if insight and insight.get("sensibilidad_real"):
        sens_insight = insight["sensibilidad_real"]
        # Solo sobrescribir si el insight coincide con este candidato específico,
        # comparando por tokens del nombre para tolerar variaciones de orden/partículas.
        nombre_insight = (insight.get("nombre") or "").upper().strip()
        cand_tokens   = set(candidato_norm.split())
        insight_tokens = set(nombre_insight.split())
        # Coincidencia: al menos 2 tokens en común (apellido + nombre típico)
        if len(cand_tokens & insight_tokens) >= 2:
            sensibilidad = sens_insight

    # Aggregate per manzana
    mz_agg = (
        mz_cand.groupby("ID_MANZANA", as_index=False)
        .agg(
            voto_abs=("votos_manzana", "sum"),
            local_votacion=("local_norm", "first"),
            local_lat=("local_lat", "first"),
            local_lon=("local_lon", "first"),
            dist_local_m=("dist_local_m", "first"),
        )
    )
    total_per_mz = (
        votos.groupby("ID_MANZANA")["votos_manzana"].sum().rename("total_votos")
    )
    mz_agg = mz_agg.merge(total_per_mz, on="ID_MANZANA", how="left")
    mz_agg["total_votos"] = mz_agg["total_votos"].fillna(0)
    mz_agg["voto_pct"] = np.where(
        mz_agg["total_votos"] > 0,
        mz_agg["voto_abs"] / mz_agg["total_votos"] * 100, 0.0
    )

    mz_activas_aut = mz_agg[mz_agg["total_votos"] > 0]
    threshold = mz_activas_aut["voto_pct"].quantile(0.6) if len(mz_activas_aut) > 0 else 0.0
    mz_agg["is_fortaleza"] = (mz_agg["total_votos"] > 0) & (mz_agg["voto_pct"] >= threshold)
    voto_ponderado_aut = (
        float(mz_activas_aut["voto_abs"].sum() / mz_activas_aut["total_votos"].sum() * 100)
        if mz_activas_aut["total_votos"].sum() > 0 else 0.0
    )

    # Comparación de primera mayoría: ranking entre todos los candidatos de la elección
    votos_totales_cand = votos.groupby("candidato")["votos_manzana"].sum()
    votos_propio_abs = float(mz_cand["votos_manzana"].sum())
    rank = int((votos_totales_cand > votos_propio_abs).sum()) + 1  # 1 = primera mayoría
    primera_mayoria = rank == 1
    total_candidatos = int(votos_totales_cand.shape[0])

    total_votos_all = float(votos["votos_manzana"].sum())
    pct_propio = float(votos_propio_abs / max(total_votos_all, 1) * 100)

    # Rival más cercano (el candidato con rank inmediatamente superior o inferior)
    rival_pct: float | None = None
    sorted_votos = votos_totales_cand.sort_values(ascending=False)
    if rank <= len(sorted_votos):
        rival_abs = float(sorted_votos.iloc[rank - 1] if primera_mayoria else sorted_votos.iloc[rank - 2])
        rival_pct = rival_abs / max(total_votos_all, 1) * 100

    # Locales: where did this candidate win?
    local_totals = votos.groupby("local_norm")["votos_manzana"].sum()
    local_propio = mz_cand.groupby("local_norm")["votos_manzana"].sum()
    locales_total = int((local_totals > 0).sum())
    locales_ganados = int((local_propio / local_totals.reindex(local_propio.index) > 0.2).sum())

    top_locales = (
        (local_propio / local_totals.reindex(local_propio.index) * 100)
        .dropna().sort_values(ascending=False).head(5)
    )
    top_locales_list = [
        {"local": loc, "pct": float(pct)} for loc, pct in top_locales.items()
    ]

    _votos_total_sector_aut = float(votos["votos_manzana"].sum())
    top_partidos_aut_list = _top_breakdown(votos, "partido", _votos_total_sector_aut)
    top_pactos_aut_list   = _top_breakdown(votos, "pacto", _votos_total_sector_aut)

    stats = {
        "voto_promedio_pct": voto_ponderado_aut,
        "total_votos": float(mz_agg["voto_abs"].sum()),
        "votos_sector_total": _votos_total_sector_aut,
        "manzanas_total": int(len(mz_activas_aut)),
        "manzanas_fortaleza": int(mz_agg["is_fortaleza"].sum()),
        "manzanas_debilidad": int(((mz_agg["total_votos"] > 0) & (~mz_agg["is_fortaleza"])).sum()),
        "locales_ganados": locales_ganados,
        "locales_total": locales_total,
        "top_candidatos": top_locales_list,
        "top_partidos": top_partidos_aut_list,
        "top_pactos": top_pactos_aut_list,
        "pres_historico_pct": pct_propio,
        "swing": None,
        "rank": rank,
        "total_candidatos": total_candidatos,
        "primera_mayoria": primera_mayoria,
        "rival_pct": rival_pct,
        "partido": partido,
        "sensibilidad_inferida": sensibilidad,
    }

    manzanas_out = mz_agg.rename(columns={"ID_MANZANA": "id_manzana"}).to_dict("records")

    pct = stats["voto_promedio_pct"]
    fortalezas = stats["manzanas_fortaleza"]
    total_mz = stats["manzanas_total"]
    narrative_parts = [
        f"{candidato.title()} ({partido}) obtuvo en promedio {pct:.1f}% del voto territorial",
        f"en {comuna.title()}, con zonas fuertes en {fortalezas} de {total_mz} manzanas analizadas.",
    ]
    if stats["primera_mayoria"]:
        rival_note = ""
        if stats["rival_pct"] is not None:
            rival_note = f" El candidato más cercano obtuvo {stats['rival_pct']:.1f}%."
        narrative_parts.append(
            f"Fue primera mayoría comunal con {pct:.1f}% del voto.{rival_note}"
        )
    elif stats["rank"] and stats["total_candidatos"]:
        narrative_parts.append(
            f"Obtuvo el lugar N°{stats['rank']} de {stats['total_candidatos']} candidatos en la elección."
        )

    # Enriquecer narrativa con insights (solo alcaldes con match de nombre)
    if insight and len(cand_tokens & insight_tokens) >= 2:
        estado = insight.get("estado") or ""
        antigua = insight.get("antigua_militancia") or ""
        cupo = insight.get("cupo") or ""
        es_recl = insight.get("es_independiente_reclasificado")

        if estado.startswith("REELECTO"):
            narrative_parts.append("Es alcalde reelecto, consolidando una base ya construida.")
        elif estado == "NUEVO-RETORNO":
            narrative_parts.append("Vuelve al cargo tras un período fuera, recuperando territorio histórico.")
        elif estado.startswith("NUEVO"):
            narrative_parts.append("Es alcalde nuevo, sin desempeño municipal previo en esta comuna.")

        if es_recl and antigua:
            narrative_parts.append(
                f"Aunque compitió como independiente, su trayectoria viene de {antigua}, "
                f"lo que reclasifica la lectura territorial hacia su sector real."
            )
        elif es_recl and cupo:
            narrative_parts.append(
                f"Entró como independiente dentro del pacto, ocupando el cupo de {cupo}."
            )

    return {
        "comuna": comuna,
        "cargo": cargo,
        "sensibilidad": sensibilidad,
        "candidato": candidato_norm,
        "partido": partido,
        "manzanas": manzanas_out,
        "stats": stats,
        "narrative": " ".join(narrative_parts),
        "insights": insight if insight and len(cand_tokens & insight_tokens) >= 2 else None,
    }


def _compute_sector_alternatives(votos: pd.DataFrame, exclude: str) -> list[dict]:
    """For each other sensibilidad, report whether it had candidates and its share."""
    total = votos["votos_manzana"].sum()
    out = []
    for sens, partidos in SENSIBILIDAD_PARTIDOS.items():
        if sens == exclude:
            continue
        partidos_up = [p.upper() for p in partidos]
        mask = votos["partido"].str.upper().isin(partidos_up)
        subset = votos[mask]
        if subset.empty:
            continue
        n_candidatos = subset["candidato"].nunique()
        votos_sum = subset["votos_manzana"].sum()
        share = float(votos_sum / total * 100) if total else 0.0
        out.append({
            "sensibilidad": sens,
            "candidatos": int(n_candidatos),
            "voto_promedio_pct": share,
        })
    out.sort(key=lambda r: r["voto_promedio_pct"], reverse=True)
    return out


def _compute_concejal_proxy(comuna: str, sensibilidad: str) -> dict | None:
    """Return a slim summary of this sensibilidad's territorial performance in concejales,
    used as a fallback projection when this sector did not run in another cargo."""
    path = DATA_DIR / "votos" / "concejal" / f"{comuna}.parquet"
    _ensure_remote(path, f"votos/concejal/{comuna}.parquet")
    if not path.exists():
        return None
    votos = pd.read_parquet(path)
    partidos_up = [p.upper() for p in SENSIBILIDAD_PARTIDOS.get(sensibilidad, [])]
    sens_subset = votos[votos["partido"].str.upper().isin(partidos_up)]
    if sens_subset.empty:
        return None
    total_per_mz = votos.groupby("ID_MANZANA")["votos_manzana"].sum()
    sens_per_mz  = sens_subset.groupby("ID_MANZANA")["votos_manzana"].sum()
    # Weighted mean on inhabited manzanas only (same logic as get_snapshot_data)
    inhabited = total_per_mz[total_per_mz > 0]
    sens_inhabited = sens_per_mz.reindex(inhabited.index).fillna(0)
    voto_ponderado = (
        float(sens_inhabited.sum() / inhabited.sum() * 100)
        if inhabited.sum() > 0 else 0.0
    )
    return {
        "voto_promedio_pct": voto_ponderado,
        "manzanas_con_datos": int((sens_per_mz > 0).sum()),
        "candidatos": int(sens_subset["candidato"].nunique()),
    }


def get_geojson(comuna: str) -> dict | None:
    geo_path = DATA_DIR / "geojson" / f"{comuna}.geojson"
    _ensure_remote(geo_path, f"geojson/{comuna}.geojson")
    if not geo_path.exists():
        return None
    with open(geo_path, encoding="utf-8") as f:
        return json.load(f)


def get_distrito_geojson(distrito_id: int, comuna_filter: str | None = None) -> dict | None:
    """
    Une los geojsons de todas las comunas de un distrito en una sola FeatureCollection.
    Si comuna_filter es provisto, devuelve solo esa comuna (drill-in dentro del distrito).
    """
    info = get_distrito_info(distrito_id)
    if not info:
        return None

    comunas = [comuna_filter] if comuna_filter else info["comunas"]
    available = set(get_available_comunas())

    features = []
    for c in comunas:
        if c not in available:
            continue
        path = DATA_DIR / "geojson" / f"{c}.geojson"
        _ensure_remote(path, f"geojson/{c}.geojson")
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            geo = json.load(f)
        for feat in geo.get("features", []):
            # Etiquetar cada manzana con su comuna para el filtro del frontend
            feat.setdefault("properties", {})["COMUNA"] = c
            features.append(feat)

    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}


def get_distrito_snapshot(
    distrito_id: int, sensibilidad: str, comuna_filter: str | None = None
) -> dict | None:
    """
    Snapshot agregando todas las comunas de un distrito para cargo=diputado.
    Si comuna_filter está presente, restringe el análisis a esa comuna (drill-in).
    """
    info = get_distrito_info(distrito_id)
    if not info:
        return None

    comunas_distrito = [comuna_filter] if comuna_filter else info["comunas"]
    available = set(get_available_comunas())
    comunas_procesadas = [c for c in comunas_distrito if c in available]

    if not comunas_procesadas:
        return None

    # Cargar y concatenar votos de todas las comunas del distrito (cargo=diputado)
    dfs = []
    for c in comunas_procesadas:
        path = DATA_DIR / "votos" / "diputado" / f"{c}.parquet"
        _ensure_remote(path, f"votos/diputado/{c}.parquet")
        if not path.exists():
            continue
        sub = pd.read_parquet(path)
        if sub.empty:
            continue
        sub["comuna"] = c
        dfs.append(sub)

    if not dfs:
        return None

    votos = pd.concat(dfs, ignore_index=True)

    partidos = SENSIBILIDAD_PARTIDOS.get(sensibilidad, [])
    partidos_upper = [p.upper() for p in partidos]
    mask = votos["partido"].str.upper().isin(partidos_upper)
    votos_sens = votos[mask].copy()

    label = info["distrito"] + (
        f" — {comuna_filter.title()}" if comuna_filter else ""
    )

    if votos_sens.empty:
        empty_manzanas = (
            votos.groupby("ID_MANZANA", as_index=False)
            .agg(
                local_votacion=("local_norm", "first"),
                local_lat=("local_lat", "first"),
                local_lon=("local_lon", "first"),
                dist_local_m=("dist_local_m", "first"),
            )
        )
        empty_manzanas["voto_abs"]     = 0.0
        empty_manzanas["total_votos"]  = 0.0
        empty_manzanas["voto_pct"]     = 0.0
        empty_manzanas["is_fortaleza"] = False
        return {
            "distrito_id": distrito_id,
            "distrito": info["distrito"],
            "comuna_filter": comuna_filter,
            "comunas": info["comunas"],
            "comunas_procesadas": comunas_procesadas,
            "cargo": "diputado",
            "sensibilidad": sensibilidad,
            "manzanas": empty_manzanas.rename(columns={"ID_MANZANA": "id_manzana"})
                                       .to_dict("records"),
            "stats": {
                "voto_promedio_pct": 0.0, "total_votos": 0.0,
                "manzanas_total": len(empty_manzanas),
                "manzanas_fortaleza": 0, "manzanas_debilidad": len(empty_manzanas),
                "locales_ganados": 0,
                "locales_total": votos["local_norm"].nunique(),
                "top_candidatos": [], "top_partidos": [],
                "votos_sector_total": float(votos["votos_manzana"].sum()),
                "pres_historico_pct": None, "swing": None,
            },
            "narrative": f"El sector {sensibilidad} no presentó candidatos a "
                          f"diputado en {label} en esta elección.",
            "no_data": True,
            "alternativas": _compute_sector_alternatives(votos, exclude=sensibilidad),
            "proxy_concejales": None,  # proxy a nivel de distrito no aplica directo
        }

    # Aggregate per manzana (ID_MANZANA es único nacional vía INE)
    mz_agg = (
        votos_sens
        .groupby("ID_MANZANA", as_index=False)
        .agg(
            voto_abs=("votos_manzana", "sum"),
            local_votacion=("local_norm", "first"),
            local_lat=("local_lat", "first"),
            local_lon=("local_lon", "first"),
            dist_local_m=("dist_local_m", "first"),
        )
    )
    total_per_mz = (
        votos.groupby("ID_MANZANA")["votos_manzana"].sum().rename("total_votos")
    )
    mz_agg = mz_agg.merge(total_per_mz, on="ID_MANZANA", how="left")
    mz_agg["total_votos"] = mz_agg["total_votos"].fillna(0)
    mz_agg["voto_pct"] = np.where(
        mz_agg["total_votos"] > 0,
        mz_agg["voto_abs"] / mz_agg["total_votos"] * 100, 0.0
    )

    mz_activas_dist = mz_agg[mz_agg["total_votos"] > 0]
    threshold = mz_activas_dist["voto_pct"].quantile(0.6) if len(mz_activas_dist) > 0 else 0.0
    mz_agg["is_fortaleza"] = (mz_agg["total_votos"] > 0) & (mz_agg["voto_pct"] >= threshold)
    voto_pct_ponderado = (
        float(mz_activas_dist["voto_abs"].sum() / mz_activas_dist["total_votos"].sum() * 100)
        if mz_activas_dist["total_votos"].sum() > 0 else 0.0
    )

    top = (
        votos_sens.groupby(["candidato", "partido"])["votos_manzana"]
        .sum().reset_index().sort_values("votos_manzana", ascending=False).head(5)
    )
    top_list = top.rename(columns={"votos_manzana": "votos"}).to_dict("records")

    _votos_total_sector_daut = float(votos["votos_manzana"].sum())
    top_partidos_daut_list = _top_breakdown(votos, "partido", _votos_total_sector_daut)
    top_pactos_daut_list   = _top_breakdown(votos, "pacto", _votos_total_sector_daut)

    local_totals = votos.groupby("local_norm")["votos_manzana"].sum()
    local_sens   = votos_sens.groupby("local_norm")["votos_manzana"].sum()
    local_share  = (local_sens / local_totals.reindex(local_sens.index)).fillna(0)
    locales_total = int((local_totals > 0).sum())
    distrito_avg  = local_sens.sum() / max(local_totals.sum(), 1)
    locales_ganados = int((local_share > distrito_avg).sum())

    stats = {
        "voto_promedio_pct": voto_pct_ponderado,
        "total_votos": float(mz_agg["voto_abs"].sum()),
        "votos_sector_total": _votos_total_sector_daut,
        "manzanas_total": int(len(mz_activas_dist)),
        "manzanas_fortaleza": int(mz_agg["is_fortaleza"].sum()),
        "manzanas_debilidad": int(((mz_agg["total_votos"] > 0) & (~mz_agg["is_fortaleza"])).sum()),
        "locales_ganados": locales_ganados,
        "locales_total": locales_total,
        "top_candidatos": top_list,
        "top_partidos": top_partidos_daut_list,
        "top_pactos": top_pactos_daut_list,
        "pres_historico_pct": None,
        "swing": None,
    }
    manzanas_out = mz_agg.rename(columns={"ID_MANZANA": "id_manzana"}).to_dict("records")

    # Narrativa simplificada: reutilizamos el generador con cargo=diputado y
    # "comuna" actuando como label del distrito (o distrito+comuna en drill-in).
    narrative = generate_narrative(sensibilidad, "diputado", label, stats, mz_agg)

    return {
        "distrito_id": distrito_id,
        "distrito": info["distrito"],
        "comuna_filter": comuna_filter,
        "comunas": info["comunas"],
        "comunas_procesadas": comunas_procesadas,
        "cargo": "diputado",
        "sensibilidad": sensibilidad,
        "manzanas": manzanas_out,
        "stats": stats,
        "narrative": narrative,
    }


def generate_narrative(sensibilidad: str, cargo: str, comuna: str,
                       stats: dict, mz_agg: pd.DataFrame) -> str:
    """
    Build the territorial narrative. For alcalde we talk about candidaturas
    (since only one wins per commune); for the other cargos we talk about
    sector / lista since candidates run on slates.
    """
    cargo_es_uninominal = cargo == "alcalde"
    top_cands = stats.get("top_candidatos", [])
    nombres = [c["candidato"] for c in top_cands if c.get("candidato")]
    n_cands = len(nombres)
    pct = stats["voto_promedio_pct"]
    fortalezas = stats["manzanas_fortaleza"]
    total_mz   = stats["manzanas_total"]
    locales_ganados = stats["locales_ganados"]
    locales_total   = stats["locales_total"]

    label_sector = {
        "izquierda":       "La izquierda",
        "centroizquierda": "La centroizquierda",
        "centro":          "El centro político",
        "centroderecha":   "La centroderecha",
        "derecha":         "La derecha",
        "independiente":   "Las candidaturas independientes",
    }.get(sensibilidad, "El sector")

    # Build subject: candidatura(s) for alcalde or independiente, sector for the rest.
    if cargo_es_uninominal and n_cands > 0:
        if n_cands == 1:
            label = f"La candidatura de {nombres[0].title()}"
        else:
            joined = ", ".join(n.title() for n in nombres[:3])
            label = f"Las candidaturas de {joined}"
    elif sensibilidad == "independiente" and n_cands > 0:
        joined = ", ".join(n.title() for n in nombres[:3])
        suffix = f" y {n_cands - 3} más" if n_cands > 3 else ""
        label = f"Las candidaturas independientes ({joined}{suffix})"
    else:
        label = label_sector

    cargo_label = {
        "concejal": "la elección de concejales",
        "core":     "la elección de CORE",
        "alcalde":  "la elección de alcalde",
        "diputado": "la elección de diputados",
    }.get(cargo, "esta elección")

    pct_fortalezas = fortalezas / max(total_mz, 1) * 100

    if pct >= 40:
        fuerza = "muestra una presencia dominante"
    elif pct >= 30:
        fuerza = "tiene una presencia significativa"
    elif pct >= 20:
        fuerza = "mantiene presencia competitiva"
    else:
        fuerza = "presenta una base electoral limitada"

    territorio = (
        f"controlando el {pct_fortalezas:.0f}% del territorio comunal"
        if pct_fortalezas > 50
        else f"con zonas fuertes en {fortalezas} de {total_mz} manzanas"
    )

    locales_str = (
        f"dominando {locales_ganados} de {locales_total} locales de votación"
        if locales_total > 0 else ""
    )

    parts = [
        f"{label} {fuerza} en {cargo_label} de {comuna.title()},",
        f"promediando {pct:.1f}% del voto territorial",
        f"y {territorio}.",
    ]
    if locales_str:
        parts.append(f"El análisis de locales muestra {locales_str}.")

    if stats.get("swing") is not None:
        swing = stats["swing"]
        direction = "por encima" if swing > 0 else "por debajo"
        sujeto = "esta candidatura" if cargo_es_uninominal else "este sector"
        parts.append(f"Comparado con la primera vuelta presidencial, {sujeto} está "
                     f"{abs(swing):.1f}pp {direction}.")

    return " ".join(parts)
