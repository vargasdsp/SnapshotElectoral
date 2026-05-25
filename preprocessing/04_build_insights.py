"""
Step 4: Build insights_alcaldes.parquet from InsightsAlcaldes25.csv.

Adds political metadata per alcalde 2024 (reelecto/nuevo, ex-militancia, cupo)
and computes `sensibilidad_real` reclassifying independents by their previous
militancy or by the cupo that elected them.

Output: data/processed/insights_alcaldes.parquet
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from pathlib import Path
from utils import normaliza_texto

RAW_FILE = Path(__file__).parent.parent / "InsightsAlcaldes25.csv"
OUT_DIR  = Path(__file__).parent.parent / "data" / "processed"
OUT_PATH = OUT_DIR / "insights_alcaldes.parquet"

# Vocabulario específico del CSV de insights.
# Mapea tokens normalizados (uppercase, sin tildes) a sensibilidad política.
# Cubre tanto militancias formales como las versiones largas que aparecen en el CSV.
PARTIDO_A_SENSIBILIDAD = {
    # Izquierda
    "PC": "izquierda",
    "PCCH": "izquierda",
    "PARTIDO COMUNISTA": "izquierda",
    "PARTIDO COMUNISTA DE CHILE": "izquierda",
    "FA": "izquierda",
    "FRENTE AMPLIO": "izquierda",
    "CONVERGENCIA SOCIAL": "izquierda",
    "REVOLUCION DEMOCRATICA": "izquierda",
    "ACCION HUMANISTA": "izquierda",
    "FRVS": "izquierda",
    "FEDERACION REGIONALISTA VERDE SOCIAL": "izquierda",

    # Centroizquierda
    "PS": "centroizquierda",
    "PARTIDO SOCIALISTA": "centroizquierda",
    "PARTIDO SOCIALISTA DE CHILE": "centroizquierda",
    "PPD": "centroizquierda",
    "PARTIDO POR LA DEMOCRACIA": "centroizquierda",
    "PR": "centroizquierda",
    "PRSD": "centroizquierda",
    "PARTIDO RADICAL": "centroizquierda",
    "PARTIDO RADICAL DE CHILE": "centroizquierda",
    "PDC": "centroizquierda",
    "DC": "centroizquierda",
    "PARTIDO DEMOCRATA CRISTIANO": "centroizquierda",
    "DEMOCRACIA CRISTIANA": "centroizquierda",

    # Centro
    "PL": "centro",
    "PARTIDO LIBERAL": "centro",
    "AMARILLOS": "centro",
    "AMARILLOS POR CHILE": "centro",

    # Centroderecha
    "EVO": "centroderecha",
    "EVOPOLI": "centroderecha",
    "EVOLUCION POLITICA": "centroderecha",
    "DEMOCRATAS": "centroderecha",

    # Derecha
    "UDI": "derecha",
    "UNION DEMOCRATA INDEPENDIENTE": "derecha",
    "UNION DEMOCRATICA INDEPENDIENTE": "derecha",
    "RN": "derecha",
    "RENOVACION NACIONAL": "derecha",
    "PARTIDO RENOVACION NACIONAL": "derecha",
    "REP": "derecha",
    "REPUBLICANO": "derecha",
    "PARTIDO REPUBLICANO": "derecha",
    "PARTIDO REPUBLICANO DE CHILE": "derecha",
    "PNL": "derecha",
    "PARTIDO NACIONAL LIBERTARIO": "derecha",
    "PLR": "derecha",

    # Independiente puro o sin información suficiente
    "IND": "independiente",
    "INDEPENDIENTE": "independiente",
    "FRENTE REGIONAL": "independiente",
}


def _is_independiente_token(militancia_norm: str) -> bool:
    """True si la militancia formal es algún tipo de independiente."""
    if not militancia_norm:
        return True
    return militancia_norm.startswith("INDEPENDIENTE")


def infer_sensibilidad(token: str) -> str | None:
    """Devuelve la sensibilidad mapeada para un token (None si no se reconoce)."""
    if not isinstance(token, str):
        return None
    t = normaliza_texto(token)
    if not t:
        return None
    if t in PARTIDO_A_SENSIBILIDAD:
        return PARTIDO_A_SENSIBILIDAD[t]
    # Coincidencia parcial: cualquier partido cuyo nombre largo contenga el token
    for key, sens in PARTIDO_A_SENSIBILIDAD.items():
        if len(key) > 5 and key in t:
            return sens
    return None


def resolve_sensibilidad(row: pd.Series) -> str:
    """
    Reglas para asignar sensibilidad real al alcalde:
      1. Si Militancia es IND* y hay Antigua Militancia → usa Antigua Militancia.
      2. Si Militancia es IND* y hay CUPO → usa CUPO.
      3. Si Militancia es IND* sin nada más → "independiente".
      4. Si Militancia es partido formal → mapeo directo.
    """
    militancia = normaliza_texto(row.get("Militancia", "") or "")
    antigua    = normaliza_texto(row.get("Antigua Militancia (si es IND)", "") or "")
    cupo       = normaliza_texto(row.get("CUPO", "") or "")

    if _is_independiente_token(militancia):
        if antigua:
            sens = infer_sensibilidad(antigua)
            if sens:
                return sens
        if cupo:
            sens = infer_sensibilidad(cupo)
            if sens:
                return sens
        return "independiente"

    sens = infer_sensibilidad(militancia)
    if sens:
        return sens
    # Último recurso: usar la bancada AchM si existe
    bancada = normaliza_texto(row.get("BANCADA AchM", "") or "")
    sens = infer_sensibilidad(bancada)
    return sens or "independiente"


def main():
    if not RAW_FILE.exists():
        print(f"ERROR: {RAW_FILE} not found")
        return

    print(f"Loading {RAW_FILE.name}...")
    # CSV con encabezados en español incluyendo tildes y caracteres especiales;
    # probamos varios encodings para evitar mojibake en columnas como ¿Nuevo o Reelecto?
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(RAW_FILE, encoding=enc)
            print(f"  Loaded {len(df):,} rows with encoding={enc!r}")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError("Could not read InsightsAlcaldes25.csv")

    print(f"  Columns: {df.columns.tolist()}")

    # Normalizar nombres de columnas: detección flexible
    col_comuna  = next(c for c in df.columns if c.strip().lower() == "comuna")
    col_nombre  = next(c for c in df.columns if c.strip().lower() == "nombre")
    col_pacto   = next((c for c in df.columns if c.strip().lower() == "pacto"), None)
    col_region  = next((c for c in df.columns if "regi" in c.lower()), None)
    col_estado  = next((c for c in df.columns if "nuevo" in c.lower() and "reelecto" in c.lower()), None)
    col_bancada = next((c for c in df.columns if "bancada" in c.lower()), None)
    col_milit   = next(c for c in df.columns if c.strip().lower() == "militancia")
    col_cupo    = next(c for c in df.columns if c.strip().lower() == "cupo")
    col_ex      = next(c for c in df.columns if "antigua" in c.lower())

    out = pd.DataFrame({
        "comuna_norm": df[col_comuna].apply(normaliza_texto),
        "nombre": df[col_nombre].astype(str).str.strip(),
        "pacto": df[col_pacto].astype(str).str.strip() if col_pacto else "",
        "region": df[col_region].astype(str).str.strip() if col_region else "",
        "estado": df[col_estado].astype(str).str.strip().str.upper() if col_estado else "",
        "bancada_achm": df[col_bancada].astype(str).str.strip() if col_bancada else "",
        "militancia": df[col_milit].astype(str).str.strip(),
        "cupo": df[col_cupo].astype(str).str.strip(),
        "antigua_militancia": df[col_ex].astype(str).str.strip(),
    })

    # Limpiar valores tipo "nan"/"#N/A" que pandas convierte en strings
    for c in ("pacto", "region", "estado", "bancada_achm", "cupo", "antigua_militancia"):
        out[c] = out[c].replace({"nan": "", "NaN": "", "#N/A": "", "None": ""})

    # Reclasificar sensibilidad usando antigua militancia / cupo
    out["sensibilidad_real"] = df.apply(resolve_sensibilidad, axis=1)

    # Flag para detectar a quién aplicamos reclasificación (IND con dato extra)
    out["es_independiente_reclasificado"] = (
        out["militancia"].str.upper().str.startswith("INDEPENDIENTE") &
        ((out["antigua_militancia"] != "") | (out["cupo"] != ""))
    )

    # Filtrar filas sin comuna (data quality)
    out = out[out["comuna_norm"] != ""].copy()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)

    print(f"\nSaved {len(out):,} insights -> {OUT_PATH}")
    print(f"  Comunas únicas: {out['comuna_norm'].nunique()}")
    print(f"  Reelectos: {(out['estado'].str.startswith('REELECTO')).sum()}")
    print(f"  Nuevos:    {(out['estado'].str.startswith('NUEVO')).sum()}")
    print(f"  IND reclasificados: {out['es_independiente_reclasificado'].sum()}")
    print(f"\n  Distribución sensibilidad_real:")
    print(out["sensibilidad_real"].value_counts().to_string())


if __name__ == "__main__":
    main()
