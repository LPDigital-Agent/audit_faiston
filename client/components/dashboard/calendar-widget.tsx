"use client";

import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Calendar, Clock, MapPin, Users } from "lucide-react";
import { calendarEvents } from "@/mocks/mock-data";
import { formatTime, cn } from "@/lib/utils";

/**
 * CalendarWidget - Upcoming events widget
 *
 * Shows the next calendar events from Outlook.
 * Read-only in Phase 1.
 */

export function CalendarWidget() {
  // Get today's events
  const todayEvents = calendarEvents.slice(0, 3);

  return (
    <GlassCard className="h-full flex flex-col">
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-blue-light" />
          <GlassCardTitle>Calendário</GlassCardTitle>
        </div>
        <Badge variant="outline" className="text-xs">
          Hoje
        </Badge>
      </GlassCardHeader>

      <ScrollArea className="flex-1 -mx-4 px-4">
        <div className="space-y-3">
          {todayEvents.map((event, index) => (
            <EventCard key={event.id} event={event} isNext={index === 0} />
          ))}
        </div>
      </ScrollArea>
    </GlassCard>
  );
}

interface EventCardProps {
  event: (typeof calendarEvents)[0];
  isNext?: boolean;
}

function EventCard({ event, isNext }: EventCardProps) {
  const startTime = formatTime(event.start);
  const endTime = formatTime(event.end);

  return (
    <div
      className={cn(
        "p-3 rounded-lg",
        "border border-border",
        "transition-all duration-150",
        isNext
          ? "bg-blue-dark/20 border-blue-mid/30"
          : "bg-white/5 hover:bg-white/10"
      )}
    >
      {/* Time */}
      <div className="flex items-center gap-2 mb-2">
        <Clock className="w-3 h-3 text-text-muted" />
        <span className="text-xs text-text-muted">
          {startTime} - {endTime}
        </span>
        {isNext && (
          <Badge className="ml-auto text-[10px] bg-blue-mid text-white">
            Próxima
          </Badge>
        )}
      </div>

      {/* Title */}
      <h4 className="text-sm font-medium text-text-primary mb-2">
        {event.title}
      </h4>

      {/* Details */}
      <div className="flex items-center gap-4 text-xs text-text-muted">
        <div className="flex items-center gap-1">
          <MapPin className="w-3 h-3" />
          <span>{event.location}</span>
        </div>
        <div className="flex items-center gap-1">
          <Users className="w-3 h-3" />
          <span>{event.attendees.length}</span>
        </div>
      </div>
    </div>
  );
}

export default CalendarWidget;
