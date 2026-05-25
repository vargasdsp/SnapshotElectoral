"""
Step 6: Compute elected candidates using the D'Hondt method.

- alcalde:  top 1 by votes (uninominal, already correct).
- concejal: D'Hondt at Lista level per commune.
             N escaños from Dipu25.csv electores (Ley 18.695, Art. 72):
               <= 15,000 → 6  |  15,001–70,000 → 8  |  >70,000 → 10
- core:     D'Hondt at Lista level per circunscripcion provincial.
             N escaños hardcoded from official SERVEL 2024 proclamation.
- diputado: D'Hondt at Pacto level per distrito.
             N escaños hardcoded from official TRICEL 2025 proclamation.

Output: data/processed/electos/{cargo}.parquet
Columns: comuna_norm, candidato, partido, lista, votos_total
Each row = one elected candidate for that commune × cargo.
For core/diputado a candidate appears in every commune of its scope.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from pathlib import Path
from utils import normaliza_texto, filtrar_comuna

RAW_DIR  = Path(__file__).parent.parent
PROC_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR  = PROC_DIR / "electos"

# ---------------------------------------------------------------------------
# Seat counts (official, from SERVEL/TRICEL 2024-2025)
# ---------------------------------------------------------------------------

# Diputados: seats per distrito (Elecciones 2025, 155 total)
DIPUTADO_N: dict[int, int] = {
    1: 3,  2: 3,  3: 5,  4: 5,  5: 7,  6: 8,  7: 8,  8: 8,  9: 7, 10: 8,
   11: 6, 12: 7, 13: 5, 14: 6, 15: 5, 16: 4, 17: 7, 18: 4, 19: 5, 20: 8,
   21: 5, 22: 4, 23: 7, 24: 5, 25: 4, 26: 5, 27: 3, 28: 3,
}

# Cores: seats per circunscripcion provincial (Elecciones 2024, 302 total)
# Keys are normalized (uppercase, no accents) matching Cores24.txt column.
CORE_N: dict[str, int] = {
    # Arica y Parinacota
    "ARICA": 11, "PARINACOTA": 3,
    # Tarapacá
    "IQUIQUE": 11, "TAMARUGAL": 3,
    # Antofagasta
    "ANTOFAGASTA": 8, "EL LOA": 5, "TOCOPILLA": 3,
    # Atacama
    "COPIAPO": 8, "HUASCO": 4, "CHANARAL": 2,
    # Coquimbo
    "ELQUI": 8, "LIMARI": 4, "CHOAPA": 4,
    # Valparaíso
    "VALPARAISO I": 5, "VALPARAISO II": 4, "MARGA MARGA": 4,
    "SAN ANTONIO": 3, "SAN FELIPE": 3, "QUILLOTA": 3,
    "PETORCA": 2, "LOS ANDES": 2, "ISLA DE PASCUA": 2,
    # Metropolitana
    "SANTIAGO I": 3, "SANTIAGO II": 4, "SANTIAGO III": 3, "SANTIAGO IV": 4,
    "SANTIAGO V": 4, "SANTIAGO VI": 4,
    "CORDILLERA": 3, "MAIPO": 3, "CHACABUCO": 2, "MELIPILLA": 2, "TALAGANTE": 2,
    # O'Higgins
    "CACHAPOAL I": 5, "CACHAPOAL II": 8, "COLCHAGUA": 5, "CARDENAL CARO": 2,
    # Maule
    "TALCA": 7, "CURICO": 6, "LINARES": 5, "CAUQUENES": 2,
    # Ñuble
    "DIGUILLIN": 8, "PUNILLA": 4, "ITATA": 4,
    # Biobío
    "CONCEPCION I": 6, "CONCEPCION II": 6, "CONCEPCION III": 6,
    "BIOBIO": 6, "ARAUCO": 4,
    # Araucanía
    "CAUTIN I": 7, "CAUTIN II": 8, "MALLECO": 5,
    # Los Ríos
    "VALDIVIA": 9, "RANCO": 5,
    # Los Lagos
    "LLANQUIHUE": 8, "OSORNO": 6, "CHILOE": 4, "PALENA": 2,
    # Aysén
    "COYHAIQUE": 6, "AISEN": 4, "CAPITAN PRAT": 2, "GENERAL CARRERA": 2,
    # Magallanes
    "MAGALLANES": 7, "ULTIMA ESPERANZA": 3, "TIERRA DEL FUEGO": 2,
    "ANTARTICA CHILENA": 2,
}


# ---------------------------------------------------------------------------
# D'Hondt core
# ---------------------------------------------------------------------------

def dhondt(votos_por_lista: dict[str, float], n_escanos: int) -> dict[str, int]:
    """Return {lista: seats_won} via D'Hondt quotient method."""
    if n_escanos <= 0:
        return {}
    quotients: list[tuple[float, str]] = []
    for lista, votos in votos_por_lista.items():
        if votos > 0:
            for div in range(1, n_escanos + 1):
                quotients.append((votos / div, lista))
    quotients.sort(reverse=True)
    seats: dict[str, int] = {}
    for _, lista in quotients[:n_escanos]:
        seats[lista] = seats.get(lista, 0) + 1
    return seats


