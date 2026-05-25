"""
Step 5: Build distritos.parquet from Dipu25.csv.

Crea un mapping (region, distrito_id, distrito_nombre) -> list[comunas]
para que el wizard pueda mostrar el flujo Region -> Distrito -> Snapshot
cuando el cargo elegido es diputado.

Output: data/processed/distritos.parquet con columnas
  region_norm, distrito_id, distrito, comuna_norm
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from pathlib import Path
from utils import normaliza_texto

RAW_FILE = Path(__file__).parent.parent / "Dipu25.csv"
OUT_DIR  = Path(__file__).parent.parent / "data" / "processed"
OUT_PATH = OUT_DIR / "distritos.parquet"


def main():
    if not RAW_FILE.exists():
        print(f"ERROR: {RAW_FILE} not found")
        return

    print(f"Loading {RAW_FILE.name}...")
    # Solo necesitamos las columnas de region/distrito/comuna; cargamos eso y
    # deduplicamos. El archivo es grande (~hundreds of MB) pero estas tres
    # columnas en chunks son livianas.
    keep = ["region", "id_distrito", "distrito", "comuna"]
    chunks = []
    for chunk in pd.read_csv(
        RAW_FILE, sep=";", encoding="utf-8",
        usecols=keep, chunksize=200_000, low_memory=False,
        on_bad_lines="skip",
    ):
        chunks.append(chunk.drop_duplicates())
    df = pd.concat(chunks, ignore_index=True).drop_duplicates()
    print(f"  {len(df):,} pares únicos region/distrito/comuna tras dedupe")

    df["region_norm"] = df["region"].apply(normaliza_texto)
    df["comuna_norm"] = df["comuna"].apply(normaliza_texto)
    df["distrito_id"] = pd.to_numeric(df["id_distrito"], errors="coerce").astype("Int64")

    out = df[["region_norm", "distrito_id", "distrito", "comuna_norm"]].copy()
    out = out.dropna(subset=["distrito_id"]).drop_duplicates()
    out = out.sort_values(["region_norm", "distrito_id", "comuna_norm"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)

    print(f"\nSaved {len(out):,} mappings -> {OUT_PATH}")
    print(f"  Regiones: {out['region_norm'].nunique()}")
    print(f"  Distritos: {out['distrito_id'].nunique()}")
    print(f"  Comunas: {out['comuna_norm'].nunique()}")
    print(f"\n  Sample:")
    print(out.head(10).to_string())


if __name__ == "__main__":
    main()
