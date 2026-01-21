import type { Metadata, Viewport } from "next";
import { Roboto, Roboto_Slab } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers/Providers";

/**
 * Faiston One - Root Layout
 *
 * Configures the base layout with:
 * - Roboto font family (official Faiston typography)
 * - Dark theme as default
 * - Portuguese (Brazil) language
 */

// Roboto Light for body text
const roboto = Roboto({
  variable: "--font-roboto",
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
  display: "swap",
});

// Roboto Slab for headings
const robotoSlab = Roboto_Slab({
  variable: "--font-roboto-slab",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Faiston One",
    template: "%s | Faiston One",
  },
  description: "Faiston One - Portal Intranet AI-First comandado pelo NEXO",
  keywords: ["Faiston", "Intranet", "NEXO", "AI", "Portal"],
  authors: [{ name: "Faiston" }],
  creator: "Faiston",
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  themeColor: "#151720",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="dark">
      <body
        className={`${roboto.variable} ${robotoSlab.variable} font-sans antialiased`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
