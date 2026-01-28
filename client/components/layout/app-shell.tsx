"use client";

import { cn } from "@/lib/utils";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { useState } from "react";
import dynamic from "next/dynamic";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

/**
 * AppShell - Main layout wrapper for Faiston One
 *
 * Combines Sidebar, Header, and main content area.
 * Handles the Command Palette state.
 * Protected by authentication - redirects to login if not authenticated.
 */

// Lazy load Command Palette for better initial load
const CommandPalette = dynamic(
  () => import("@/components/command-palette/command-palette"),
  { ssr: false }
);

interface AppShellProps {
  children: React.ReactNode;
  /** Se true, não exige autenticação (default: false) */
  requireAuth?: boolean;
}

export function AppShell({ children, requireAuth = true }: AppShellProps) {
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  const content = (
    <div className="min-h-screen bg-faiston-bg">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="pl-[72px] lg:pl-[240px] transition-all duration-200">
        {/* Header */}
        <Header onOpenCommandPalette={() => setIsCommandPaletteOpen(true)} />

        {/* Page Content */}
        <main className={cn("min-h-[calc(100vh-4rem)]", "p-6")}>
          {children}
        </main>
      </div>

      {/* Command Palette */}
      <CommandPalette
        open={isCommandPaletteOpen}
        onOpenChange={setIsCommandPaletteOpen}
      />
    </div>
  );

  // Se requireAuth é false, retornar conteúdo sem proteção
  if (!requireAuth) {
    return content;
  }

  // Proteger rotas que requerem autenticação
  return <ProtectedRoute>{content}</ProtectedRoute>;
}

export default AppShell;
