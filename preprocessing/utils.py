"""
Shared utilities extracted from LA_MAQUINARIA_v3_2.ipynb
"""
from __future__ import annotations
import re
import unicodedata
import numpy as np
import pandas as pd


SENSIBILIDAD_PARTIDOS = {
    "izquierda":       ["PC", "FA", "FREVS", "CONVERGENCIA SOCIAL", "ACCION HUMANISTA"],
    "centroizquierda": ["PS", "PPD", "PL", "PR", "PDC", "PARTIDO SOCIALISTA",
                        "PARTIDO POR LA DEMOCRACIA", "PARTIDO LIBERAL",
                        "PARTIDO RADICAL", "DEMOCRACIA CRISTIANA"],
    "centro":          ["PDC", "DEMOCRACIA CRISTIANA", "IND", "INDEPENDIENTE"],
    "centroderecha":   ["RN", "RENOVACION NACIONAL", "EVO"],
    "derecha":         ["UDI", "UNION DEMOCRATICA INDEPENDIENTE", "RN",
                        "RENOVACION NACIONAL", "REP", "REPUBLICANO", "PLR"],
    "independiente":   ["IND", "INDEPENDIENTE"],
}

CARGO_FUENTE = {
    "concejal": "Concejales24",
    "core":     "Cores24",
    "alcalde":  "Muni24",
    "diputado": "Dipu25",
}

CARGO_LABEL = {
    "concejal": "Concejal",
    "core":     "Consejero Regional (CORE)",
    "alcalde":  "Alcalde",
    "diputado": "Diputado",
}


def normaliza_texto(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # Source files often have mangled encodings where Ñ became U+FFFD.
    # In Chilean place names Ñ is by far the most common non-ASCII letter,
    # so treat the replacement character as N before stripping.
    s = s.replace("�", "N").replace("?", "")
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.upper().strip()


def variantes_comuna(nombre: str):
    base = normaliza_texto(nombre)
    variants = {base}
    reemplazos = {
        "A": ["A", "Á"], "E": ["E", "É"], "I": ["I", "Í"],
        "O": ["O", "Ó"], "U": ["U", "Ú"],
    }
    for orig, alts in reemplazos.items():
        for alt in alts:
            variants.add(base.replace(orig, alt))
    return list(variants)


def filtrar_comuna(df: pd.DataFrame, col: str, comuna: str) -> pd.DataFrame:
    target = normaliza_texto(comuna)
    normalized = df[col].astype(str).apply(normaliza_texto)
    return df[normalized == target].copy()


def canonizar_local(nombre: str) -> str:
    if not isinstance(nombre, str):
        return ""
    s = normaliza_texto(nombre)
    # Strip sub-sede suffix used in Muni24/Cores ("L1", "L2", "L3", "LOCAL 1", etc.)
    s = re.sub(r"\s+L\s*\d+\s*$", "", s)
    s = re.sub(r"\s+LOCAL\s*\d+\s*$", "", s)
    s = re.sub(r"\s+SEDE\s*\d+\s*$", "", s)
    prefijos = [
        "ESCUELA", "COLEGIO", "LICEO", "INSTITUTO", "CENTRO",
        "GIMNASIO", "SALA", "JUNTA", "CLUB", "PARROQUIA",
    ]
    for p in prefijos:
        if s.startswith(p + " "):
            s = s[len(p):].strip()
    # "NA7" used in Muni24 is the mangled "N°7" — strip the "NA" prefix on digits.
    s = re.sub(r"\bNA(\d+)\b", r"N\1", s)
    s = re.sub(r"\bN[°oO]?\s*\d+\b", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_coord(val) -> float:
    """
    Fix Chilean coords stored with garbage dots inserted every 3 chars.
    Examples:
        '-236.509.279'           -> -23.6509279
        '-7.039.750.219.999.990' -> -70.3975021999999
    Strategy: strip all non-digit chars, place decimal after digit 2 (Chile always uses 2-digit integer parts for lat/lon).
    """
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    if s in ("", "nan", "NaN", "None"):
        return np.nan
    sign = -1 if s.startswith("-") else 1
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 3:
        try:
            return sign * float(digits)
        except ValueError:
            return np.nan
    intpart = digits[:2]
    decpart = digits[2:]
    try:
        return sign * float(f"{intpart}.{decpart}")
    except ValueError:
        return np.nan


def to_numeric_cl(series: pd.Series) -> pd.Series:
    """
    Convert series to numeric, handling Chilean formatting ('1.234,56') only when
    detected. If values already parse cleanly as plain numbers, leave them alone.
    """
    direct = pd.to_numeric(series, errors="coerce")
    if direct.notna().sum() >= len(series) * 0.95:
        return direct.fillna(0)
    # Fall back to CL-formatted parsing
    s = series.astype(str).str.strip()
    has_comma = s.str.contains(",", regex=False)
    s = s.where(~has_comma,
                s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce").fillna(0)
