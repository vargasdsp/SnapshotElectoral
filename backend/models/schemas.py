from pydantic import BaseModel
from typing import Optional


class SnapshotRequest(BaseModel):
    comuna: str
    cargo: str      # concejal | core | alcalde | diputado
    sensibilidad: str  # izquierda | centroizquierda | centro | centroderecha | derecha | independiente


class ManzanaFeature(BaseModel):
    id_manzana: str
    voto_pct: float
    voto_abs: float
    total_votos: float
    local_votacion: str
    local_lat: float
    local_lon: float
    dist_local_m: float
    is_fortaleza: bool


class SnapshotStats(BaseModel):
    voto_promedio_pct: float
    total_votos: float
    manzanas_total: int
    manzanas_fortaleza: int
    manzanas_debilidad: int
    locales_ganados: int
    locales_total: int
    top_candidatos: list[dict]
    pres_historico_pct: Optional[float]
    swing: Optional[float]


class SnapshotResponse(BaseModel):
    comuna: str
    cargo: str
    sensibilidad: str
    manzanas: list[ManzanaFeature]
    stats: SnapshotStats
    narrative: str


class ComunaInfo(BaseModel):
    nombre: str
    region: Optional[str]
    manzanas: int
    locales: int


class HealthResponse(BaseModel):
    status: str
    comunas_disponibles: int
    cargos_disponibles: list[str]
