"use client";

import { AppShell } from "@/components/layout/app-shell";

/**
 * Main Layout - Shared layout for all authenticated pages
 *
 * This layout provides the AppShell (Sidebar + Header) for ALL pages
 * within the (main) route group. This ensures consistent navigation
 * and avoids conflicts when using client-side routing.
 *
 * Route Group: (main) - Parentheses mean it doesn't affect the URL
 * So /ferramentas/ativos still works, not /(main)/ferramentas/ativos
 */

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  return <AppShell>{children}</AppShell>;
}
