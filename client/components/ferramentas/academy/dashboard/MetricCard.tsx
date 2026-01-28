// =============================================================================
// Metric Card - Faiston Academy Dashboard
// =============================================================================
// Compact card displaying a single metric with optional trend indicator.
// Used in dashboard grids to show learning statistics.
// =============================================================================

'use client';

import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
}

export function MetricCard({ icon: Icon, label, value, trend, className = '' }: MetricCardProps) {
  return (
    <div className={`bg-white/5 border border-white/10 rounded-xl p-3 min-w-0 ${className}`}>
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-3.5 h-3.5 text-white/50 flex-shrink-0" />
        <span className="text-[10px] text-white/50 leading-tight truncate uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="text-lg font-bold text-white truncate">{value}</span>
        {trend === 'up' && (
          <div className="flex items-center gap-0.5 text-green-400 flex-shrink-0">
            <TrendingUp className="w-3 h-3" />
          </div>
        )}
        {trend === 'down' && (
          <div className="flex items-center gap-0.5 text-red-400 flex-shrink-0">
            <TrendingDown className="w-3 h-3" />
          </div>
        )}
      </div>
    </div>
  );
}
