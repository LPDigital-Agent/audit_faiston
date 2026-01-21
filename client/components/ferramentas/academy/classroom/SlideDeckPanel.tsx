// =============================================================================
// Slide Deck Panel - Faiston Academy
// =============================================================================
// AI-powered slide deck generation using batch architecture for parallel
// processing. Generates professional presentations from lesson transcriptions.
// =============================================================================

'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Presentation,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Loader2,
  StickyNote,
  ChevronDown,
  ChevronUp,
  ImageIcon,
  History,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import {
  useSlideDeck,
  DECK_ARCHETYPES,
  type SlideDeckHistoryItem,
  type GenerationProgress,
} from '@/hooks/academy/useSlideDeck';
import type { Slide } from '@/lib/academy/types';

interface SlideDeckPanelProps {
  episodeId: string;
  transcription?: string;
}

// Dynamic transcription path based on course and episode
function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

// Get progress message based on phase
const getProgressMessage = (progress: GenerationProgress | null) => {
  if (!progress) return 'Preparando...';

  switch (progress.phase) {
    case 'planning':
      return progress.message || 'Analisando conteudo...';
    case 'generating':
      return progress.message || `Gerando lote ${progress.current}/${progress.total}...`;
    case 'complete':
      return 'Apresentacao pronta!';
    default:
      return 'Processando...';
  }
};

// Calculate progress percentage from GenerationProgress
const getProgressPercentage = (progress: GenerationProgress | null): number => {
  if (!progress) return 0;

  switch (progress.phase) {
    case 'planning':
      return 10;
    case 'generating': {
      const total = progress.total || 1;
      const current = progress.current || 0;
      const batchProgress = (current / total) * 85;
      return Math.min(95, Math.max(10, 10 + batchProgress));
    }
    case 'complete':
      return 100;
    default:
      return 0;
  }
};

// =============================================================================
// Slide Preview Component with AI-generated image
// =============================================================================
function SlidePreview({
  slide,
  index,
  totalSlides,
  onNext,
  onPrev,
  isFirst,
  isLast,
}: {
  slide: Slide;
  index: number;
  totalSlides: number;
  onNext: () => void;
  onPrev: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const handleSlideClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;

    if (clickX > width * 0.3) {
      if (!isLast) onNext();
    } else {
      if (!isFirst) onPrev();
    }
  };

  return (
    <div
      onClick={handleSlideClick}
      className="aspect-[16/9] rounded-xl overflow-hidden relative bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 border border-white/10 cursor-pointer group"
    >
      {/* Loading state */}
      {isLoading && !hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/5">
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-8 h-8 text-[var(--faiston-magenta-mid,#C31B8C)] animate-spin" />
            <span className="text-xs text-white/40">Carregando slide...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {hasError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/5">
          <ImageIcon className="w-12 h-12 text-white/20 mb-2" />
          <span className="text-sm text-white/40">{slide.title}</span>
          <span className="text-xs text-white/20 mt-1">Imagem nao disponivel</span>
        </div>
      )}

      {/* Slide image */}
      {slide.image_url && (
        <img
          src={slide.image_url}
          alt={slide.title}
          className={`w-full h-full object-contain ${isLoading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300 pointer-events-none`}
          loading="lazy"
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false);
            setHasError(true);
          }}
        />
      )}

      {/* Floating navigation arrows */}
      {!isFirst && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPrev();
          }}
          className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center text-white/70 hover:text-white hover:bg-black/70 transition-all opacity-0 group-hover:opacity-100"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>
      )}
      {!isLast && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onNext();
          }}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center text-white/70 hover:text-white hover:bg-black/70 transition-all opacity-0 group-hover:opacity-100"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      )}

      {/* Slide number badge */}
      <div className="absolute bottom-3 right-3 px-2 py-0.5 rounded-full bg-black/50 text-white/60 text-xs">
        {index + 1}/{totalSlides}
      </div>

      {/* Click hint */}
      <div className="absolute bottom-3 left-3 px-2 py-0.5 rounded-full bg-black/50 text-white/40 text-xs opacity-0 group-hover:opacity-100 transition-opacity">
        Clique para navegar
      </div>
    </div>
  );
}