def electos_desde_dhondt(
    df_raw: pd.DataFrame,
    col_lista: str,
    col_candidato: str,
    col_partido: str,
    col_votos: str,
    n_escanos: int,
    col_subpacto: str | None = None,
) -> pd.DataFrame:
    """
    Chilean two-level D'Hondt:
      1. D'Hondt among LISTAS → seats per lista.
      2. If col_subpacto given: D'Hondt among SUBPACTOS within each lista → seats per subpacto.
      3. Within each (lista, subpacto), top vote-getters win the seats.
    """
    if n_escanos <= 0 or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    df[col_votos] = pd.to_numeric(df[col_votos], errors="coerce").fillna(0)

    # Level 1: D'Hondt among listas
    lista_votos = df.groupby(col_lista)[col_votos].sum().to_dict()
    seats_per_lista = dhondt(lista_votos, n_escanos)

    rows = []
    for lista, n_lista_seats in seats_per_lista.items():
        df_lista = df[df[col_lista] == lista]

        if col_subpacto and col_subpacto in df.columns:
            # Fill NaN subpacto with partido so those rows aren't dropped from groupby
            df_lista = df_lista.copy()
            df_lista[col_subpacto] = df_lista[col_subpacto].fillna(df_lista[col_partido])
            # Level 2: D'Hondt among subpactos within this lista
            subpacto_votos = df_lista.groupby(col_subpacto)[col_votos].sum().to_dict()
            seats_per_sub = dhondt(subpacto_votos, n_lista_seats)

            for subpacto, n_sub_seats in seats_per_sub.items():
                df_sub = df_lista[df_lista[col_subpacto] == subpacto]
                cand_votos = (
                    df_sub.groupby([col_candidato, col_partido])[col_votos]
                    .sum().reset_index()
                    .sort_values(col_votos, ascending=False)
                )
                for _, r in cand_votos.head(n_sub_seats).iterrows():
                    rows.append({
                        "lista":       str(lista),
                        "candidato":   normaliza_texto(str(r[col_candidato])),
                        "partido":     normaliza_texto(str(r[col_partido])),
                        "votos_total": float(r[col_votos]),
                    })
        else:
            # No subpacto: top vote-getters within lista
            cand_votos = (
                df_lista.groupby([col_candidato, col_partido])[col_votos]
                .sum().reset_index()
                .sort_values(col_votos, ascending=False)
            )
            for _, r in cand_votos.head(n_lista_seats).iterrows():
                rows.append({
                    "lista":       str(lista),
                    "candidato":   normaliza_texto(str(r[col_candidato])),
                    "partido":     normaliza_texto(str(r[col_partido])),
                    "votos_total": float(r[col_votos]),
                })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Alcalde
# ---------------------------------------------------------------------------

