from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..services.query import (
    get_snapshot_data, get_available_comunas,
    get_candidatos, get_autoridad_snapshot,
    get_distrito_snapshot, get_distrito_info,
    get_candidatos_distrito, get_autoridad_distrito_snapshot,
)

router = APIRouter(prefix="/api/electoral", tags=["electoral"])

VALID_CARGOS        = {"concejal", "core", "alcalde", "diputado"}
VALID_SENSIBILIDADES = {
    "izquierda", "centroizquierda", "centro",
    "centroderecha", "derecha", "independiente"
}


@router.get("/snapshot")
def get_snapshot(
    comuna: str = Query(..., description="Nombre de la comuna (normalizado)"),
    cargo: str  = Query(..., description="concejal|core|alcalde|diputado"),
    sensibilidad: str = Query(..., description="izquierda|centroizquierda|..."),
    partido: Optional[str] = Query(None, description="Filtrar por partido específico (opcional)"),
):
    if cargo not in VALID_CARGOS:
        raise HTTPException(422, f"Invalid cargo. Must be one of: {VALID_CARGOS}")
    if sensibilidad not in VALID_SENSIBILIDADES:
        raise HTTPException(422, f"Invalid sensibilidad. Must be one of: {VALID_SENSIBILIDADES}")

    available = get_available_comunas()
    if comuna not in available:
        raise HTTPException(404, f"No processed data for commune '{comuna}'. "
                                 f"Run the preprocessing pipeline first.")

    result = get_snapshot_data(comuna, cargo, sensibilidad, partido=partido)
    if result is None:
        raise HTTPException(404, f"No data for {cargo} in {comuna}. "
                                 f"Check if this cargo was processed.")
    return result


@router.get("/candidatos")
def list_candidatos(
    comuna: str = Query(..., description="Nombre de la comuna (normalizado)"),
    cargo: str  = Query(..., description="concejal|core|alcalde|diputado"),
    electos_only: bool = Query(False, description="Solo autoridades electas"),
):
    if cargo not in VALID_CARGOS:
        raise HTTPException(422, f"Invalid cargo. Must be one of: {VALID_CARGOS}")
    candidatos = get_candidatos(comuna, cargo, electos_only=electos_only)
    if candidatos is None:
        raise HTTPException(404, f"No data for {cargo} in {comuna}.")
    return {"comuna": comuna, "cargo": cargo, "candidatos": candidatos}


@router.get("/compare")
def compare_autoridades(
    comuna: str = Query(...),
    cargo: str  = Query(...),
    candidato_a: str = Query(...),
    candidato_b: str = Query(...),
):
    if cargo not in VALID_CARGOS:
        raise HTTPException(422, f"Invalid cargo")
    a = get_autoridad_snapshot(comuna, cargo, candidato_a)
    b = get_autoridad_snapshot(comuna, cargo, candidato_b)
    if a is None or b is None:
        raise HTTPException(404, "Uno o más candidatos no fueron encontrados")
    return {"comuna": comuna, "cargo": cargo, "a": a, "b": b}


@router.get("/candidatos-distrito")
def list_candidatos_distrito(
    distrito_id: int = Query(...),
    electos_only: bool = Query(False),
):
    info = get_distrito_info(distrito_id)
    if not info:
        raise HTTPException(404, f"Distrito {distrito_id} no encontrado")
    candidatos = get_candidatos_distrito(distrito_id, electos_only=electos_only)
    if candidatos is None:
        raise HTTPException(404, f"Sin datos de diputado para distrito {distrito_id}")
    return {
        "distrito_id": distrito_id,
        "distrito": info["distrito"],
        "candidatos": candidatos,
    }


@router.get("/snapshot-autoridad-distrito")
def get_snapshot_autoridad_distrito(
    distrito_id: int = Query(...),
    candidato: str = Query(...),
    comuna: Optional[str] = Query(None, description="Filtrar a una comuna del distrito"),
):
    info = get_distrito_info(distrito_id)
    if not info:
        raise HTTPException(404, f"Distrito {distrito_id} no encontrado")
    if comuna and comuna not in info["comunas"]:
        raise HTTPException(404, f"Comuna '{comuna}' no pertenece al distrito")
    result = get_autoridad_distrito_snapshot(distrito_id, candidato, comuna_filter=comuna)
    if result is None:
        raise HTTPException(404, f"Sin datos para '{candidato}' en distrito {distrito_id}")
    return result


@router.get("/snapshot-distrito")
def get_snapshot_distrito(
    distrito_id: int = Query(..., description="ID numérico del distrito electoral"),
    sensibilidad: str = Query(..., description="izquierda|centroizquierda|..."),
    comuna: Optional[str] = Query(None, description="Opcional: filtrar a una comuna del distrito"),
):
    """Snapshot agregando todas las comunas de un distrito (cargo=diputado).
    Si se pasa `comuna`, restringe el análisis a esa sola comuna del distrito."""
    if sensibilidad not in VALID_SENSIBILIDADES:
        raise HTTPException(422, f"Invalid sensibilidad. Must be one of: {VALID_SENSIBILIDADES}")
    info = get_distrito_info(distrito_id)
    if not info:
        raise HTTPException(404, f"Distrito {distrito_id} no encontrado")
    if comuna and comuna not in info["comunas"]:
        raise HTTPException(404, f"Comuna '{comuna}' no pertenece al distrito {distrito_id}")
    result = get_distrito_snapshot(distrito_id, sensibilidad, comuna_filter=comuna)
    if result is None:
        raise HTTPException(
            404,
            f"No hay datos de diputado procesados para el distrito {distrito_id}. "
            f"Corre el pipeline de votos para sus comunas."
        )
    return result


@router.get("/snapshot-autoridad")
def get_snapshot_autoridad(
    comuna: str = Query(..., description="Nombre de la comuna (normalizado)"),
    cargo: str  = Query(..., description="concejal|core|alcalde|diputado"),
    candidato: str = Query(..., description="Nombre del candidato/autoridad electa"),
):
    if cargo not in VALID_CARGOS:
        raise HTTPException(422, f"Invalid cargo. Must be one of: {VALID_CARGOS}")
    result = get_autoridad_snapshot(comuna, cargo, candidato)
    if result is None:
        raise HTTPException(404, f"No data for '{candidato}' as {cargo} in {comuna}.")
    return result
