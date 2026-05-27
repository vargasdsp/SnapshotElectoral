"""
Maquinaria Electoral — FastAPI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import communes, electoral, geo, census
from .services.query import get_available_comunas, get_available_cargos

app = FastAPI(
    title="Maquinaria Electoral API",
    description="Plataforma de inteligencia electoral-territorial para Chile",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(communes.router)
app.include_router(electoral.router)
app.include_router(geo.router)
app.include_router(census.router)


@app.get("/api/health")
def health():
    comunas = get_available_comunas()
    return {
        "status": "ok",
        "comunas_disponibles": len(comunas),
        "cargos_disponibles": ["concejal", "core", "alcalde", "diputado"],
    }