def build_alcalde(src: Path) -> pd.DataFrame:
    print("  Cargando alcaldes...")
    if src.suffix == ".xlsx":
        df = pd.read_excel(src)
        df.columns = df.columns.str.strip().str.upper()
    else:
        df = pd.read_csv(src, encoding="utf-8", sep=";", on_bad_lines="skip")
        df.columns = df.columns.str.strip().str.upper()

    df["VOTOS"] = pd.to_numeric(df["VOTOS"], errors="coerce").fillna(0)
    df["CANDIDATO"] = (
        df["NOMBRES"].fillna("").astype(str).str.strip() + " " +
        df["PRIMER APELLIDO"].fillna("").astype(str).str.strip() + " " +
        df["SEGUNDO APELLIDO"].fillna("").astype(str).str.strip()
    ).str.replace(r"\s+", " ", regex=True).str.strip()

    agg = (
        df.groupby(["COMUNA", "CANDIDATO", "PARTIDO"])["VOTOS"]
        .sum().reset_index()
    )
    # Top 1 per commune
    idx = agg.groupby("COMUNA")["VOTOS"].idxmax()
    winners = agg.loc[idx].copy()
    winners["comuna_norm"] = winners["COMUNA"].apply(normaliza_texto)
    winners["candidato"]   = winners["CANDIDATO"].apply(normaliza_texto)
    winners["partido"]     = winners["PARTIDO"].apply(normaliza_texto)
    winners["lista"]       = ""
    winners["votos_total"] = winners["VOTOS"].astype(float)
    return winners[["comuna_norm", "candidato", "partido", "lista", "votos_total"]]


# ---------------------------------------------------------------------------
# Concejal
# ---------------------------------------------------------------------------

def compute_n_concejales(dipu_path: Path) -> dict[str, int]:
    """
    Derive commune padron from Dipu25.csv (electores per local, deduplicated).
    Thresholds per Ley 18.695 Art. 72:
      <= 15,000  → 6 concejales
      <= 70,000  → 8 concejales
      >  70,000  → 10 concejales
    """
    print("  Calculando padrón por comuna desde Dipu25.csv...")
    chunks = []
    for chunk in pd.read_csv(
        dipu_path, sep=";", encoding="utf-8",
        usecols=["id_local", "id_comuna", "comuna", "electores"],
        chunksize=200_000, on_bad_lines="skip",
    ):
        chunks.append(chunk.drop_duplicates("id_local"))
    df = pd.concat(chunks, ignore_index=True).drop_duplicates("id_local")
    df["electores"] = pd.to_numeric(df["electores"], errors="coerce").fillna(0)
    padron = df.groupby("comuna")["electores"].sum()

    n_map: dict[str, int] = {}
    for comuna, electores in padron.items():
        key = normaliza_texto(str(comuna))
        if electores <= 15_000:
            n = 6
        elif electores <= 70_000:
            n = 8
        else:
            n = 10
        n_map[key] = n
    return n_map


