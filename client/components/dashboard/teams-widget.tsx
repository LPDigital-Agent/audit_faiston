"use client";

import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { MessageSquare } from "lucide-react";
import { teamsMessages } from "@/mocks/mock-data";
import { formatRelativeTime, getInitials, truncate, cn } from "@/lib/utils";

/**
 * TeamsWidget - Microsoft Teams messages preview
 *
 * Shows recent messages from Teams channels and direct messages.
 * Read-only in Phase 1.
 */

const statusColors: Record<string, string> = {
  online: "bg-green-500",
  away: "bg-yellow-500",
  busy: "bg-red-500",
  offline: "bg-gray-500",
};

export function TeamsWidget() {
  const unreadCount = teamsMessages.filter((m) => m.unread).length;

  return (
    <GlassCard className="h-full flex flex-col">
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-accent-primary" />
          <GlassCardTitle>Teams</GlassCardTitle>
        </div>
        {unreadCount > 0 && (
          <Badge className="bg-accent-primary text-white text-xs">
            {unreadCount} nova{unreadCount > 1 ? "s" : ""}
          </Badge>
        )}
      </GlassCardHeader>

      <ScrollArea className="flex-1 -mx-4 px-4">
        <div className="space-y-2">
          {teamsMessages.map((message) => (
            <MessageCard key={message.id} message={message} />
          ))}
        </div>
      </ScrollArea>
    </GlassCard>
  );
}

interface MessageCardProps {
  message: (typeof teamsMessages)[0];
}

function MessageCard({ message }: MessageCardProps) {
  const timeAgo = formatRelativeTime(message.timestamp);
  const initials = getInitials(message.sender.name);
  const statusColor = statusColors[message.sender.status] || statusColors.offline;

  return (
    <div
      className={cn(
        "p-3 rounded-lg",
        "border border-border",
        "transition-all duration-150",
        "hover:bg-white/5 cursor-pointer",
        message.unread && "bg-accent-primary/5 border-accent-primary/20"
      )}
    >
      <div className="flex gap-3">
        {/* Avatar with status */}
        <div className="relative">
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-gradient-to-br from-blue-mid to-magenta-mid text-white text-xs">
              {initials}
            </AvatarFallback>
          </Avatar>
          <span
            className={cn(
              "absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-faiston-bg",
              statusColor
            )}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-text-primary">
              {message.sender.name}
            </span>
            <span className="text-xs text-text-muted">{timeAgo}</span>
            {message.unread && (
              <span className="w-2 h-2 rounded-full bg-accent-primary ml-auto" />
            )}
          </div>
          {message.channel !== "direct" && (
            <Badge variant="outline" className="text-[10px] mb-1">
              #{message.channel}
            </Badge>
          )}
          <p className="text-xs text-text-muted line-clamp-2">
            {truncate(message.preview, 80)}
          </p>
        </div>
      </div>
    </div>
  );
}

export default TeamsWidget;
