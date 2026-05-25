# Maquinaria Electoral — Arquitectura Técnica

## Concepto

Plataforma de inteligencia electoral-territorial para Chile.
El mapa es el producto. El dato territorial es el núcleo.

---

## Stack

| Capa          | Tecnología                    | Rol                                    |
|---------------|-------------------------------|----------------------------------------|
| Preprocessing | Python, GeoPandas, scikit-learn | Pipeline offline → Parquet por comuna |
| Backend       | FastAPI + DuckDB              | API REST, queries sobre Parquet        |
| Frontend      | Next.js 14 + Tailwind + TS   | UX fullscreen, mapa interactivo        |
| Mapas         | Leaflet + GeoJSON             | Choropleth territorial                 |
| Datos         | Parquet (columnar)            | Consultas rápidas sin carga completa   |
| Hosting       | Netlify (frontend) + Railway (backend) | Serverless/ligero              |

---

## Flujo de datos

```
[Datos crudos SERVEL]                    [Datos geográficos]
Concejales24.txt (556MB)                manzanas_nacional.parquet (193MB)
Cores24.txt (383MB)          ──────→    TODOSLOCALES.csv (600KB)
Muni24.xlsx (18MB)
Dipu25.csv (30MB)

          ↓ preprocessing/run_pipeline.py (offline, 1 vez)

data/processed/
├── locales.parquet              # Locales georreferenciados, normalizados
├── pesos/{COMUNA}.parquet       # Manzana → local (BallTree centroide)
├── votos/{cargo}/{COMUNA}.parquet  # Votos distribuidos por manzana
└── geojson/{COMUNA}.geojson     # Geometría simplificada para web

          ↓ FastAPI backend

GET /api/electoral/snapshot?comuna=X&cargo=Y&sensibilidad=Z
→ JSON: { manzanas, stats, narrative }

GET /api/geo/{COMUNA}
→ GeoJSON simplificado

          ↓ Next.js frontend

Landing → Wizard (cargo → sensibilidad → comuna) → Snapshot fullscreen
```

---

## Decisiones de arquitectura

### Eliminar geocodificación individual (HERE API)
El notebook original geocodificaba cada elector del padrón (1.9GB, ~15M registros).
Esta arquitectura usa el **método centroide**: cada manzana se asigna a su local más
cercano mediante BallTree. Resultado equivalente, 1000x más rápido, sin API keys.

### Preprocessing offline
Los 3+ GB de datos crudos se transforman en ~50MB de Parquet por región.
El backend solo lee datos pre-calculados; nunca carga el padrón completo.

### DuckDB en backend
Consultas columnar sobre Parquet sin montar base de datos. Ideal para el patrón
de acceso (filtrar por comuna, agregar por manzana/local).

### GeoJSON simplificado
`simplify(tolerance=0.00005)` reduce el peso de geometrías ~70% sin impacto visual
apreciable en zoom communal.

---

## Pipeline de preprocessing

```bash
# Instalar dependencias
pip install -r preprocessing/requirements.txt

# Procesar una comuna (testing)
python preprocessing/run_pipeline.py --comunas PENALOLEN

# Procesar múltiples comunas
python preprocessing/run_pipeline.py --comunas PENALOLEN SANTIAGO MAIPU --cargos concejal alcalde

# Procesar todo Chile (puede tardar horas)
python preprocessing/run_pipeline.py --all
```

---

## API Endpoints

| Método | Ruta                                     | Descripción                           |
|--------|------------------------------------------|---------------------------------------|
| GET    | `/api/health`                            | Estado + comunas disponibles          |
| GET    | `/api/communes/`                         | Lista de comunas procesadas           |
| GET    | `/api/communes/{comuna}`                 | Info de una comuna + cargos disponibles |
| GET    | `/api/electoral/snapshot`               | Snapshot electoral completo           |
| GET    | `/api/geo/{comuna}`                      | GeoJSON de manzanas de la comuna      |

### Parámetros de snapshot
- `comuna`: nombre normalizado (sin tildes, mayúsculas) — ej. `PENALOLEN`
- `cargo`: `concejal` | `core` | `alcalde` | `diputado`
- `sensibilidad`: `izquierda` | `centroizquierda` | `centro` | `centroderecha` | `derecha` | `independiente`

---

## Deployment

### Local (desarrollo)
```bash
# Backend
pip install -r backend/requirements.txt
python backend/run.py

# Frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

### Producción
- **Frontend → Netlify**: `npm run build` + deploy `frontend/` 
  - Variable: `NEXT_PUBLIC_API_URL=https://tu-backend.railway.app`
- **Backend → Railway / Render**: deploy `backend/` como Python app
  - `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Datos procesados**: incluir `data/processed/` en el deploy del backend
  (o montar volumen en Railway)

---

## Estructura de archivos

```
MAQUINARIA/
├── preprocessing/              # Pipeline offline (Python)
│   ├── utils.py                  # Funciones compartidas del notebook
│   ├── 01_build_locales.py       # Procesa TODOSLOCALES → locales.parquet
│   ├── 02_build_pesos.py         # Manzana → local (BallTree)
│   ├── 03_build_votos.py         # Redistribuye votos → manzanas
│   └── run_pipeline.py           # Orquestador
│
├── backend/                    # FastAPI
│   ├── main.py
│   ├── routers/                  # communes, electoral, geo
│   └── services/query.py         # DuckDB + narrativa automática
│
├── frontend/                   # Next.js 14
│   ├── app/
│   │   ├── page.tsx              # Landing "Quiero ser candidato"
│   │   └── snapshot/page.tsx     # Mapa fullscreen + sidebar
│   ├── components/
│   │   ├── wizard/WizardFlow.tsx  # Flujo cargo → sensibilidad → comuna
│   │   ├── map/ElectoralMap.tsx   # Leaflet choropleth
│   │   ├── map/MapControls.tsx    # Switcher de capas
│   │   └── charts/SwingChart.tsx  # Top candidatos horizontal
│   ├── lib/api.ts                # Fetch functions
│   └── types/electoral.ts        # Tipos TS compartidos
│
└── data/
    ├── raw/       → archivos originales SERVEL (no en git)
    └── processed/ → outputs del pipeline (no en git, van en deploy)
```

---

## Roadmap evolutivo

### v1.0 (MVP actual)
- Wizard 3 pasos
- Mapa choropleth por sensibilidad
- Sidebar con stats + top candidatos
- Narrativa automática

### v1.1
- Capa de heatmap (Leaflet.heat)
- Comparación pres 1ra vuelta vs cargo seleccionado
- Export PNG del mapa

### v1.2
- Múltiples candidatos simultáneos (comparación directa)
- Ranking de locales por rendimiento
- Filtro por distancia geográfica

### v2.0
- Autenticación (plataforma privada por campaña)
- Modo "mi candidato" con nombre propio
- Proyecciones basadas en swing histórico
- Dashboard de campaña multi-comuna
