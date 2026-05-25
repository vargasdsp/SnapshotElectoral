from fastapi import APIRouter, HTTPException
from ..services.query import (
    get_available_comunas, get_available_cargos, get_comunas_by_region,
    get_distritos_by_region,
)

router = APIRouter(prefix="/api/communes", tags=["communes"])


@router.get("/")
def list_communes():
    comunas = get_available_comunas()
    return {"comunas": comunas, "total": len(comunas)}


@router.get("/by-region")
def list_communes_by_region():
    grupos = get_comunas_by_region()
    total = sum(len(g["comunas"]) for g in grupos)
    return {"regiones": grupos, "total_comunas": total, "total_regiones": len(grupos)}


@router.get("/distritos-by-region")
def list_distritos_by_region():
    """Devuelve distritos agrupados por región para el flujo de diputado."""
    grupos = get_distritos_by_region()
    total_distritos = sum(len(g["distritos"]) for g in grupos)
    return {"regiones": grupos, "total_distritos": total_distritos}


@router.get("/{comuna}")
def get_commune_info(comuna: str):
    available = get_available_comunas()
    if comuna not in available:
        raise HTTPException(404, f"Commune '{comuna}' not found in processed data")
    cargos = get_available_cargos(comuna)
    return {"comuna": comuna, "cargos": cargos}
