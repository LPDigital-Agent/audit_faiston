"use client";

import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { Button } from "@/components/ui/button";
import { Calendar, MessageSquare, BarChart3, Search, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * QuickActions - Shortcut buttons for common actions
 *
 * Provides quick access to frequently used features.
 */

const actions = [
  {
    id: "schedule",
    label: "Agendar",
    icon: Calendar,
    color: "blue",
    action: "schedule-meeting",
  },
  {
    id: "message",
    label: "Mensagem",
    icon: MessageSquare,
    color: "magenta",
    action: "send-message",
  },
  {
    id: "reports",
    label: "Relatórios",
    icon: BarChart3,
    color: "blue",
    action: "view-reports",
  },
  {
    id: "search",
    label: "Buscar",
    icon: Search,
    color: "magenta",
    action: "search",
  },
];

const colorClasses = {
  blue: {
    bg: "bg-blue-dark/20 hover:bg-blue-dark/30",
    icon: "text-blue-light",
    border: "border-blue-mid/20 hover:border-blue-mid/40",
  },
  magenta: {
    bg: "bg-magenta-dark/20 hover:bg-magenta-dark/30",
    icon: "text-magenta-light",
    border: "border-magenta-mid/20 hover:border-magenta-mid/40",
  },
};

export function QuickActions() {
  const handleAction = (action: string) => {
    console.log("Quick action:", action);
    // TODO: Implement action handlers
  };

  return (
    <GlassCard className="h-full flex flex-col">
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent-warning" />
          <GlassCardTitle>Ações Rápidas</GlassCardTitle>
        </div>
      </GlassCardHeader>

      <div className="flex-1 grid grid-cols-2 gap-2">
        {actions.map((action) => {
          const Icon = action.icon;
          const colors = colorClasses[action.color as keyof typeof colorClasses];

          return (
            <Button
              key={action.id}
              variant="outline"
              onClick={() => handleAction(action.action)}
              className={cn(
                "h-auto flex-col gap-2 py-4",
                "border transition-all duration-150",
                colors.bg,
                colors.border
              )}
            >
              <Icon className={cn("w-5 h-5", colors.icon)} />
              <span className="text-xs text-text-primary">{action.label}</span>
            </Button>
          );
        })}
      </div>
    </GlassCard>
  );
}

export default QuickActions;
