import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Procede — Assistente de Procedimentos",
  description: "Tire dúvidas dos procedimentos de execução da obra.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
