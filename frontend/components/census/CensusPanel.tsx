"use client";

import { CensusData } from "@/types/electoral";

interface Props {
  data: CensusData;
  colorMain: string;
  activeVar?: string | null;
  onVarClick?: (variable: string, label: string) => void;
}

function Bar({ pct, color = "#4A90D9", max = 100 }: { pct: number; color?: string; max?: number }) {
  const w = Math.min((pct / Math.max(max, 0.01)) * 100, 100);
  return (
    <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}

function Row({
  label, value, color, max, variable, activeVar, onVarClick,
}: {
  label: string; value: number; color?: string; max?: number;
  variable?: string; activeVar?: string | null; onVarClick?: (v: string, l: string) => void;
}) {
  const isActive = variable && activeVar === variable;
  const clickable = variable && onVarClick;
  return (
    <button
      className="flex items-center gap-3 py-1.5 w-full text-left rounded-md px-1.5 -mx-1.5 transition-colors"
      style={{
        background: isActive ? "rgba(255,255,255,0.08)" : "transparent",
        cursor: clickable ? "pointer" : "default",
      }}
      onClick={() => clickable && onVarClick(variable, label)}
      disabled={!clickable}
    >
      <span className="text-gray-400 text-xs w-36 shrink-0 leading-tight flex items-center gap-1">
        {isActive && <span className="text-xs" style={{ color: "#F39C12" }}>◉</span>}
        {label}
      </span>
      <Bar pct={value} color={color} max={max} />
      <span className="text-white text-xs font-semibold w-10 text-right tabular-nums shrink-0">
        {value.toFixed(1)}%
      </span>
    </button>
  );
}

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="p-4 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-sm">{icon}</span>
        <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">{title}</span>
      </div>
      {children}
    </div>
  );
}

