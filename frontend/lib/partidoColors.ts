// Paleta de colores por partido político chileno.
// Base proporcionada por el usuario; colores complementarios buscados para
// partidos pequeños o coaliciones, cuidando que no se mezclen tonos dentro
// del mismo bloque ideológico (ej: dos rojos casi idénticos en izquierda).

export const PARTIDO_COLORS: Record<string, string> = {
  // === Izquierda ===
  "PARTIDO COMUNISTA DE CHILE":               "#DB0A13",
  "FRENTE AMPLIO":                            "#00B85A",  // coalición FA: verde representativo
  "PARTIDO HUMANISTA":                        "#FF5801",
  "PARTIDO ACCION HUMANISTA":                 "#FF8B33",  // tono más claro para no confundir con PH
  "FEDERACION REGIONALISTA VERDE SOCIAL":     "#DBDA12",
  "PARTIDO ECOLOGISTA VERDE":                 "#2ECC71",
  "PARTIDO ALIANZA VERDE POPULAR":            "#16A085",
  "IGUALDAD":                                 "#3FA535",
  "PARTIDO DE TRABAJADORES REVOLUCIONARIOS":  "#800000",

  // === Centroizquierda ===
  "PARTIDO SOCIALISTA DE CHILE":              "#CE001A",
  "PARTIDO POR LA DEMOCRACIA":                "#2F2462",
  "PARTIDO RADICAL DE CHILE":                 "#122486",
  "PARTIDO DEMOCRATA CRISTIANO":              "#0060A7",  // DC ahora en centroizquierda

  // === Centro ===
  "PARTIDO LIBERAL DE CHILE":                 "#FE432D",
  "MOVIMIENTO AMARILLOS POR CHILE":           "#F4C20D",

  // === Centroderecha ===
  "EVOLUCION POLITICA":                       "#01A3C9",
  "PARTIDO DEMOCRATAS CHILE":                 "#5DADE2",  // Demócratas ahora en centroderecha

  // === Derecha ===
  "UNION DEMOCRATA INDEPENDIENTE":            "#29388A",
  "RENOVACION NACIONAL":                      "#00205D",
  "PARTIDO REPUBLICANO DE CHILE":             "#334568",
  "PARTIDO NACIONAL LIBERTARIO":              "#1A237E",
  "PARTIDO SOCIAL CRISTIANO":                 "#8E44AD",

  // === Independientes y otros ===
  "INDEPENDIENTES":                           "#B3B3B3",
  "PARTIDO DE LA GENTE":                      "#00225F",
  "POPULAR":                                  "#757575",
};

const FALLBACK = "#9CA3AF";

// Lookup tolerante a variaciones de casing y espacios.
export function partidoColor(partido: string | null | undefined): string {
  if (!partido) return FALLBACK;
  const key = partido.toUpperCase().trim();
  if (PARTIDO_COLORS[key]) return PARTIDO_COLORS[key];
  // Match parcial (ej. "INDEPENDIENTES FUERA DE PACTO" → INDEPENDIENTES)
  for (const [k, v] of Object.entries(PARTIDO_COLORS)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return FALLBACK;
}
