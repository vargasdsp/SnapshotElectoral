"""
Step 1: Process TODOSLOCALES.csv -> locales.parquet

Reads polling places with their coordinates and standardizes names.
Real schema (verified via inspect):
  nombre_estandar, variantes, comuna, region, direccion_full, Latitude, Longitude

Coordinates use dots as thousand separators (e.g. '-236.509.279' = -23.6509279).
normalize_coord() fixes this.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from pathlib import Path
from utils import normaliza_texto, canonizar_local, normalize_coord

OUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOCALES_FILE = Path(__file__).parent.parent / "TODOSLOCALES.csv"


def main():
    print(f"Loading {LOCALES_FILE.name}...")
    # Try utf-8 first, fall back to latin-1
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(
                LOCALES_FILE, encoding=enc, low_memory=False,
                dtype={"Latitude": str, "Longitude": str},
            )
            print(f"  Loaded {len(df):,} rows with encoding={enc!r}")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError("Could not read TODOSLOCALES.csv with any encoding")

    print(f"  Columns: {df.columns.tolist()}")

    df = df.rename(columns={
        "nombre_estandar": "local_votacion_raw",
        "Latitude":  "lat_raw",
        "Longitude": "lon_raw",
    })

    df["lat"] = df["lat_raw"].apply(normalize_coord)
    df["lon"] = df["lon_raw"].apply(normalize_coord)

    print(f"  Coords sample: lat={df['lat'].head(3).tolist()}, lon={df['lon'].head(3).tolist()}")
    print(f"  Coord ranges: lat [{df['lat'].min():.4f}, {df['lat'].max():.4f}], "
          f"lon [{df['lon'].min():.4f}, {df['lon'].max():.4f}]")

    mask = (
        df["lat"].between(-56, -17) &
        df["lon"].between(-76, -65)
    )
    invalid = (~mask).sum()
    if invalid > 0:
        print(f"  Warning: {invalid} rows with invalid coordinates - dropped")
    df = df[mask].copy()

    df["local_norm"]  = df["local_votacion_raw"].apply(normaliza_texto)
    df["local_canon"] = df["local_norm"].apply(canonizar_local)
    df["comuna_norm"] = df["comuna"].apply(normaliza_texto)

    # Add variantes as additional matching keys (concejales/cores use raw names)
    df["variantes_norm"] = df["variantes"].fillna("").apply(
        lambda s: "|".join(normaliza_texto(v.strip()) for v in str(s).split("|"))
    )

    out_path = OUT_DIR / "locales.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved {len(df):,} locales -> {out_path}")
    print(f"  Communes covered: {df['comuna_norm'].nunique()}")


if __name__ == "__main__":
    main()
