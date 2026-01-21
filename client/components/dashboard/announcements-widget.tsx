"use client";

import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Megaphone, ChevronRight } from "lucide-react";
import { announcements } from "@/mocks/mock-data";
import { formatRelativeTime, cn } from "@/lib/utils";

/**
 * AnnouncementsWidget - Corporate announcements and news
 *
 * Displays important company-wide announcements.
 */

const priorityColors: Record<string, string> = {
  high: "bg-red-500/20 text-red-400 border-red-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-green-500/20 text-green-400 border-green-500/30",
};

const typeIcons: Record<string, string> = {
  policy: "📋",
  business: "📊",
  it: "🔧",
  hr: "👥",
};

export function AnnouncementsWidget() {
  return (
    <GlassCard className="h-full flex flex-col">
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <Megaphone className="w-4 h-4 text-accent-warning" />
          <GlassCardTitle>Comunicados</GlassCardTitle>
        </div>
        <Badge variant="outline" className="text-xs">
          {announcements.length}
        </Badge>
      </GlassCardHeader>

      <ScrollArea className="flex-1 -mx-4 px-4">
        <div className="space-y-2">
          {announcements.map((announcement) => (
            <AnnouncementCard key={announcement.id} announcement={announcement} />
          ))}
        </div>
      </ScrollArea>
    </GlassCard>
  );
}

interface AnnouncementCardProps {
  announcement: (typeof announcements)[0];
}

function AnnouncementCard({ announcement }: AnnouncementCardProps) {
  const timeAgo = formatRelativeTime(announcement.publishedAt);
  const priorityColor = priorityColors[announcement.priority] || priorityColors.low;
  const typeIcon = typeIcons[announcement.type] || "📢";

  return (
    <div
      className={cn(
        "p-3 rounded-lg",
        "border border-border",
        "transition-all duration-150",
        "hover:bg-white/5 cursor-pointer",
        "group"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm">{typeIcon}</span>
        <span className="text-xs text-text-muted">{announcement.author}</span>
        <Badge className={cn("ml-auto text-[10px] border", priorityColor)}>
          {announcement.priority === "high" ? "Importante" : "Info"}
        </Badge>
      </div>

      {/* Title */}
      <h4 className="text-sm font-medium text-text-primary mb-1 group-hover:text-blue-light transition-colors">
        {announcement.title}
      </h4>

      {/* Content preview */}
      <p className="text-xs text-text-muted line-clamp-2 mb-2">
        {announcement.content}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>{timeAgo}</span>
        <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  );
}

export default AnnouncementsWidget;
