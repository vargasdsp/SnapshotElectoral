"""
Inspect raw source files before running the full pipeline.

Prints columns, encoding, sample rows, communa values, etc.
Use this to detect schema mismatches between SCHEMA constants
in 03_build_votos.py and actual file contents.

Usage:
    python preprocessing/inspect_sources.py
    python preprocessing/inspect_sources.py --sample-comuna PENALOLEN
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
from pathlib import Path
import pandas as pd
from utils import normaliza_texto, filtrar_comuna

ROOT = Path(__file__).parent.parent

SOURCES = {
    "Concejales24.txt":     {"sep": ";",  "encoding": "latin-1"},
    "Cores24.txt":          {"sep": ";",  "encoding": "latin-1"},
    "Dipu25.csv":           {"sep": ";",  "encoding": "utf-8"},
    "PRES_LOCALES.csv":     {"sep": ",",  "encoding": "utf-8"},
    "TODOSLOCALES.csv":     {"sep": ",",  "encoding": "latin-1"},
    "Muni24.xlsx":          {"sep": None, "encoding": None},
}


def inspect_file(filename: str, opts: dict, sample_comuna: str | None = None):
    path = ROOT / filename
    print(f"\n{'='*70}")
    print(f"[FILE] {filename}")
    print('='*70)

    if not path.exists():
        print(f"  [ERR] FILE NOT FOUND: {path}")
        return

    size_mb = path.stat().st_size / (1024*1024)
    print(f"  Size: {size_mb:,.1f} MB")

    try:
        if filename.endswith(".xlsx"):
            df = pd.read_excel(path, nrows=500)
        else:
            df = pd.read_csv(
                path, sep=opts["sep"], encoding=opts["encoding"],
                nrows=500, low_memory=False, on_bad_lines="skip",
            )
    except Exception as e:
        print(f"  [ERR] READ ERROR: {e}")
        # Try alternative encodings
        for enc in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            if enc == opts["encoding"]:
                continue
            try:
                df = pd.read_csv(path, sep=opts["sep"], encoding=enc, nrows=10)
                print(f"  [OK] Works with encoding={enc!r}")
                break
            except Exception:
                continue
        return

    print(f"  Rows in sample: {len(df)}")
    print(f"  Columns ({len(df.columns)}):")
    for col in df.columns:
        sample_val = df[col].dropna().head(1).values
        sample_str = str(sample_val[0])[:40] if len(sample_val) else "(empty)"
        print(f"    - {col!r:<40} -> {sample_str!r}")

    # Look for commune column
    comuna_cols = [c for c in df.columns if "COMUN" in c.upper()]
    if comuna_cols:
        col = comuna_cols[0]
        unique_communes = df[col].dropna().astype(str).str.upper().str.strip().unique()
        print(f"\n  Communes in sample (col={col!r}): {len(unique_communes)}")
        print(f"    First 8: {list(unique_communes[:8])}")

        if sample_comuna:
            target = normaliza_texto(sample_comuna)
            filtered = filtrar_comuna(df, col, sample_comuna)
            print(f"\n  Filter test for '{target}': {len(filtered)} rows")
            if len(filtered):
                print(f"    Sample row keys: {list(filtered.iloc[0].to_dict().keys())[:6]}")

    # Coordinate columns
    coord_cols = [c for c in df.columns if any(k in c.upper() for k in ["LAT", "LON", "COORD"])]
    if coord_cols:
        print(f"\n  Coordinate columns found: {coord_cols}")
        for cc in coord_cols:
            vals = pd.to_numeric(df[cc], errors="coerce").dropna()
            if len(vals):
                print(f"    {cc}: range [{vals.min():.4f}, {vals.max():.4f}], n={len(vals)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-comuna", help="Test commune filter on each file")
    args = parser.parse_args()

    print("\n=== INSPECCION DE ARCHIVOS FUENTE ===")
    print(f"   Working dir: {ROOT}")

    for filename, opts in SOURCES.items():
        inspect_file(filename, opts, args.sample_comuna)

    # Manzanas parquet
    print(f"\n{'='*70}")
    print(f"[FILE] manzanas_nacional.parquet")
    print('='*70)
    mz_path = ROOT / "manzanas_nacional.parquet"
    if not mz_path.exists():
        print(f"  [ERR] FILE NOT FOUND: {mz_path}")
    else:
        try:
            import geopandas as gpd
            print(f"  Loading (this may take ~10s)...")
            mz = gpd.read_parquet(mz_path)
            print(f"  Rows: {len(mz):,}")
            print(f"  CRS: {mz.crs}")
            print(f"  Geometry type: {mz.geometry.geom_type.iloc[0]}")
            print(f"  Columns:")
            for col in mz.columns:
                if col == "geometry":
                    continue
                sample = mz[col].dropna().head(1).values
                s = str(sample[0])[:40] if len(sample) else "(empty)"
                print(f"    - {col!r:<40} -> {s!r}")
        except ImportError:
            print("  [WARN] geopandas not installed — skipping")
        except Exception as e:
            print(f"  [ERR] ERROR: {e}")

    print(f"\n{'='*70}")
    print("[OK] Inspección completa.")
    print("  Si alguna columna no coincide con la SCHEMA en 03_build_votos.py,")
    print("  ajústala antes de correr el pipeline.\n")


if __name__ == "__main__":
    main()