// =============================================================================
// Thumbnail Component
// =============================================================================
function SlideThumbnail({
  slide,
  index,
  isActive,
  onClick,
}: {
  slide: Slide;
  index: number;
  isActive: boolean;
  onClick: () => void;
}) {
  const [isLoading, setIsLoading] = useState(true);

  return (
    <button
      onClick={onClick}
      className={`w-20 h-12 rounded-lg overflow-hidden border-2 ${
        isActive ? 'border-[var(--faiston-magenta-mid,#C31B8C)]' : 'border-transparent'
      } flex items-center justify-center transition-all hover:scale-105 shrink-0 relative bg-white/5`}
    >
      {slide.image_url ? (
        <>
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs text-white/40">{index + 1}</span>
            </div>
          )}
          <img
            src={slide.image_url}
            alt={slide.title}
            className={`w-full h-full object-cover ${isLoading ? 'opacity-0' : 'opacity-100'}`}
            loading="lazy"
            onLoad={() => setIsLoading(false)}
            onError={() => setIsLoading(false)}
          />
        </>
      ) : (
        <span className="text-xs text-white/70">{index + 1}</span>
      )}
    </button>
  );
}

export function SlideDeckPanel({ episodeId }: SlideDeckPanelProps) {
  const { courseId, episodeTitle } = useAcademyClassroom();

  const [view, setView] = useState<'settings' | 'result'>('settings');
  const [transcription, setTranscription] = useState<string>('');
  const [loadingTranscription, setLoadingTranscription] = useState(false);
  const [showNotes, setShowNotes] = useState(false);

  const {
    deckData,
    currentSlide,
    currentSlideIndex,
    totalSlides,
    nextSlide,
    prevSlide,
    goToSlide,
    settings,
    updateSettings,
    history,
    loadFromHistory,
    hasHistory,
    generate,
    resetDeck,
    isGenerating,
    generateError,
    hasDeck,
    isFirstSlide,
    isLastSlide,
    progress,
  } = useSlideDeck({
    courseId,
    episodeId,
    episodeTitle: episodeTitle || `Aula ${episodeId}`,
  });

  const progressPercentage = getProgressPercentage(progress);
  const progressMessage = getProgressMessage(progress);

  // Load transcription when course/episode changes
  useEffect(() => {
    const url = getTranscriptionPath(courseId, episodeId);
    setLoadingTranscription(true);
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load');
        return r.text();
      })
      .then((content) => {
        setTranscription(content);
        setLoadingTranscription(false);
      })
      .catch(() => {
        setLoadingTranscription(false);
      });
  }, [courseId, episodeId]);

  // Switch to result view when deck is generated
  useEffect(() => {
    if (hasDeck) {
      setView('result');
    }
  }, [hasDeck]);

  const handleGenerate = () => {
    if (transcription) {
      generate(transcription);
    }
  };

  const handleStartOver = () => {
    resetDeck();
    setView('settings');
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (view !== 'result') return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.key === 'ArrowRight') {
        nextSlide();
      } else if (e.key === 'ArrowLeft') {
        prevSlide();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [view, nextSlide, prevSlide]);

  // ========== SETTINGS VIEW ==========
  if (view === 'settings') {
    return (
      <div className="h-full flex flex-col bg-black/20">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Presentation className="w-6 h-6 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white">Slide Deck</h3>
              <p className="text-sm text-white/40">Gere uma apresentacao profissional com IA.</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1">
          <div className="p-6 space-y-6">
            {/* Archetype Selection */}
            <div>
              <label className="block text-sm font-medium text-white/60 mb-2">
                Escolha o Estilo
              </label>
              <div className="grid grid-cols-2 gap-2">
                {DECK_ARCHETYPES.map((archetype) => {
                  const isSelected = settings.archetype === archetype.id;
                  return (
                    <button
                      key={archetype.id}
                      onClick={() => updateSettings({ archetype: archetype.id })}
                      className={`px-3 py-2 rounded-lg border text-left transition-all flex items-center gap-2 ${
                        isSelected
                          ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20 border-[var(--faiston-magenta-mid,#C31B8C)]/50'
                          : 'bg-white/[0.03] border-white/10 hover:bg-white/[0.06] hover:border-white/20'
                      }`}
                    >
                      <span className="text-base flex-shrink-0">{archetype.emoji}</span>
                      <span
                        className={`text-xs font-medium truncate ${isSelected ? 'text-[var(--faiston-magenta-mid,#C31B8C)]' : 'text-white/70'}`}
                      >
                        {archetype.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* History Section */}
            {hasHistory && (
              <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10">
                <div className="flex items-center gap-2 mb-3">
                  <History className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                  <span className="text-sm font-medium text-white">Apresentacoes Anteriores</span>
                  <span className="text-xs text-white/40">({history.length}/3)</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {history.map((item: SlideDeckHistoryItem, index: number) => (
                    <button
                      key={item.id}
                      onClick={() => loadFromHistory(item.id)}
                      className="group relative aspect-video rounded-lg overflow-hidden border border-white/10 hover:border-[var(--faiston-magenta-mid,#C31B8C)]/50 transition-all"
                    >
                      {item.thumbnailUrl ? (
                        <img
                          src={item.thumbnailUrl}
                          alt={`Apresentacao ${index + 1}`}
                          className="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity"
                        />
                      ) : (
                        <div className="w-full h-full bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center">
                          <Presentation className="w-4 h-4 text-white/40" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-1.5">
                        <div className="flex items-center gap-1 text-[10px] text-white/70">
                          <Clock className="w-2.5 h-2.5" />
                          <span>
                            {new Date(item.createdAt).toLocaleDateString('pt-BR', {
                              day: '2-digit',
                              month: 'short',
                            })}
                          </span>
                        </div>
                      </div>
                      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-[var(--faiston-magenta-mid,#C31B8C)]/10 flex items-center justify-center">
                        <span className="text-[10px] font-medium text-[var(--faiston-magenta-mid,#C31B8C)]">
                          Carregar
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-white/30 mt-2 text-center">
                  Clique para carregar uma apresentacao anterior
                </p>
              </div>
            )}

            {/* Error Message */}
            {generateError && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                <p className="font-medium">Falha na geracao</p>
                <p className="text-xs opacity-70 mt-1">{generateError.message}</p>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="p-5 border-t border-white/5">
          {isGenerating ? (
            <div className="space-y-3">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-[var(--faiston-magenta-mid,#C31B8C)] animate-pulse">
                  {progressMessage}
                </span>
                <span className="text-white/40">{Math.round(progressPercentage)}%</span>
              </div>
              <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: '0%' }}
                  animate={{ width: `${progressPercentage}%` }}
                  transition={{ duration: 0.5 }}
                  className="h-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] via-[var(--faiston-blue-mid,#2226C0)] to-[var(--faiston-magenta-mid,#C31B8C)]"
                />
              </div>
              {progress?.phase === 'generating' && progress.total > 0 && (
                <p className="text-xs text-white/40 text-center">
                  Lote {progress.current}/{progress.total} em paralelo
                </p>
              )}
              <p className="text-xs text-white/30 text-center">
                ⏱️ Geracao paralela (mais rapido)
              </p>
            </div>
          ) : (
            <>
              <Button
                onClick={handleGenerate}
                disabled={loadingTranscription || !transcription}
                className="w-full h-12 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] via-[var(--faiston-blue-mid,#2226C0)] to-[var(--faiston-magenta-mid,#C31B8C)] hover:opacity-90 text-white font-semibold rounded-xl border-0 transition-all"
              >
                Gerar Apresentacao
                <Presentation className="w-5 h-5 ml-2" />
              </Button>
              <p className="text-xs text-white/30 text-center mt-2">
                ⏱️ Geracao paralela (mais rapido)
              </p>
            </>
          )}
          {loadingTranscription && (
            <p className="text-xs text-white/30 text-center mt-2 animate-pulse">
              Preparando transcricao...
            </p>
          )}
        </div>
      </div>
    );
  }

  // ========== RESULT VIEW ==========
  return (
    <div className="h-full flex flex-col bg-black/20">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Presentation className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          <span className="text-sm font-medium text-white/80 truncate max-w-[180px]">
            {deckData?.deck_title || 'Apresentacao'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">
            {currentSlideIndex + 1}/{totalSlides}
          </span>
          <button
            onClick={handleStartOver}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white/80 transition-all"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Slide Preview */}
      <div className="flex-1 p-4 flex flex-col">
        <div className="flex-1 relative">
          <AnimatePresence mode="wait">
            {currentSlide && (
              <motion.div
                key={currentSlide.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="relative"
              >
                <SlidePreview
                  slide={currentSlide}
                  index={currentSlideIndex}
                  totalSlides={totalSlides}
                  onNext={nextSlide}
                  onPrev={prevSlide}
                  isFirst={isFirstSlide}
                  isLast={isLastSlide}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Speaker Notes */}
        {currentSlide?.speaker_notes && (
          <div className="mt-3">
            <button
              onClick={() => setShowNotes(!showNotes)}
              className="flex items-center gap-2 text-xs text-white/40 hover:text-white/60 transition-colors"
            >
              <StickyNote className="w-3 h-3" />
              <span>Notas do Apresentador</span>
              {showNotes ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            <AnimatePresence>
              {showNotes && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="mt-2 p-3 rounded-lg bg-white/5 border border-white/10">
                    <p className="text-xs text-white/60 leading-relaxed">
                      {currentSlide.speaker_notes}
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="px-4 py-3 border-t border-white/10">
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent">
          {deckData?.slides.map((slide, index) => (
            <SlideThumbnail
              key={slide.id}
              slide={slide}
              index={index}
              isActive={index === currentSlideIndex}
              onClick={() => goToSlide(index)}
            />
          ))}
        </div>
        <p className="text-[10px] text-white/30 text-center mt-2">
          ← → Use as setas do teclado ou clique no slide
        </p>
      </div>
    </div>
  );
}
