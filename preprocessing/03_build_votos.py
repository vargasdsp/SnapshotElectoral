"""
Step 3: Distribute electoral votes to manzanas per commune.

Implements the repartir() logic from the notebook using the pre-built
tabla_pesos (centroid method). No individual voter geocoding needed.

Outputs: data/processed/votos/{cargo}/{COMUNA}.parquet
Each file contains: ID_MANZANA, candidato, partido, votos, pct_manzana
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from pathlib import Path
from utils import normaliza_texto, canonizar_local, filtrar_comuna, to_numeric_cl

RAW_DIR  = Path(__file__).parent.parent
PROC_DIR = Path(__file__).parent.parent / "data" / "processed"
PESOS_DIR = PROC_DIR / "pesos"

# Source files
SOURCES = {
    "concejal": RAW_DIR / "Concejales24.txt",
    "core":     RAW_DIR / "Cores24.txt",
    "alcalde":  RAW_DIR / "Muni24.xlsx",
    "diputado": RAW_DIR / "Dipu25.csv",
}

# Real schemas (verified via inspect_sources.py)
# All names compared case-insensitively (uppercased internally).
SCHEMA = {
    "concejal": {
        "encoding":     "utf-8",
        "sep":          ";",
        "col_comuna":   "COMUNA",
        "col_local":    "LOCAL",
        # candidate name = concat(Nombres, Primer apellido, Segundo apellido)
        "col_cand_parts": ["NOMBRES", "PRIMER APELLIDO", "SEGUNDO APELLIDO"],
        "col_partido":  "PARTIDO",
        "col_subpacto": "SUBPACTO",
        "col_votos":    "VOTOS",
    },
    "core": {
        "encoding":     "utf-8",
        "sep":          ";",
        "col_comuna":   "COMUNA",
        "col_local":    "LOCAL",
        "col_cand_parts": ["NOMBRES", "PRIMER APELLIDO", "SEGUNDO APELLIDO"],
        "col_partido":  "PARTIDO",
        "col_subpacto": "SUBPACTO",
        "col_votos":    "VOTOS",
    },
    "alcalde": {
        "encoding":     None,
        "sep":          None,  # xlsx
        "col_comuna":   "COMUNA",
        "col_local":    "LOCAL",
        "col_cand_parts": ["NOMBRES", "PRIMER APELLIDO", "SEGUNDO APELLIDO"],
        "col_partido":  "PARTIDO",
        "col_subpacto": "SUBPACTO",
        "col_votos":    "VOTOS",
    },
    "diputado": {
        "encoding":     "utf-8",
        "sep":          ";",
        "col_comuna":   "COMUNA",
        "col_local":    "LOCAL",
        "col_cand":     "CANDIDATO",
        "col_partido":  "PARTIDO",
        "col_subpacto": "SUBPACTO",
        "col_votos":    "VOTOS",
    },
}

# Keyword → partido_efectivo for IND candidates.
# Normalized (uppercase, ASCII) keywords matched against the Subpacto field.
# Order matters: more specific entries first.
SUBPACTO_KEYWORD_MAP = [
    # Izquierda
    ("CONVERGENCIA SOCIAL",    "IND-IZQUIERDA"),
    ("ACCION HUMANISTA",       "IND-IZQUIERDA"),
    ("REVOLUCION DEMOCRATICA", "IND-IZQUIERDA"),
    ("PARTIDO COMUNISTA",      "IND-IZQUIERDA"),
    ("FRENTE AMPLIO",          "IND-IZQUIERDA"),
    ("FREVS",                  "IND-IZQUIERDA"),
    # Centroizquierda
    ("DEMOCRACIA CRISTIANA",   "IND-CENTROIZQUIERDA"),
    ("PARTIDO SOCIALISTA",     "IND-CENTROIZQUIERDA"),
    ("PARTIDO RADICAL",        "IND-CENTROIZQUIERDA"),
    ("PPD",                    "IND-CENTROIZQUIERDA"),
    ("NUEVA ACCION",           "IND-CENTROIZQUIERDA"),
    ("NUEVA MAYORIA",          "IND-CENTROIZQUIERDA"),
    # Centro
    ("AMARILLOS",              "IND-CENTRO"),
    ("PARTIDO LIBERAL",        "IND-CENTRO"),
    # Centroderecha
    ("EVOPOLI",                "IND-CENTRODERECHA"),
    ("EVOLUCION POLITICA",     "IND-CENTRODERECHA"),
    ("DEMOCRATAS",             "IND-CENTRODERECHA"),
    # Derecha
    ("RENOVACION NACIONAL",    "IND-DERECHA"),
    ("UNION DEMOCRATA",        "IND-DERECHA"),
    ("REPUBLICANO",            "IND-DERECHA"),
    ("CHILE VAMOS",            "IND-DERECHA"),
    ("PARTIDO NACIONAL",       "IND-DERECHA"),
]


def reclasificar_independientes(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """For IND candidates that ran under a pact (Subpacto), replace partido
    with a synthetic 'IND-<sensibilidad>' label so they appear in the right sector."""
    col_partido  = schema["col_partido"].upper()
    col_subpacto = schema.get("col_subpacto", "SUBPACTO").upper()

    if col_subpacto not in df.columns:
        return df

    is_ind = df[col_partido].str.strip().str.upper().isin(
        {"IND", "INDEPENDIENTE", "INDEPENDIENTES"}
    )
    if not is_ind.any():
        return df

    df = df.copy()

    def _lookup(subpacto: str) -> str | None:
        norm = normaliza_texto(subpacto).upper() if subpacto else ""
        for keyword, partido_ef in SUBPACTO_KEYWORD_MAP:
            if keyword in norm:
                return partido_ef
        return None

    reclasificados = 0
    for idx in df.index[is_ind]:
        raw_subpacto = str(df.at[idx, col_subpacto])
        partido_ef = _lookup(raw_subpacto)
        if partido_ef:
            df.at[idx, col_partido] = partido_ef
            reclasificados += 1

    if reclasificados:
        print(f"  Reclasificados {reclasificados} IND por subpacto")

    return df


def load_results(cargo: str, comuna: str) -> pd.DataFrame | None:
    src = SOURCES[cargo]
    schema = SCHEMA[cargo]
    if not src.exists():
        print(f"  Source not found: {src}")
        return None

    print(f"  Loading {src.name} for {comuna}...")

    try:
        if src.suffix == ".xlsx":
            df = pd.read_excel(src)
            df.columns = [c.strip().upper() for c in df.columns]
            df = filtrar_comuna(df, schema["col_comuna"], comuna)
        else:
            chunksize = 200_000
            chunks = []
            for chunk in pd.read_csv(
                src, sep=schema["sep"], encoding=schema["encoding"],
                chunksize=chunksize, low_memory=False, on_bad_lines="skip"
            ):
                chunk.columns = [c.strip().upper() for c in chunk.columns]
                filtered = filtrar_comuna(chunk, schema["col_comuna"], comuna)
                if len(filtered) > 0:
                    chunks.append(filtered)
            df = pd.concat(chunks) if chunks else pd.DataFrame()
    except Exception as e:
        print(f"  Error loading {src}: {e}")
        return None

    if len(df) == 0:
        print(f"  No data for {comuna} in {cargo}")
        return None

    # Build composite candidate name if needed
    if "col_cand_parts" in schema and schema["col_cand_parts"]:
        parts = [p.upper() for p in schema["col_cand_parts"]]
        missing = [p for p in parts if p not in df.columns]
        if missing:
            print(f"  Warning: missing name parts {missing}; columns are {df.columns.tolist()[:10]}...")
        else:
            df["CANDIDATO"] = (
                df[parts[0]].fillna("").astype(str).str.strip() + " " +
                df[parts[1]].fillna("").astype(str).str.strip() + " " +
                df[parts[2]].fillna("").astype(str).str.strip()
            ).str.replace(r"\s+", " ", regex=True).str.strip()
            schema["col_cand"] = "CANDIDATO"

    df = reclasificar_independientes(df, schema)
    print(f"  Found {len(df):,} rows")
    return df


def repartir(resultados: pd.DataFrame, pesos: pd.DataFrame,
             schema: dict, cargo: str) -> pd.DataFrame | None:
    """
    Core redistribution function: assigns local-level votes to manzanas.
    Translated directly from notebook's repartir() with centroid weights.
    """
    col_local   = schema["col_local"].upper()
    col_cand    = schema.get("col_cand", "CANDIDATO").upper()
    col_partido = schema["col_partido"].upper()
    col_votos   = schema["col_votos"].upper()

    # Normalize local names in results
    resultados = resultados.copy()
    resultados["local_canon"] = resultados[col_local].apply(canonizar_local)
    resultados[col_votos] = to_numeric_cl(resultados[col_votos]).fillna(0)

    # Aggregate by (canonical local, candidato, partido).
    # Multiple sub-sedes ("L1","L2") of the same local in source data collapse here,
    # so we sum them into a single canonical local total.
    agg = (
        resultados
        .groupby(["local_canon", col_cand, col_partido], as_index=False)
        [col_votos].sum()
    )
    agg.columns = ["local_canon", "candidato", "partido", "votos_local"]

    # Normalize local name in pesos using the same canonical form
    pesos = pesos.copy()
    pesos["local_canon"] = pesos["local_norm"].apply(canonizar_local)

    # Join on canonical name
    merged = pesos.merge(agg, on="local_canon", how="inner")

    if len(merged) == 0:
        print("  Warning: no local name matches found between results and pesos")
        return None

    # Diagnostic: coverage
    src_locales = agg["local_canon"].nunique()
    matched_locales = merged["local_canon"].nunique()
    coverage = matched_locales / max(src_locales, 1) * 100
    print(f"  Local match coverage: {matched_locales}/{src_locales} ({coverage:.0f}%)")

    # Apply peso (centroid method: peso=1.0 so votes go directly)
    merged["votos_manzana"] = merged["votos_local"] * merged["peso"]

    # Calculate total votes per manzana (all candidates)
    total_por_manzana = (
        merged.groupby("ID_MANZANA")["votos_manzana"].sum()
        .rename("votos_total_manzana")
    )
    merged = merged.merge(total_por_manzana, on="ID_MANZANA", how="left")
    merged["pct_manzana"] = np.where(
        merged["votos_total_manzana"] > 0,
        merged["votos_manzana"] / merged["votos_total_manzana"] * 100,
        0.0
    )

    out = merged[[
        "ID_MANZANA", "local_norm", "local_lat", "local_lon",
        "candidato", "partido", "votos_manzana", "votos_total_manzana",
        "pct_manzana", "dist_local_m"
    ]].copy()

    out["candidato"] = out["candidato"].apply(normaliza_texto)
    out["partido"]   = out["partido"].apply(normaliza_texto)
    out["cargo"]     = cargo
    return out


def main(comunas: list[str] | None = None, cargos: list[str] | None = None):
    available_comunas = sorted([p.stem for p in PESOS_DIR.glob("*.parquet")])
    if not available_comunas:
        print("No pesos files found. Run 02_build_pesos.py first.")
        return

    target_comunas = comunas or available_comunas
    target_cargos  = cargos or list(SOURCES.keys())

    for cargo in target_cargos:
        out_dir = PROC_DIR / "votos" / cargo
        out_dir.mkdir(parents=True, exist_ok=True)

        for comuna in target_comunas:
            print(f"\n[{cargo.upper()}] {comuna}")
            pesos_path = PESOS_DIR / f"{comuna}.parquet"
            if not pesos_path.exists():
                print(f"  No pesos file for {comuna} — skipping")
                continue

            pesos = pd.read_parquet(pesos_path)
            resultados = load_results(cargo, comuna)
            if resultados is None:
                continue

            votos = repartir(resultados, pesos, SCHEMA[cargo], cargo)
            if votos is None:
                continue

            out_path = out_dir / f"{comuna}.parquet"
            votos.to_parquet(out_path, index=False)
            print(f"  Saved {len(votos):,} rows -> {out_path.name}")
            print(f"  Candidates: {votos['candidato'].nunique()}")

    print("\nDone.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--comunas", nargs="*", help="Communes to process")
    parser.add_argument("--cargos", nargs="*", choices=list(SOURCES.keys()),
                        help="Cargo types to process")
    args = parser.parse_args()

    from utils import normaliza_texto
    comunas = [normaliza_texto(c) for c in args.comunas] if args.comunas else None
    main(comunas=comunas, cargos=args.cargos)
