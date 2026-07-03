"use client";

import { useEffect, useRef, useMemo, useState } from "react";
import { Sensibilidad, ManzanaFeature, SENSIBILIDAD_COLORS } from "@/types/electoral";
import { choroplethColor, censusColor } from "@/lib/colors";
import { useTheme } from "@/components/ThemeProvider";
import type LeafletNS from "leaflet";
type LType = typeof LeafletNS;

interface Props {
  geojson: GeoJSON.FeatureCollection | null;
  manzanas: ManzanaFeature[];
  sensibilidad: Sensibilidad;
  activeLayer: "choropleth" | "heatmap" | "winner" | "debilidades" | "censo";
  onManzanaHover?: (mz: ManzanaFeature | null) => void;
  onManzanaClick?: (mz: ManzanaFeature) => void;
  selectedManzanaId?: string | null;
  censusVarData?: Record<string, number> | null;
  censusVarLabel?: string;
}

function featureCentroid(feature: GeoJSON.Feature): [number, number] | null {
  const geom = feature.geometry;
  if (!geom) return null;
  let coords: number[][] = [];
  if (geom.type === "Polygon")       coords = geom.coordinates[0];
  else if (geom.type === "MultiPolygon") coords = geom.coordinates[0][0];
  else return null;
  if (!coords.length) return null;
  let sx = 0, sy = 0;
  for (const [x, y] of coords) { sx += x; sy += y; }
  return [sy / coords.length, sx / coords.length];
}

