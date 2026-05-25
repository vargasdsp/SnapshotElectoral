"""
Step 2: Build manzana->local weight tables per commune.

Uses centroid-based method (Method 2 from notebook):
  - Compute manzana centroids from geometry
  - BallTree to assign each manzana to nearest polling place
  - peso = 1.0 (each manzana belongs to exactly one local)

No geocoding of individual voters required.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from sklearn.neighbors import BallTree
from utils import normaliza_texto, variantes_comuna

RAW_DIR    = Path(__file__).parent.parent
PROC_DIR   = Path(__file__).parent.parent / "data" / "processed"
PESOS_DIR  = PROC_DIR / "pesos"
GEO_DIR    = PROC_DIR / "geojson"
PESOS_DIR.mkdir(parents=True, exist_ok=True)
GEO_DIR.mkdir(parents=True, exist_ok=True)

MANZANAS_FILE = RAW_DIR / "manzanas_nacional.parquet"
LOCALES_FILE  = PROC_DIR / "locales.parquet"


def build_pesos_for_commune(comuna: str, manzanas_gdf: gpd.GeoDataFrame,
                             locales_df: pd.DataFrame) -> pd.DataFrame | None:
    variants = [v.upper() for v in variantes_comuna(comuna)]

    # Filter manzanas: column is "COMUNA"
    mz_col = "COMUNA" if "COMUNA" in manzanas_gdf.columns else next(
        (c for c in manzanas_gdf.columns if "COMUN" in c.upper()), None
    )
    if mz_col:
        comuna_normalized = manzanas_gdf[mz_col].astype(str).apply(normaliza_texto)
        mz = manzanas_gdf[comuna_normalized.isin(variants)].copy()
    else:
        print(f"  Warning: no commune column in manzanas - using all rows")
        mz = manzanas_gdf.copy()

    if len(mz) == 0:
        print(f"  No manzanas found for {comuna}")
        return None

    # Filter locales
    loc = locales_df[locales_df["comuna_norm"].isin(variants)].copy()
    if len(loc) == 0:
        print(f"  No locales found for {comuna}")
        return None

    print(f"  {len(mz)} manzanas, {len(loc)} locales")

    # Compute manzana centroids (reproject to 4326 if needed)
    if mz.crs and mz.crs.to_epsg() != 4326:
        mz = mz.to_crs(epsg=4326)
    centroids = mz.geometry.centroid

    # BallTree: assign each manzana centroid to nearest local
    loc_coords = np.radians(loc[["lat", "lon"]].values)
    tree = BallTree(loc_coords, metric="haversine")

    mz_coords = np.radians(
        np.column_stack([centroids.y.values, centroids.x.values])
    )
    distances, indices = tree.query(mz_coords, k=1)

    mz = mz.copy()
    mz["local_norm"]     = loc.iloc[indices.flatten()]["local_norm"].values
    mz["local_canon"]    = loc.iloc[indices.flatten()]["local_canon"].values
    mz["local_lat"]      = loc.iloc[indices.flatten()]["lat"].values
    mz["local_lon"]      = loc.iloc[indices.flatten()]["lon"].values
    mz["dist_local_m"]   = distances.flatten() * 6371000  # meters

    # Peso ponderado por población censal de la manzana.
    # peso(mz) = poblacion(mz) / sum(poblacion de todas las manzanas en su local)
    # Esto distribuye los votos del local proporcionalmente al peso poblacional
    # de cada manzana, no uniformemente. Manzanas con más habitantes reciben más voto.
    pop_col = "n_per" if "n_per" in mz.columns else None
    if pop_col is None:
        print("  Warning: no n_per population column, falling back to uniform weights")
        counts = mz.groupby("local_norm").size().rename("_local_count")
        mz = mz.merge(counts, left_on="local_norm", right_index=True)
        mz["peso"] = 1.0 / mz["_local_count"]
        mz = mz.drop(columns=["_local_count"])
    else:
        mz["_pop"] = pd.to_numeric(mz[pop_col], errors="coerce").fillna(0)
        # Local with zero population gets uniform fallback
        totals = mz.groupby("local_norm")["_pop"].transform("sum")
        counts = mz.groupby("local_norm")["_pop"].transform("size")
        mz["peso"] = np.where(
            totals > 0,
            mz["_pop"] / totals,
            1.0 / counts,
        )
        mz = mz.drop(columns=["_pop"])

    # Detect manzana ID column (real schema uses MANZENT)
    id_col = "MANZENT" if "MANZENT" in mz.columns else None
    if id_col is None:
        id_col = next((c for c in mz.columns if "MANZ" in c.upper() and "ENT" in c.upper()), None)
    if id_col is None:
        id_col = next((c for c in mz.columns if "MANZ" in c.upper() and "ID" in c.upper()), None)
    if id_col is None:
        mz["ID_MANZANA"] = range(len(mz))
        id_col = "ID_MANZANA"

    pesos = mz[[id_col, "local_norm", "local_canon", "local_lat", "local_lon",
                "dist_local_m", "peso"]].copy()
    pesos = pesos.rename(columns={id_col: "ID_MANZANA"})
    pesos["ID_MANZANA"] = pesos["ID_MANZANA"].astype(str)
    return pesos, mz, id_col


def export_geojson(mz: gpd.GeoDataFrame, id_col: str, pesos: pd.DataFrame,
                   out_path: Path):
    # Simplify geometry for web delivery
    mz_4326 = mz.to_crs(epsg=4326) if mz.crs and mz.crs.to_epsg() != 4326 else mz
    mz_simple = mz_4326.copy()
    # More aggressive simplification - geometry detail is unimportant at commune zoom levels
    mz_simple["geometry"] = mz_simple.geometry.simplify(0.0002, preserve_topology=True)

    # Keep only essential columns
    keep = [id_col, "geometry"]
    extra = [c for c in mz_simple.columns if "ELEC" in c.upper() or "POB" in c.upper()]
    keep += extra[:3]
    mz_simple = mz_simple[keep].copy()
    mz_simple = mz_simple.rename(columns={id_col: "ID_MANZANA"})
    mz_simple["ID_MANZANA"] = mz_simple["ID_MANZANA"].astype(str)

    # Merge pesos info
    mz_simple = mz_simple.merge(
        pesos[["ID_MANZANA", "local_norm", "local_canon", "dist_local_m"]],
        on="ID_MANZANA", how="left"
    )

    mz_simple.to_file(out_path, driver="GeoJSON")
    print(f"  GeoJSON saved ({out_path.stat().st_size // 1024} KB)")


def main(comunas: list[str] | None = None):
    print("Loading manzanas_nacional.parquet...")
    manzanas = gpd.read_parquet(MANZANAS_FILE)
    print(f"  Loaded {len(manzanas):,} manzanas, CRS={manzanas.crs}")

    print("Loading locales.parquet...")
    locales = pd.read_parquet(LOCALES_FILE)
    print(f"  Loaded {len(locales):,} locales")

    if comunas is None:
        comunas = locales["comuna_norm"].unique().tolist()
        print(f"  Processing ALL {len(comunas)} communes...")
    else:
        comunas = [normaliza_texto(c) for c in comunas]
        print(f"  Processing {len(comunas)} specified communes...")

    results = []
    for comuna in comunas:
        print(f"\nProcessing: {comuna}")
        result = build_pesos_for_commune(comuna, manzanas, locales)
        if result is None:
            continue
        pesos, mz_filtered, id_col = result

        pesos_path = PESOS_DIR / f"{comuna}.parquet"
        pesos.to_parquet(pesos_path, index=False)

        geo_path = GEO_DIR / f"{comuna}.geojson"
        export_geojson(mz_filtered, id_col, pesos, geo_path)

        results.append({"comuna": comuna, "manzanas": len(pesos),
                        "locales": pesos["local_norm"].nunique()})

    summary = pd.DataFrame(results)
    summary.to_csv(PROC_DIR / "communes_index.csv", index=False)
    print(f"\nDone. Processed {len(results)} communes.")
    print(summary)


if __name__ == "__main__":
    import sys
    target = sys.argv[1:] if len(sys.argv) > 1 else None
    main(target)
