import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        izquierda:       { DEFAULT: "#C0392B", light: "#E74C3C", dark: "#922B21" },
        centroizquierda: { DEFAULT: "#E74C3C", light: "#FADBD8", dark: "#C0392B" },
        centro:          { DEFAULT: "#8E44AD", light: "#D2B4DE", dark: "#6C3483" },
        centroderecha:   { DEFAULT: "#2980B9", light: "#AED6F1", dark: "#1A5276" },
        derecha:         { DEFAULT: "#1A5276", light: "#85C1E9", dark: "#154360" },
        independiente:   { DEFAULT: "#7F8C8D", light: "#D5DBDB", dark: "#566573" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'DM Sans'", "Inter", "sans-serif"],
      },
      animation: {
        "fade-in":    "fadeIn 0.5s ease-out",
        "slide-up":   "slideUp 0.4s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%":   { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