export default function ElectoralMap({
  geojson, manzanas, sensibilidad, activeLayer, onManzanaHover,
  onManzanaClick, selectedManzanaId,
  censusVarData, censusVarLabel,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<LeafletNS.Map | null>(null);
  const layerRef     = useRef<LeafletNS.GeoJSON | null>(null);
  const heatRef      = useRef<any>(null);
  const tileRef      = useRef<LeafletNS.TileLayer | null>(null);
  const featureLayersRef = useRef<Map<string, LeafletNS.Layer>>(new Map());
  const selectedIdRef     = useRef<string | null>(null);
  const prevSelectedIdRef = useRef<string | null>(null);
  const [L, setL]    = useState<LType | null>(null);
  const { theme }    = useTheme();

  const mzLookup = useMemo(() => {
    const m = new Map<string, ManzanaFeature>();
    manzanas.forEach(mz => m.set(mz.id_manzana, mz));
    return m;
  }, [manzanas]);

  // Local-level aggregates. Como las pesos suman 1 dentro de cada local,
  // sumando voto_abs y total_votos por manzana recuperamos los totales reales
  // a nivel de local de votación (lo que SERVEL entrega). Esto es lo único
  // que tenemos con resolución real; las manzanas son una desagregación
  // ponderada por población, no un dato granular real.
  const localTotals = useMemo(() => {
    const m = new Map<string, { sector: number; total: number }>();
    manzanas.forEach(mz => {
      const key = mz.local_votacion || "";
      if (!key) return;
      const prev = m.get(key) || { sector: 0, total: 0 };
      prev.sector += mz.voto_abs || 0;
      prev.total  += mz.total_votos || 0;
      m.set(key, prev);
    });
    return m;
  }, [manzanas]);

  // Census variable range for choropleth normalization
  const censusRange = useMemo(() => {
    if (!censusVarData) return { min: 0, max: 1 };
    const vals = Object.values(censusVarData).filter(v => v > 0);
    if (!vals.length) return { min: 0, max: 1 };
    vals.sort((a, b) => a - b);
    const p = (q: number) => vals[Math.min(vals.length - 1, Math.floor(q * vals.length))];
    return { min: p(0.05), max: p(0.95) };
  }, [censusVarData]);

  // 1. Load Leaflet (client-side only)
  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;
    (async () => {
      const leaflet = await import("leaflet");
      (window as any).L = leaflet.default;
      await import("leaflet.heat");
      if (cancelled) return;
      setL(leaflet.default);
    })();
    return () => { cancelled = true; };
  }, []);

  // 2. Initialize map once L is loaded
  useEffect(() => {
    if (!L || !containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    // Guard against StrictMode double-mount
    if ((container as any)._leaflet_id) return;

    L.Icon.Default.mergeOptions({
      iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
      iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
      shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    });

    const map = L.map(container, {
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: true,
      preferCanvas: true,
    }).setView([-33.45, -70.65], 12);

    const isDark = document.documentElement.classList.contains("dark");
    const tileUrl = isDark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    tileRef.current = L.tileLayer(tileUrl, {
      attribution: "&copy; CartoDB &copy; OpenStreetMap contributors",
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;

    // Fix sizing after layout settles
    setTimeout(() => map.invalidateSize(), 50);
    setTimeout(() => map.invalidateSize(), 300);

    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(container);
    (map as any)._ccd_ro = ro;

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, [L]);

  // 2b. Swap tile layer when theme changes
  useEffect(() => {
    const map = mapRef.current;
    if (!L || !map) return;
    const tileUrl = theme === "dark"
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    if (tileRef.current) map.removeLayer(tileRef.current);
    tileRef.current = L.tileLayer(tileUrl, {
      attribution: "&copy; CartoDB &copy; OpenStreetMap contributors",
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);
  }, [theme, L]);

  // 3. Render geojson layer
  useEffect(() => {
    const map = mapRef.current;
    if (!L || !map || !geojson) return;

    // Clear previous layers
    if (layerRef.current) { map.removeLayer(layerRef.current); layerRef.current = null; }
    if (heatRef.current)  { map.removeLayer(heatRef.current);  heatRef.current = null;  }

    const { main } = SENSIBILIDAD_COLORS[sensibilidad];

    // Heatmap
    if (activeLayer === "heatmap") {
      const r = parseInt(main.slice(1, 3), 16);
      const g = parseInt(main.slice(3, 5), 16);
      const b = parseInt(main.slice(5, 7), 16);
      const points: [number, number, number][] = [];
      geojson.features.forEach(f => {
        const id = (f.properties as any)?.ID_MANZANA;
        const mz = id ? mzLookup.get(id) : null;
        if (!mz || mz.voto_pct <= 0) return;
        const c = featureCentroid(f);
        if (c) points.push([c[0], c[1], Math.min(mz.voto_pct / 50, 1.0)]);
      });
      const heat = (L as any).heatLayer(points, {
        radius: 25, blur: 35, maxZoom: 17, max: 1.0,
        gradient: {
          0.0: "rgba(0,0,0,0)",
          0.3: `rgba(${r},${g},${b},0.4)`,
          0.6: `rgba(${r},${g},${b},0.75)`,
          1.0: `rgb(${r},${g},${b})`,
        },
      }).addTo(map);
      heatRef.current = heat;
    }

    // Vector layer (always - serves as choropleth/winner OR as hover layer under heatmap)
    const styleFn = (feature?: GeoJSON.Feature): LeafletNS.PathOptions => {
      const id = (feature?.properties as any)?.ID_MANZANA;
      const mz = id ? mzLookup.get(id) : null;
      let style: LeafletNS.PathOptions;
      if (!mz) {
        // Manzanas without data (no voters assigned): subtle grey overlay so the
        // commune outline is visible without competing with the choropleth.
        style = {
          fillColor: "#2a2a36", fillOpacity: 0.35,
          color: "rgba(255,255,255,0.08)", weight: 0.3,
        };
      } else if (activeLayer === "heatmap") {
        style = {
          fillColor: "transparent", fillOpacity: 0,
          color: "rgba(255,255,255,0.04)", weight: 0.3,
        };
      } else if (activeLayer === "winner") {
        style = {
          fillColor: mz.is_fortaleza ? main : "#3a3a44",
          fillOpacity: mz.is_fortaleza ? 0.85 : 0.4,
          color: mz.is_fortaleza ? main : "rgba(255,255,255,0.08)",
          weight: mz.is_fortaleza ? 0.8 : 0.3,
        };
      } else if (activeLayer === "debilidades") {
        style = {
          fillColor: !mz.is_fortaleza ? "#E74C3C" : "#3a3a44",
          fillOpacity: !mz.is_fortaleza ? 0.85 : 0.25,
          color: !mz.is_fortaleza ? "#E74C3C" : "rgba(255,255,255,0.05)",
          weight: !mz.is_fortaleza ? 0.8 : 0.3,
        };
      } else if (activeLayer === "censo" && censusVarData) {
        const val = censusVarData[id] ?? 0;
        style = {
          fillColor: censusColor(val, censusRange.min, censusRange.max),
          fillOpacity: 0.9,
          color: "rgba(255,255,255,0.08)",
          weight: 0.3,
        };
      } else {
        style = {
          fillColor: choroplethColor(mz.voto_pct, sensibilidad),
          fillOpacity: 1,
          color: "rgba(255,255,255,0.10)",
          weight: 0.3,
        };
      }
      // Persistent highlight for the clicked manzana, on top of the base style.
      if (mz && id === selectedIdRef.current) {
        style = { ...style, color: "#3B82F6", weight: 3 };
      }
      return style;
    };

    featureLayersRef.current = new Map();
    const layer = L.geoJSON(geojson, {
      style: styleFn,
      onEachFeature: (feature: GeoJSON.Feature, lyr: LeafletNS.Layer) => {
        const id = (feature?.properties as any)?.ID_MANZANA;
        if (id) featureLayersRef.current.set(id, lyr);
      },
    } as any);

    layer.on("mouseover", (e: any) => {
      const f = e.layer?.feature;
      const id = f?.properties?.ID_MANZANA;
      const mz = id ? mzLookup.get(id) : null;
      if (!mz) return;
      e.layer.setStyle({ color: "#FFFFFF", weight: 2 });
      e.layer.bringToFront?.();
      onManzanaHover?.(mz);
      // Estimación por manzana: voto_abs y total_votos ya están ponderados
      // por la población censal de cada manzana dentro del local. La tilde
      // marca que es estimación, no recuento real (no tenemos geocoding
      // individual del padrón).
      const sectorMz = Math.round(mz.voto_abs || 0);
      const totalMz  = Math.round(mz.total_votos || 0);
      const votosLine = totalMz > 0
        ? `~${sectorMz.toLocaleString("es-CL")} de ${totalMz.toLocaleString("es-CL")} votos estimados en la manzana`
        : "";
      const loc = localTotals.get(mz.local_votacion || "");
      const contextLine = loc && loc.total > 0
        ? `Local: ${Math.round(loc.sector).toLocaleString("es-CL")} de ${Math.round(loc.total).toLocaleString("es-CL")}`
        : "";
      e.layer.bindTooltip(
        `<div style="min-width:180px">
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">${mz.local_votacion || "Local desconocido"}</div>
          <div style="font-size:20px;font-weight:700;color:var(--text-primary)">${mz.voto_pct.toFixed(1)}%</div>
          <div style="font-size:11px;color:var(--text-primary);opacity:0.75;margin-top:2px">${votosLine}</div>
          <div style="font-size:10px;color:var(--text-muted);opacity:0.85;margin-top:1px">${contextLine}</div>
          <div style="margin-top:6px;font-size:10px;color:${mz.is_fortaleza ? "#4CAF50" : "#F44336"}">${mz.is_fortaleza ? "▲ Zona fuerte" : "▼ Zona débil"}</div>
        </div>`,
        { permanent: false, direction: "top", sticky: true },
      ).openTooltip();
    });

    layer.on("mouseout", (e: any) => {
      layer.resetStyle(e.layer);
      e.layer.closeTooltip?.();
      onManzanaHover?.(null);
    });

    layer.on("click", (e: any) => {
      const f = e.layer?.feature;
      const id = f?.properties?.ID_MANZANA;
      const mz = id ? mzLookup.get(id) : null;
      if (!mz) return;
      onManzanaClick?.(mz);
    });

    layer.addTo(map);
    layerRef.current = layer;

    // Recompute size first, then fit bounds (so zoom matches actual viewport).
    map.invalidateSize();
    requestAnimationFrame(() => {
      map.invalidateSize();
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [20, 20], maxZoom: 15 });
      }
    });
  }, [L, geojson, manzanas, sensibilidad, activeLayer, mzLookup, localTotals, onManzanaHover, onManzanaClick, censusVarData, censusRange]);

  // 4. Live-highlight the selected manzana without rebuilding the whole layer
  // (rebuilding would also re-run fitBounds, yanking the viewport on every click).
  useEffect(() => {
    selectedIdRef.current = selectedManzanaId ?? null;
    const layer = layerRef.current;
    if (!layer) return;
    const prevId = prevSelectedIdRef.current;
    if (prevId && prevId !== selectedManzanaId) {
      const prevLyr = featureLayersRef.current.get(prevId);
      if (prevLyr) layer.resetStyle(prevLyr as any);
    }
    if (selectedManzanaId) {
      const lyr = featureLayersRef.current.get(selectedManzanaId) as any;
      if (lyr) {
        lyr.setStyle({ color: "#3B82F6", weight: 3 });
        lyr.bringToFront?.();
      }
    }
    prevSelectedIdRef.current = selectedManzanaId ?? null;
  }, [selectedManzanaId]);

  return (
    <div ref={containerRef}
         className="w-full h-full"
         style={{ background: "var(--bg-primary)", minHeight: 0 }} />
  );
}