export default function CensusPanel({ data, colorMain, activeVar, onVarClick }: Props) {
  const d = data;
  const vulnerIdx = d.vulnerabilidad.indice_vulnerabilidad;

  return (
    <div className="flex flex-col">
      {/* Header totals */}
      <div className="p-4 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
        <div className="flex justify-between items-start">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">Censo 2024 INE</p>
            <p className="text-white font-semibold text-sm mt-0.5">
              {d.comuna.charAt(0) + d.comuna.slice(1).toLowerCase()}
            </p>
          </div>
          <div className="text-right">
            <p className="text-white font-bold text-lg">{d.total_personas.toLocaleString("es-CL")}</p>
            <p className="text-[10px] text-gray-500">personas</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-3">
          <div className="glass rounded-lg p-2 text-center">
            <p className="text-white font-bold">{d.total_viviendas.toLocaleString("es-CL")}</p>
            <p className="text-[10px] text-gray-500">viviendas</p>
          </div>
          <div className="glass rounded-lg p-2 text-center">
            <p className="text-white font-bold">{d.total_hogares.toLocaleString("es-CL")}</p>
            <p className="text-[10px] text-gray-500">hogares</p>
          </div>
        </div>
        {activeVar && (
          <div className="mt-3 px-2 py-1.5 rounded-lg text-xs flex items-center gap-1.5"
               style={{ background: "rgba(243,156,18,0.12)", color: "#F39C12", border: "1px solid rgba(243,156,18,0.25)" }}>
            <span>◉</span>
            <span>Variable activa en mapa</span>
            <button className="ml-auto text-gray-500 hover:text-white" onClick={() => onVarClick?.("", "")}>✕</button>
          </div>
        )}
        <p className="text-[10px] text-gray-600 mt-2">Clic en una variable para visualizarla en el mapa</p>
      </div>

      {/* Vulnerabilidad */}
      <Section title="Vulnerabilidad habitacional" icon="⚠">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1">
            <div className="flex justify-between items-end mb-1">
              <span className="text-xs text-gray-400">Índice compuesto</span>
              <span className="font-bold text-lg" style={{
                color: vulnerIdx < 5 ? "#27AE60" : vulnerIdx < 15 ? "#F39C12" : "#E74C3C"
              }}>
                {vulnerIdx.toFixed(1)}%
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
              <div className="h-full rounded-full" style={{
                width: `${Math.min(vulnerIdx * 3, 100)}%`,
                background: vulnerIdx < 5 ? "#27AE60" : vulnerIdx < 15 ? "#F39C12" : "#E74C3C",
              }} />
            </div>
          </div>
        </div>
        <Row label="Hacinamiento" value={d.vulnerabilidad.hacinamiento_pct} color="#E74C3C" max={30}
             variable="n_viv_hacinadas" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Déficit cuantitativo" value={d.vulnerabilidad.deficit_cuant_pct} color="#E67E22" max={30}
             variable="n_deficit_cuantitativo" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Viviendas irrecuperables" value={d.vulnerabilidad.irrecuperables_pct} color="#C0392B" max={20}
             variable="n_viv_irrecuperables" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Paredes precarias" value={d.vulnerabilidad.paredes_precarias_pct} color="#922B21" max={15}
             variable="n_mat_paredes_precarios" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Piso tierra" value={d.vulnerabilidad.piso_tierra_pct} color="#7B241C" max={10}
             variable="n_mat_piso_tierra" activeVar={activeVar} onVarClick={onVarClick} />
      </Section>

      {/* Educación y ocupaciones */}
      <Section title="Ocupaciones y educación" icon="◈">
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="glass rounded-lg p-2 text-center">
            <p className="font-bold text-white">{d.educacion_clase.prom_escolaridad.toFixed(1)}</p>
            <p className="text-[10px] text-gray-500">años escolaridad</p>
          </div>
          <div className="glass rounded-lg p-2 text-center">
            <p className="font-bold" style={{ color: colorMain }}>{d.educacion_clase.ed_superior_pct.toFixed(1)}%</p>
            <p className="text-[10px] text-gray-500">% pob. c/ ed. superior</p>
          </div>
        </div>
        <Row label="Directivos, prof. y técnicos" value={d.educacion_clase.clase_alta_media_pct} color={colorMain} max={40}
             variable="n_ciuo_1" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Oficios, operarios y servicios" value={d.educacion_clase.clase_trabajadora_pct} color="#7F8C8D" max={60}
             variable="n_ciuo_9" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Con estudios superiores" value={d.educacion_clase.ed_superior_pct} color="#3498DB" max={60}
             variable="n_cine_terciaria_maestria_doctorado" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Analfabetismo" value={d.educacion_clase.analfabetismo_pct} color="#E74C3C" max={10}
             variable="n_analfabet" activeVar={activeVar} onVarClick={onVarClick} />
      </Section>

      {/* Demografía */}
      <Section title="Demografía" icon="◉">
        <Row label="18–24 años" value={d.demografia.edad_18_24_pct} color="#3498DB" max={25}
             variable="n_edad_18_24" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="25–44 años" value={d.demografia.edad_25_44_pct} color="#2980B9" max={40}
             variable="n_edad_25_44" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="45–59 años" value={d.demografia.edad_45_59_pct} color="#1A5276" max={30}
             variable="n_edad_45_59" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="60 o más" value={d.demografia.edad_60_mas_pct} color="#154360" max={35}
             variable="n_edad_60_mas" activeVar={activeVar} onVarClick={onVarClick} />
        <div className="mt-1 pt-1 border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
          <Row label="Mujeres" value={d.demografia.mujeres_pct} color="#9B59B6"
               variable="n_mujeres" activeVar={activeVar} onVarClick={onVarClick} />
          <Row label="Inmigrantes" value={d.demografia.inmigrantes_pct} color="#E67E22" max={30}
               variable="n_inmigrantes" activeVar={activeVar} onVarClick={onVarClick} />
          <Row label="Pueblos originarios" value={d.demografia.pueblos_orig_pct} color="#27AE60" max={20}
               variable="n_pueblos_orig" activeVar={activeVar} onVarClick={onVarClick} />
          <Row label="Discapacidad" value={d.demografia.discapacidad_pct} color="#F39C12" max={20}
               variable="n_discapacidad" activeVar={activeVar} onVarClick={onVarClick} />
        </div>
      </Section>

      {/* Servicios */}
      <Section title="Servicios y conectividad" icon="◎">
        <Row label="Acceso a internet" value={d.servicios.internet_pct} color="#27AE60"
             variable="n_internet" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Agua potable" value={d.servicios.agua_potable_pct} color="#3498DB"
             variable="n_fuente_agua_publica" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Sin electricidad" value={d.servicios.sin_elect_pct} color="#E74C3C" max={10}
             variable="n_fuente_elect_no_tiene" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Auto propio" value={d.servicios.auto_pct} color="#F39C12"
             variable="n_transporte_auto" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Transporte público" value={d.servicios.transporte_pub_pct} color="#7F8C8D"
             variable="n_transporte_publico" activeVar={activeVar} onVarClick={onVarClick} />
      </Section>

      {/* Vivienda y hogares */}
      <Section title="Vivienda y hogares" icon="⌂">
        <Row label="Propietarios" value={d.vivienda.propietarios_pct} color="#27AE60"
             variable="n_tenencia_propia_pagada" activeVar={activeVar} onVarClick={onVarClick} />
        <Row label="Arrendatarios" value={d.vivienda.arrendatarios_pct} color="#E67E22"
             variable="n_tenencia_arrendada_contrato" activeVar={activeVar} onVarClick={onVarClick} />
        <div className="mt-1 pt-1 border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
          <Row label="Jefa de hogar mujer" value={d.hogares.jefatura_mujer_pct} color="#9B59B6"
               variable="n_jefatura_mujer" activeVar={activeVar} onVarClick={onVarClick} />
          <Row label="Hogares unipersonales" value={d.hogares.unipersonales_pct} color="#7F8C8D"
               variable="n_hog_unipersonales" activeVar={activeVar} onVarClick={onVarClick} />
          <Row label="Con adulto mayor" value={d.hogares.con_adulto_mayor_pct} color="#5D6D7E"
               variable="n_hog_60" activeVar={activeVar} onVarClick={onVarClick} />
          <Row label="Con menores de edad" value={d.hogares.con_menores_pct} color="#2E86C1"
               variable="n_hog_menores" activeVar={activeVar} onVarClick={onVarClick} />
        </div>
      </Section>

      {/* Empleo */}
      <div className="p-4">
        <div className="flex items-center gap-1.5 mb-3">
          <span className="text-sm">◈</span>
          <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Empleo</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            className="glass rounded-lg p-3 text-center transition-colors hover:bg-white hover:bg-opacity-5"
            style={{ outline: activeVar === "n_ocupado" ? "1px solid #F39C12" : "none" }}
            onClick={() => onVarClick?.("n_ocupado", "Ocupados")}
          >
            <p className="font-bold text-lg" style={{ color: "#27AE60" }}>{d.empleo.ocupados_pct.toFixed(1)}%</p>
            <p className="text-[10px] text-gray-500">ocupados</p>
          </button>
          <button
            className="glass rounded-lg p-3 text-center transition-colors hover:bg-white hover:bg-opacity-5"
            style={{ outline: activeVar === "n_desocupado" ? "1px solid #F39C12" : "none" }}
            onClick={() => onVarClick?.("n_desocupado", "Desocupados")}
          >
            <p className="font-bold text-lg" style={{ color: "#E74C3C" }}>{d.empleo.desocupados_pct.toFixed(1)}%</p>
            <p className="text-[10px] text-gray-500">desocupados</p>
          </button>
        </div>
        <p className="text-[10px] text-gray-600 mt-3 text-center">
          Fuente: INE Censo 2024 · Datos a nivel manzana agregados por comuna
        </p>
      </div>
    </div>
  );
}