def build_concejal(src: Path, n_map: dict[str, int]) -> pd.DataFrame:
    print("  Procesando concejales (D'Hondt por lista)...")
    comunas_seen: set[str] = set()
    rows_all: list[dict] = []

    for chunk in pd.read_csv(
        src, sep=";", encoding="utf-8",
        chunksize=200_000, on_bad_lines="skip",
    ):
        chunk.columns = chunk.columns.str.strip().str.upper()
        chunk["CANDIDATO"] = (
            chunk["NOMBRES"].fillna("").astype(str).str.strip() + " " +
            chunk["PRIMER APELLIDO"].fillna("").astype(str).str.strip() + " " +
            chunk["SEGUNDO APELLIDO"].fillna("").astype(str).str.strip()
        ).str.replace(r"\s+", " ", regex=True).str.strip()
        chunk["VOTOS"] = pd.to_numeric(chunk["VOTOS"], errors="coerce").fillna(0)
        if "SUBPACTO" not in chunk.columns:
            chunk["SUBPACTO"] = ""

        for comuna_raw, grp in chunk.groupby("COMUNA"):
            comuna_norm = normaliza_texto(str(comuna_raw))
            if comuna_norm in comunas_seen:
                continue
            grp = grp.copy()
            grp["_COMUNA_NORM"] = comuna_norm
            rows_all.append(grp[["_COMUNA_NORM", "LISTA", "SUBPACTO", "CANDIDATO", "PARTIDO", "VOTOS"]])

    if not rows_all:
        return pd.DataFrame()

    df = pd.concat(rows_all, ignore_index=True)

    result_rows: list[dict] = []
    for comuna_norm, grp in df.groupby("_COMUNA_NORM"):
        n = n_map.get(comuna_norm, 8)  # fallback 8
        electos = electos_desde_dhondt(
            grp, "LISTA", "CANDIDATO", "PARTIDO", "VOTOS", n, col_subpacto="SUBPACTO"
        )
        if electos.empty:
            continue
        electos["comuna_norm"] = comuna_norm
        result_rows.append(electos)

    if not result_rows:
        return pd.DataFrame()
    out = pd.concat(result_rows, ignore_index=True)
    return out[["comuna_norm", "candidato", "partido", "lista", "votos_total"]]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def build_core(src: Path) -> pd.DataFrame:
    print("  Procesando cores (D'Hondt por lista, nivel circunscripcion)...")
    rows_all: list[pd.DataFrame] = []

    for chunk in pd.read_csv(
        src, sep=";", encoding="utf-8",
        chunksize=200_000, on_bad_lines="skip",
    ):
        chunk.columns = chunk.columns.str.strip().str.upper()
        chunk["CANDIDATO"] = (
            chunk["NOMBRES"].fillna("").astype(str).str.strip() + " " +
            chunk["PRIMER APELLIDO"].fillna("").astype(str).str.strip() + " " +
            chunk["SEGUNDO APELLIDO"].fillna("").astype(str).str.strip()
        ).str.replace(r"\s+", " ", regex=True).str.strip()
        chunk["VOTOS"] = pd.to_numeric(chunk["VOTOS"], errors="coerce").fillna(0)
        if "SUBPACTO" not in chunk.columns:
            chunk["SUBPACTO"] = ""
        rows_all.append(chunk[["CIRCUNSCRIPCION PROVINCIAL", "COMUNA", "LISTA",
                                "SUBPACTO", "CANDIDATO", "PARTIDO", "VOTOS"]])

    if not rows_all:
        return pd.DataFrame()

    df = pd.concat(rows_all, ignore_index=True)
    df["CIRC_NORM"] = df["CIRCUNSCRIPCION PROVINCIAL"].apply(
        lambda x: normaliza_texto(str(x)) if pd.notna(x) else ""
    )
    df["COMUNA_NORM"] = df["COMUNA"].apply(
        lambda x: normaliza_texto(str(x)) if pd.notna(x) else ""
    )

    # Mapping circunscripcion → communes it contains
    circ_to_comunas: dict[str, set[str]] = {}
    for circ, grp in df.groupby("CIRC_NORM"):
        circ_to_comunas[circ] = set(grp["COMUNA_NORM"].unique())

    result_rows: list[pd.DataFrame] = []
    for circ_norm, grp in df.groupby("CIRC_NORM"):
        if not circ_norm:
            continue
        n = CORE_N.get(circ_norm)
        if n is None:
            print(f"    AVISO: circunscripcion '{circ_norm}' sin N definido — usando 5")
            n = 5
        electos = electos_desde_dhondt(
            grp, "LISTA", "CANDIDATO", "PARTIDO", "VOTOS", n, col_subpacto="SUBPACTO"
        )
        if electos.empty:
            continue
        # Replicate for each commune in the circunscripcion
        for comuna_norm in circ_to_comunas.get(circ_norm, set()):
            e = electos.copy()
            e["comuna_norm"] = comuna_norm
            result_rows.append(e)

    if not result_rows:
        return pd.DataFrame()
    out = pd.concat(result_rows, ignore_index=True)
    return out[["comuna_norm", "candidato", "partido", "lista", "votos_total"]]


# ---------------------------------------------------------------------------
# Diputado
# ---------------------------------------------------------------------------

