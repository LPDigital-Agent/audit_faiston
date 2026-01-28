"use client";

import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/shared/glass-card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { motion } from "framer-motion";

/**
 * AssetStatsCard - KPI card component for Asset Management dashboard
 *
 * Features:
 * - Large value display
 * - Trend indicator (up/down/neutral)
 * - Icon with colored background
 * - Comparison with previous period
 * - Glassmorphism styling
 */

interface AssetStatsCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: {
    value: number;
    direction: "up" | "down" | "neutral";
    label?: string;
  };
  color?: "blue" | "magenta" | "green" | "yellow" | "red";
  subtitle?: string;
  className?: string;
  delay?: number;
}

const colorClasses = {
  blue: {
    bg: "bg-blue-mid/20",
    icon: "text-blue-light",
    trend: "text-blue-light",
  },
  magenta: {
    bg: "bg-magenta-mid/20",
    icon: "text-magenta-light",
    trend: "text-magenta-light",
  },
  green: {
    bg: "bg-green-500/20",
    icon: "text-green-400",
    trend: "text-green-400",
  },
  yellow: {
    bg: "bg-yellow-500/20",
    icon: "text-yellow-400",
    trend: "text-yellow-400",
  },
  red: {
    bg: "bg-red-500/20",
    icon: "text-red-400",
    trend: "text-red-400",
  },
};

const trendColors = {
  up: "text-green-400",
  down: "text-red-400",
  neutral: "text-text-muted",
};

export function AssetStatsCard({
  title,
  value,
  icon,
  trend,
  color = "blue",
  subtitle,
  className,
  delay = 0,
}: AssetStatsCardProps) {
  const colors = colorClasses[color];

  const TrendIcon = trend?.direction === "up"
    ? TrendingUp
    : trend?.direction === "down"
    ? TrendingDown
    : Minus;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: delay * 0.1, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <GlassCard className={cn("p-4 h-full", className)}>
        <div className="flex items-start justify-between">
          {/* Icon */}
          <div className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center",
            colors.bg
          )}>
            <div className={colors.icon}>{icon}</div>
          </div>

          {/* Trend indicator */}
          {trend && (
            <div className={cn(
              "flex items-center gap-1 text-xs font-medium",
              trendColors[trend.direction]
            )}>
              <TrendIcon className="w-3 h-3" />
              <span>{Math.abs(trend.value)}%</span>
            </div>
          )}
        </div>

        {/* Value */}
        <div className="mt-3">
          <p className="text-2xl font-bold text-text-primary">
            {typeof value === "number" ? value.toLocaleString("pt-BR") : value}
          </p>
          <p className="text-sm text-text-muted mt-0.5">{title}</p>
        </div>

        {/* Subtitle / Comparison */}
        {(subtitle || trend?.label) && (
          <p className="text-xs text-text-muted mt-2">
            {subtitle || trend?.label}
          </p>
        )}
      </GlassCard>
    </motion.div>
  );
}

export default AssetStatsCard;
