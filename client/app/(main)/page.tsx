"use client";

import { BentoGrid, BentoItem } from "@/components/dashboard/bento-grid";
import { NEXOHero } from "@/components/dashboard/nexo-hero";
import { CalendarWidget } from "@/components/dashboard/calendar-widget";
import { NewsWidget } from "@/components/dashboard/news-widget";
import { TeamsWidget } from "@/components/dashboard/teams-widget";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { AnnouncementsWidget } from "@/components/dashboard/announcements-widget";

/**
 * Dashboard Page - Main landing page for Faiston One
 *
 * Displays a Bento Grid layout with:
 * - NEXO Hero (AI assistant greeting) - 2x1
 * - Calendar Widget - 1x1
 * - News Widget - 1x2
 * - Teams Widget - 1x1
 * - Quick Actions - 1x1
 * - Announcements Widget - 1x1
 *
 * Note: AppShell is provided by the parent (main)/layout.tsx
 */

export default function DashboardPage() {
  return (
    <div className="max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-h1 text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-muted">
          Bem-vindo ao Faiston One. Seu portal unificado de produtividade.
        </p>
      </div>

      {/* Bento Grid Layout */}
      <BentoGrid>
        {/* NEXO Hero - 2 columns, 1 row */}
        <BentoItem colSpan={2} rowSpan={1} delay={0}>
          <NEXOHero />
        </BentoItem>

        {/* Calendar - 1 column, 1 row */}
        <BentoItem colSpan={1} rowSpan={1} delay={1}>
          <CalendarWidget />
        </BentoItem>

        {/* Quick Actions - 1 column, 1 row */}
        <BentoItem colSpan={1} rowSpan={1} delay={2}>
          <QuickActions />
        </BentoItem>

        {/* News - 1 column, 2 rows */}
        <BentoItem colSpan={1} rowSpan={2} delay={3}>
          <NewsWidget />
        </BentoItem>

        {/* Teams - 1 column, 1 row */}
        <BentoItem colSpan={1} rowSpan={1} delay={4}>
          <TeamsWidget />
        </BentoItem>

        {/* Announcements - 2 columns, 1 row */}
        <BentoItem colSpan={2} rowSpan={1} delay={5}>
          <AnnouncementsWidget />
        </BentoItem>
      </BentoGrid>
    </div>
  );
}
