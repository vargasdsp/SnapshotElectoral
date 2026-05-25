from fastapi import APIRouter, HTTPException, Query
from ..services.census import get_census_comuna, get_census_manzanas, VALID_MAP_COLS

router = APIRouter(prefix="/api/census", tags=["census"])


@router.get("/manzanas/{comuna}")
def get_census_manzanas_endpoint(
    comuna: str,
    variable: str = Query(..., description="Census column name"),
):
    if variable not in VALID_MAP_COLS:
        raise HTTPException(400, f"Variable '{variable}' not allowed. Valid: {sorted(VALID_MAP_COLS)}")
    data = get_census_manzanas(comuna, variable)
    if data is None:
        raise HTTPException(404, f"No census manzana data for '{comuna}'")
    return {"comuna": comuna.upper(), "variable": variable, "manzanas": data}


@router.get("/{comuna}")
def get_census(comuna: str):
    data = get_census_comuna(comuna)
    if data is None:
        raise HTTPException(404, f"No census data for '{comuna}'")
    return data