def build_diputado(src: Path) -> pd.DataFrame:
    print("  Procesando diputados (D'Hondt por pacto, nivel distrito)...")
    rows_all: list[pd.DataFrame] = []

    for chunk in pd.read_csv(
        src, sep=";", encoding="utf-8",
        chunksize=200_000, on_bad_lines="skip",
    ):
        chunk.columns = chunk.columns.str.strip().str.upper()
        chunk["VOTOS"] = pd.to_numeric(chunk["VOTOS"], errors="coerce").fillna(0)
        chunk["ID_DISTRITO"] = pd.to_numeric(chunk["ID_DISTRITO"], errors="coerce")
        rows_all.append(chunk[["ID_DISTRITO", "COMUNA", "ID_PACTO", "PACTO",
                                "CANDIDATO", "PARTIDO", "VOTOS"]])

    if not rows_all:
        return pd.DataFrame()

    df = pd.concat(rows_all, ignore_index=True)
    df["COMUNA_NORM"] = df["COMUNA"].apply(
        lambda x: normaliza_texto(str(x)) if pd.notna(x) else ""
    )

    # Mapping district → communes
    dist_to_comunas: dict[int, set[str]] = {}
    for did, grp in df.groupby("ID_DISTRITO"):
        dist_to_comunas[int(did)] = set(grp["COMUNA_NORM"].unique())

    result_rows: list[pd.DataFrame] = []
    for did, grp in df.groupby("ID_DISTRITO"):
        did_int = int(did)
        # SERVEL encodes district IDs as 6001-6028; strip prefix to get 1-28
        did_key = did_int % 1000 if did_int > 100 else did_int
        n = DIPUTADO_N.get(did_key)
        if n is None:
            print(f"    AVISO: distrito {did_int} sin N definido — usando 3")
            n = 3
        # D'Hondt: pacto → partido (sub-level) → top individual vote-getter
        electos = electos_desde_dhondt(
            grp, "ID_PACTO", "CANDIDATO", "PARTIDO", "VOTOS", n, col_subpacto="PARTIDO"
        )
        if electos.empty:
            continue
        # Replicate for each commune in the district
        for comuna_norm in dist_to_comunas.get(did_int, set()):
            e = electos.copy()
            e["comuna_norm"] = comuna_norm
            result_rows.append(e)

    if not result_rows:
        return pd.DataFrame()
    out = pd.concat(result_rows, ignore_index=True)
    out = out.rename(columns={"lista": "pacto"})
    out["lista"] = out["pacto"].astype(str)
    return out[["comuna_norm", "candidato", "partido", "lista", "votos_total"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(cargos: list[str] | None = None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    target = cargos or ["alcalde", "concejal", "core", "diputado"]

    if "alcalde" in target:
        src = RAW_DIR / "Muni24.xlsx"
        print("\n[ALCALDE]")
        if src.exists():
            df = build_alcalde(src)
            _save(df, "alcalde")
        else:
            print(f"  {src.name} no encontrado")

    if "concejal" in target:
        src_conc  = RAW_DIR / "Concejales24.txt"
        src_dipu  = RAW_DIR / "Dipu25.csv"
        print("\n[CONCEJAL]")
        if src_conc.exists() and src_dipu.exists():
            n_map = compute_n_concejales(src_dipu)
            df = build_concejal(src_conc, n_map)
            _save(df, "concejal")
        else:
            print("  Archivos fuente no encontrados")

    if "core" in target:
        src = RAW_DIR / "Cores24.txt"
        print("\n[CORE]")
        if src.exists():
            df = build_core(src)
            _save(df, "core")
        else:
            print(f"  {src.name} no encontrado")

    if "diputado" in target:
        src = RAW_DIR / "Dipu25.csv"
        print("\n[DIPUTADO]")
        if src.exists():
            df = build_diputado(src)
            _save(df, "diputado")
        else:
            print(f"  {src.name} no encontrado")

    print("\nDone.")


def _save(df: pd.DataFrame, cargo: str):
    if df is None or df.empty:
        print(f"  Sin datos para {cargo}")
        return
    path = OUT_DIR / f"{cargo}.parquet"
    df.to_parquet(path, index=False)
    n_electos = len(df)
    n_comunas = df["comuna_norm"].nunique()
    print(f"  Guardado: {n_electos:,} filas ({n_comunas} comunas) -> {path.name}")
    # Quick validation
    if "candidato" in df.columns:
        print(f"  Candidatos únicos: {df['candidato'].nunique()}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Compute D'Hondt elected candidates."
    )
    parser.add_argument("--cargos", nargs="*",
                        choices=["alcalde", "concejal", "core", "diputado"])
    args = parser.parse_args()
    main(cargos=args.cargos)
