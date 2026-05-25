from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from ..services.query import get_geojson, get_available_comunas, get_distrito_geojson

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("/distrito/{distrito_id}")
def get_distrito_geo(
    distrito_id: int,
    comuna: Optional[str] = Query(None, description="Opcional: solo esta comuna del distrito"),
):
    """GeoJSON unido de las comunas de un distrito (o de una sola si comuna está)."""
    geo = get_distrito_geojson(distrito_id, comuna_filter=comuna)
    if geo is None:
        raise HTTPException(404, f"GeoJSON no disponible para distrito {distrito_id}"
                                  + (f" / comuna '{comuna}'" if comuna else ""))
    return JSONResponse(content=geo, media_type="application/geo+json")


@router.get("/{comuna}")
def get_commune_geojson(comuna: str):
    available = get_available_comunas()
    if comuna not in available:
        raise HTTPException(404, f"No GeoJSON for '{comuna}'")
    geo = get_geojson(comuna)
    if geo is None:
        raise HTTPException(404, f"GeoJSON file not found for '{comuna}'")
    return JSONResponse(content=geo, media_type="application/geo+json")
