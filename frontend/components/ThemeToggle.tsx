"use client";
import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      title={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
      style={{
        background: "var(--overlay-soft)",
        border: "1px solid var(--border)",
        color: "var(--text-muted)",
      }}
    >
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}
