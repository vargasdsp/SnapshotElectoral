# Maquinaria Electoral — Handoff

Estado del proyecto al cierre de la sesión. Para retomar la próxima vez.

---

## Cómo levantar

**Backend** (desde la raíz del proyecto, NO desde `backend/`):
```
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
> Importante: NO usar `python backend/run.py` — falla con `ModuleNotFoundError`.

**Frontend:**
```
cd frontend
npm run dev
```
> Si el puerto 3000 está ocupado, Next.js sube solo al 3001.

**Preprocessing** (si hay datos nuevos):
```
python preprocessing/run_pipeline.py             # todo (pasos 1-6)
python preprocessing/06_build_electos.py         # solo electos D'Hondt
```

---

## Estado del pipeline (al 2026-05-12)

- **346 comunas** procesadas con datos de votos (pesos + votos en 4 cargos).
- **16 comunas sin datos**: rurales sin manzanas INE (Antártica, Cabo de Hornos, Camarones, Colchane, General Lagos, Lago Verde, Laguna Blanca, Llay-Llay, Marchigüe, Ollague, Primavera, Río Verde, San Gregorio, Timaukel, Torres del Paine + NaN).
- `data/processed/electos/` generado con D'Hondt correcto:
  - `alcalde.parquet`: 346 electos
  - `concejal.parquet`: 2,611 candidatos electos
  - `core.parquet`: 300 electos (circunscripciones provinciales)
  - `diputado.parquet`: 155 electos (28 distritos, IDs SERVEL 6001-6028)

---

## Pipeline pasos (en orden)

1. `01_build_locales.py` — índice de locales georreferenciados
2. `02_build_pesos.py` — BallTree manzana→local por centroide
3. `03_build_votos.py` — distribución de votos a manzanas
4. `04_build_insights.py` — metadata alcaldes (reelecto/nuevo/ex-militancia/cupo)
5. `05_build_distritos.py` — mapping distrito (6001-6028) → lista de comunas
6. `06_build_electos.py` — electos D'Hondt por cargo ← **NUEVO**

---

## Decisiones clave acumuladas

### 1. Limitación matemática del centroide
**El % por manzana es idéntico dentro de un mismo local.** El peso poblacional se anula en `(votos_local × peso) / (total_local × peso)`. Solo difieren votos absolutos. NO prometer "% real por manzana" en UI — solo "estimación territorial".

### 2. Reclasificación política
- DC → **centroizquierda** (no centro)
- Demócratas → **centroderecha** (no centro)
- Centro queda PL + Amarillos (correcto políticamente 2024)
- IND reclasificados con InsightsAlcaldes: ex-militancia o cupo del pacto

### 3. InsightsAlcaldes integrado
Archivo: `InsightsAlcaldes25.csv` (345 alcaldes). Procesado en `data/processed/insights_alcaldes.parquet`. Enriquece modo autoridad+alcalde con panel de trayectoria política.

### 4. D'Hondt correcto
- Antes: `agg.head(N)` con N hardcodeado. **Incorrecto**.
- Ahora: `06_build_electos.py` calcula D'Hondt real (por lista para concejal/core, por pacto para diputado).
- **OJO**: IDs de distrito SERVEL son 6001-6028, no 1-28. Lookup usa `did_int % 1000`.
- `query.py` usa `_load_electos()` + `_is_electo()` para filtrar electos desde los parquets.

### 5. Fallback por sensibilidad adyacente
Cuando un sector no presentó candidatos a un cargo (e.g., "centro" no tuvo alcalde en la comuna), `get_snapshot_data()` ahora prueba sensibilidades adyacentes en orden de proximidad antes de devolver `no_data=True`.
- El mapa muestra la data del adyacente (no queda vacío).
- Frontend muestra banner: "Proxy territorial: Centroizquierda (no hubo candidatos de Centro a alcalde)".
- Orden de fallback definido en `SENSIBILIDAD_ADJACENTES` en `query.py`.

### 6. Narrativa de autoridad corregida
- Antes: `swing = pct_propio - pct_sector` — siempre negativo para multi-listas, aunque el candidato sea primera mayoría.
- Ahora: compara vs. todos los candidatos de la elección. Muestra "fue primera mayoría" o "N° X de Y candidatos".
- El rival inmediato (segundo lugar para primera mayoría, o el que le gana) se muestra como referencia.

### 7. Flujo distrito para cargo=diputado
- Wizard candidato+diputado: cards de distrito con chips de comunas.
- Snapshot: agrega votos de todas las comunas del distrito; dropdown para filtrar a una sola.
- **Pendiente**: modo autoridad+diputado aún usa comunas en vez de distritos.

---

## Lo que quedó PENDIENTE (prioridad alta primero)

### Alta prioridad

1. **Autoridad+diputado usa comunas en vez de distritos** (wizard y snapshot page):
   - Wizard: `usesDistrito` ya existe pero no aplica para `mode=autoridad`.
   - Snapshot: no maneja `distrito_id` en modo autoridad (necesita `fetchAutoridadDistritoSnapshot`).

2. **CORE por circunscripción**: igual que distrito para diputado.
   - Falta `preprocessing/06b_build_circunscripciones.py` extrayendo de `Cores24.txt`.
   - Endpoints paralelos a los de distrito en backend.
   - Wizard CORE en ambos modos usando circunscripción como unidad.

### Media prioridad

3. **Toggle válidos vs totales**: alternar denominador entre válidos y válidos+nulos+blancos.
   - Documentado en `memory/project_toggle_validos.md`.
   - Requiere extraer nulos/blancos en `03_build_votos.py` y toggle en sidebar.

4. **Deploy**: Netlify (frontend) + Fly.io o Railway (backend).

---

## Archivos clave (esta y sesiones anteriores)

**Preprocessing:**
- `preprocessing/utils.py` — normalización texto, coordenadas, to_numeric_cl
- `preprocessing/01_build_locales.py`
- `preprocessing/02_build_pesos.py`
- `preprocessing/03_build_votos.py`
- `preprocessing/04_build_insights.py`
- `preprocessing/05_build_distritos.py`
- `preprocessing/06_build_electos.py` ← nuevo (D'Hondt)
- `preprocessing/run_pipeline.py` ← actualizado (incluye pasos 4-6)

**Backend:**
- `backend/main.py` — FastAPI app
- `backend/services/query.py` — lógica principal (snapshot, narrativa, electos)
- `backend/routers/communes.py` — /communes, /distritos-by-region
- `backend/routers/electoral.py` — /snapshot, /candidatos, flujo distrito
- `backend/routers/geo.py` — /geojson, /distrito/{id}

**Frontend:**
- `frontend/types/electoral.ts` — tipos TS (incluye proxy_sensibilidad)
- `frontend/app/page.tsx` — landing + wizard
- `frontend/app/snapshot/page.tsx` — mapa fullscreen + proxy banner
- `frontend/components/wizard/WizardFlow.tsx`
- `frontend/components/map/ElectoralMap.tsx`
- `frontend/components/map/EmptySectorOverlay.tsx`
- `frontend/components/charts/SwingChart.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/partidoColors.ts`

---

## Punto de retorno sugerido

1. Testear en browser el caso "centro + alcalde en una comuna donde ganó derecha" → debería mostrar mapa del adyacente + banner.
2. Testear narrativa de autoridad: un alcalde primera mayoría ya no debe decir "por debajo del sector".
3. Atacar el wizard **autoridad+diputado** (item 1 pendiente). El backend ya está listo.
4. Luego CORE por circunscripción.
