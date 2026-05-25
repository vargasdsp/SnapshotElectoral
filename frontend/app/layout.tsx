import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";

export const metadata: Metadata = {
  title: "Maquinaria Electoral",
  description: "Inteligencia electoral-territorial para Chile",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className="dark">
      <body className="overflow-hidden" style={{ background: "var(--bg-primary)", color: "var(--text-primary)" }}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
