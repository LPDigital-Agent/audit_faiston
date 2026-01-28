// =============================================================================
// Transcription Panel - Faiston Academy
// =============================================================================
// Displays timestamped transcription with auto-scroll to current position.
// Click on any line to seek video to that timestamp.
// =============================================================================

'use client';

import { useState, useEffect, useMemo, useRef, useCallback, startTransition } from 'react';
import { Type } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';

interface TranscriptEntry {
  time: number; // seconds (e.g., 5.19)
  text: string;
}

interface TranscriptionPanelProps {
  currentTime: number;
  courseId: string;
  episodeId: string;
  onSeek: (time: number) => void;
}

// Generate transcription path based on courseId and episodeId
function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

// Parse transcript content into structured entries
function parseTranscription(content: string): TranscriptEntry[] {
  return content
    .split('\n')
    .filter((line) => /^\d{2}:\d{2}:\d{2}\.\d{3}/.test(line))
    .map((line) => {
      const match = line.match(/^(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+(.*)$/);
      if (!match) return null;
      const [, h, m, s, ms, text] = match;
      const time =
        parseInt(h) * 3600 + parseInt(m) * 60 + parseInt(s) + parseInt(ms) / 1000;
      return { time, text };
    })
    .filter(Boolean) as TranscriptEntry[];
}

// Format seconds to MM:SS display
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function TranscriptionPanel({
  currentTime,
  courseId,
  episodeId,
  onSeek,
}: TranscriptionPanelProps) {
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeLineRef = useRef<HTMLDivElement>(null);
  const lastScrolledIndex = useRef<number>(-1);

  // Load transcript when course/episode changes
  useEffect(() => {
    const abortController = new AbortController();
    const url = getTranscriptionPath(courseId, episodeId);

    startTransition(() => {
      setLoading(true);
      setError(null);
    });

    fetch(url, { signal: abortController.signal })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load');
        return r.text();
      })
      .then((content) => {
        const parsed = parseTranscription(content);
        startTransition(() => {
          setEntries(parsed);
          setLoading(false);
        });
      })
      .catch((err) => {
        // Ignore abort errors (expected on unmount/navigation)
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        startTransition(() => {
          setError('Erro ao carregar transcricao');
          setLoading(false);
        });
      });

    return () => abortController.abort();
  }, [courseId, episodeId]);

  // Find current active entry index based on video time
  const activeIndex = useMemo(() => {
    if (entries.length === 0) return -1;
    // Find the last entry that starts before or at current time
    for (let i = entries.length - 1; i >= 0; i--) {
      if (entries[i].time <= currentTime) return i;
    }
    return 0;
  }, [entries, currentTime]);

  // Auto-scroll to active line when it changes
  useEffect(() => {
    if (activeIndex >= 0 && activeIndex !== lastScrolledIndex.current) {
      lastScrolledIndex.current = activeIndex;
      // Small delay to ensure DOM is updated
      requestAnimationFrame(() => {
        activeLineRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      });
    }
  }, [activeIndex]);

  // Handle click on transcript line
  const handleLineClick = useCallback(
    (time: number) => {
      onSeek(time);
    },
    [onSeek]
  );

  if (loading) {
    return (
      <div className="h-full flex flex-col bg-black/20">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-white/50 text-sm animate-pulse">Carregando transcricao...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex flex-col bg-black/20">
        <div className="flex-1 flex flex-col items-center justify-center gap-2 p-4">
          <Type className="w-8 h-8 text-white/30" />
          <div className="text-white/50 text-sm text-center">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-black/20">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Type className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Transcricao</h3>
              <p className="text-xs text-white/40">Acompanhe o texto da aula</p>
            </div>
          </div>
          <span className="text-xs text-white/40">{entries.length} linhas</span>
        </div>
      </div>

      {/* Scrollable transcript content */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-1">
          {entries.map((entry, index) => {
            const isActive = index === activeIndex;
            const isPast = index < activeIndex;

            return (
              <div
                key={index}
                ref={isActive ? activeLineRef : undefined}
                onClick={() => handleLineClick(entry.time)}
                className={cn(
                  'group flex gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150',
                  isActive && [
                    'bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)]/15 to-[var(--faiston-magenta-mid,#C31B8C)]/5',
                    'border-l-[3px] border-l-[var(--faiston-magenta-mid,#C31B8C)]',
                  ],
                  !isActive && 'hover:bg-white/5 border-l-[3px] border-l-transparent'
                )}
              >
                {/* Timestamp badge */}
                <span
                  className={cn(
                    'flex-shrink-0 text-xs font-mono px-1.5 py-0.5 rounded transition-colors',
                    isActive
                      ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20 text-[var(--faiston-magenta-mid,#C31B8C)]'
                      : 'bg-white/5 text-white/40 group-hover:bg-white/10 group-hover:text-white/60'
                  )}
                >
                  {formatTime(entry.time)}
                </span>

                {/* Text content */}
                <span
                  className={cn(
                    'text-sm leading-relaxed transition-colors',
                    isActive && 'text-white font-medium',
                    isPast && !isActive && 'text-white/50',
                    !isPast && !isActive && 'text-white/35'
                  )}
                >
                  {entry.text}
                </span>
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Footer with word count */}
      <div className="px-6 py-3 border-t border-white/5">
        <div className="flex items-center justify-between text-xs text-white/40">
          <span>Clique para navegar</span>
          <span>{entries.reduce((acc, e) => acc + e.text.split(' ').length, 0)} palavras</span>
        </div>
      </div>
    </div>
  );
}
