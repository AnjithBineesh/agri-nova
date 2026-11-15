import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Agri Nova – AI crop prediction and rotation strategy",
  description:
    "Agri Nova predicts the crops that suit your soil and season with machine learning, and plans crop rotation strategies that protect soil, save water and adapt to a changing climate.",
};

export const viewport: Viewport = { themeColor: "#0f3b2c", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
