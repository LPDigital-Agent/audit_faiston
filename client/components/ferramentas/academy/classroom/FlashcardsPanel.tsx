// =============================================================================
// Flashcards Panel - Faiston Academy
// =============================================================================
// AI-powered flashcard generation and study interface.
// Uses spaced repetition principles for effective learning.
// =============================================================================

'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Zap,
  ChevronLeft,
  ChevronRight,
  Check,
  HelpCircle,
  Sparkles,
  RefreshCw,
  RotateCcw,
  Trophy,
  Target,
  BookOpen,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MarkdownContent } from '@/components/ui/markdown-content';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import { useFlashcards, EXAMPLE_PROMPTS } from '@/hooks/academy/useFlashcards';

interface FlashcardsPanelProps {
  episodeId: string;
  transcription?: string; // Optional - if provided, use directly; otherwise fetch from file
}

// Generate transcription path based on courseId and episodeId
function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

// Difficulty options with colors
const DIFFICULTY_OPTIONS = [
  { value: 'easy', label: 'Facil', color: 'bg-green-500/20 text-green-400 border-green-500/30' },
  {
    value: 'medium',
    label: 'Medio',
    color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  },
  { value: 'hard', label: 'Dificil', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
] as const;

export function FlashcardsPanel({ episodeId }: FlashcardsPanelProps) {
  const { courseId } = useAcademyClassroom();
  const [view, setView] = useState<'settings' | 'cards' | 'completed'>('settings');
  const [transcription, setTranscription] = useState<string>('');
  const [loadingTranscription, setLoadingTranscription] = useState(false);

  const {
    currentCard,
    currentIndex,
    isFlipped,
    settings,
    progress,
    nextCard,
    prevCard,
    flipCard,
    markAsKnown,
    markForReview,
    updateSettings,
    resetFlashcards,
    restartStudy,
    startReviewMode,
    generate,
    isGenerating,
    generateError,
    hasCards,
    isCurrentKnown,
    canGoNext,
    canGoPrev,
    isLastCard,
    hasCardsForReview,
    cardsForReview,
  } = useFlashcards(courseId, episodeId);

  // Keyboard navigation (only when panel is focused)
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (!hasCards) return;

      switch (e.key) {
        case ' ': // Space - flip
        case 'Enter':
          e.preventDefault();
          e.stopPropagation();
          flipCard();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          e.stopPropagation();
          prevCard();
          break;
        case 'ArrowRight':
          e.preventDefault();
          e.stopPropagation();
          nextCard();
          break;
        case 'ArrowUp': // Mark as known
        case 'k':
          e.preventDefault();
          markAsKnown();
          break;
        case 'ArrowDown': // Mark for review
        case 'j':
          e.preventDefault();
          markForReview();
          break;
      }
    },
    [hasCards, flipCard, nextCard, prevCard, markAsKnown, markForReview]
  );

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

  // If we have cards, show cards view
  useEffect(() => {
    if (hasCards) {
      setView('cards');
    }
  }, [hasCards]);

  // Handle generate button
  const handleGenerate = () => {
    if (transcription) {
      generate(transcription);
    }
  };

  // Handle start over (generate new cards)
  const handleStartOver = () => {
    resetFlashcards();
    setView('settings');
  };

  // Handle restart study (keep cards, reset progress)
  const handleRestartStudy = () => {
    restartStudy();
    setView('cards');
  };

  // Handle review mode (only review cards not known)
  const handleStartReview = () => {
    startReviewMode();
    setView('cards');
  };

  // Handle marking as known on last card - go to completion screen
  const handleMarkAsKnownWithCompletion = () => {
    markAsKnown();
    if (isLastCard || cardsForReview.length <= 1) {
      setView('completed');
    }
  };

  // Handle marking for review on last card - go to completion screen
  const handleMarkForReviewWithCompletion = () => {
    markForReview();
    if (isLastCard) {
      setView('completed');
    }
  };

  // Render Settings View
  if (view === 'settings') {
    return (
      <div className="h-full flex flex-col bg-black/20">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Zap className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Flashcards AI</h3>
              <p className="text-xs text-white/40">Gere cartoes de estudo automaticamente</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-6">
            {/* Difficulty Selector */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-3">
                Nivel de Dificuldade
              </label>
              <div className="flex gap-2">
                {DIFFICULTY_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => updateSettings({ difficulty: option.value })}
                    className={`flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-all ${
                      settings.difficulty === option.value
                        ? option.color
                        : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Number of Cards */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-3">
                Quantidade de Cartoes
              </label>
              <div className="flex gap-2">
                {[5, 10, 15, 20].map((num) => (
                  <button
                    key={num}
                    onClick={() => updateSettings({ numCards: num })}
                    className={`flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-all ${
                      settings.numCards === num
                        ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20 text-[var(--faiston-magenta-mid,#C31B8C)] border-[var(--faiston-magenta-mid,#C31B8C)]/30'
                        : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
                    }`}
                  >
                    {num}
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Prompt */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-3">
                Instrucoes Personalizadas (opcional)
              </label>
              <Textarea
                value={settings.customPrompt}
                onChange={(e) => updateSettings({ customPrompt: e.target.value })}
                placeholder="Ex: Foque em conceitos praticos..."
                className="bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none min-h-[80px]"
              />
            </div>

            {/* Example Prompts */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-3">
                <Sparkles className="w-4 h-4 inline-block mr-1 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                Sugestoes de Prompts
              </label>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_PROMPTS.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => updateSettings({ customPrompt: prompt })}
                    className="px-3 py-1.5 rounded-full text-xs bg-white/5 text-white/60 border border-white/10 hover:bg-white/10 hover:text-white/80 transition-all"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {/* Error Message */}
            {generateError && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                Erro ao gerar flashcards. Tente novamente.
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="p-4 border-t border-white/5">
          <Button
            onClick={handleGenerate}
            disabled={isGenerating || loadingTranscription || !transcription}
            className="w-full h-12 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white font-semibold rounded-xl border-0 transition-all"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                Gerando Flashcards...
              </>
            ) : (
              <>
                <Zap className="w-4 h-4 mr-2" />
                Gerar {settings.numCards} Flashcards
              </>
            )}
          </Button>
          {loadingTranscription && (
            <p className="text-xs text-white/40 text-center mt-2">Carregando transcricao...</p>
          )}
        </div>
      </div>
    );
  }

  // Render Completion View
  if (view === 'completed') {
    const isPerfect = progress.percentage === 100;
    const reviewCount = cardsForReview.length;

    return (
      <div className="h-full flex flex-col bg-black/20">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Zap className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <span className="text-base font-medium text-white">Sessao Completa</span>
          </div>
          <button
            onClick={handleStartOver}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-all"
            title="Gerar novos cards"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Completion Content */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
          {/* Icon based on performance */}
          <motion.div
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', damping: 15, stiffness: 200 }}
            className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 ${
              isPerfect
                ? 'bg-gradient-to-br from-yellow-500/30 to-orange-500/30 border-2 border-yellow-500/50'
                : 'bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/30 to-[var(--faiston-blue-mid,#2226C0)]/30 border-2 border-[var(--faiston-magenta-mid,#C31B8C)]/50'
            }`}
          >
            {isPerfect ? (
              <Trophy className="w-10 h-10 text-yellow-400" />
            ) : (
              <Target className="w-10 h-10 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            )}
          </motion.div>

          {/* Title */}
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl font-bold text-white mb-2"
          >
            {isPerfect ? 'Parabens!' : 'Sessao Finalizada!'}
          </motion.h2>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-white/60 text-sm mb-6"
          >
            {isPerfect
              ? 'Voce dominou todos os flashcards!'
              : `Voce dominou ${progress.known} de ${progress.total} cards`}
          </motion.p>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="w-full max-w-xs mb-6"
          >
            <div className="flex items-center justify-between text-xs text-white/60 mb-2">
              <span>Progresso</span>
              <span>{progress.percentage}%</span>
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progress.percentage}%` }}
                transition={{ duration: 0.8, ease: 'easeOut', delay: 0.5 }}
                className={`h-full rounded-full ${
                  isPerfect
                    ? 'bg-gradient-to-r from-yellow-500 to-orange-500'
                    : 'bg-gradient-to-r from-green-500 to-green-400'
                }`}
              />
            </div>
            <div className="flex justify-between text-xs mt-2">
              <span className="text-green-400">{progress.known} dominados</span>
              <span className="text-red-400">{reviewCount} para revisar</span>
            </div>
          </motion.div>

          {/* Action Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="w-full max-w-xs space-y-3"
          >
            {/* Review Button - only if there are cards to review */}
            {hasCardsForReview && (
              <Button
                onClick={handleStartReview}
                className="w-full bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 text-white border-0"
              >
                <HelpCircle className="w-4 h-4 mr-2" />
                Revisar {reviewCount} {reviewCount === 1 ? 'Card' : 'Cards'}
              </Button>
            )}

            {/* Restart Study Button */}
            <Button
              onClick={handleRestartStudy}
              variant="outline"
              className="w-full bg-white/5 border-white/20 text-white hover:bg-white/10"
            >
              <BookOpen className="w-4 h-4 mr-2" />
              Estudar Novamente
            </Button>

            {/* Generate New Cards Button */}
            <Button
              onClick={handleStartOver}
              variant="ghost"
              className="w-full text-white/60 hover:text-white hover:bg-white/10"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Gerar Novos Flashcards
            </Button>
          </motion.div>
        </div>
      </div>
    );
  }

  // Render Cards View
  return (
    <div
      className="h-full flex flex-col outline-none bg-black/20"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
            <Zap className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </div>
          <span className="text-base font-medium text-white">Flashcards</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">
            {currentIndex + 1} / {progress.total}
          </span>
          <button
            onClick={handleStartOver}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-all"
            title="Comecar novamente"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Card Container */}
      <div className="flex-1 flex flex-col items-center justify-center p-4">
        {currentCard && (
          <>
            {/* Flip Card */}
            <div
              className="w-full max-w-sm aspect-[3/4] cursor-pointer perspective-1000"
              onClick={flipCard}
            >
              <AnimatePresence mode="wait">
                <motion.div
                  key={isFlipped ? 'back' : 'front'}
                  initial={{ rotateY: isFlipped ? -90 : 90, opacity: 0 }}
                  animate={{ rotateY: 0, opacity: 1 }}
                  exit={{ rotateY: isFlipped ? 90 : -90, opacity: 0 }}
                  transition={{ duration: 0.3, ease: 'easeOut' }}
                  className={`w-full h-full rounded-2xl p-4 flex flex-col items-center text-center relative overflow-hidden ${
                    isFlipped
                      ? 'bg-gradient-to-br from-[var(--faiston-blue-mid,#2226C0)]/20 to-[var(--faiston-magenta-mid,#C31B8C)]/20 border border-[var(--faiston-blue-mid,#2226C0)]/30'
                      : 'bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 border border-[var(--faiston-magenta-mid,#C31B8C)]/30'
                  }`}
                >
                  {/* Card Label */}
                  <div
                    className={`shrink-0 mt-2 mb-3 px-3 py-1.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                      isFlipped
                        ? 'bg-[var(--faiston-blue-mid,#2226C0)]/30 text-blue-300 border border-[var(--faiston-blue-mid,#2226C0)]/20'
                        : 'bg-[var(--faiston-magenta-mid,#C31B8C)]/30 text-pink-300 border border-[var(--faiston-magenta-mid,#C31B8C)]/20'
                    }`}
                  >
                    {isFlipped ? 'Resposta' : 'Pergunta'}
                  </div>

                  {/* Known Badge */}
                  {isCurrentKnown && (
                    <div className="absolute top-3 right-3 p-1.5 rounded-full bg-green-500/30">
                      <Check className="w-3 h-3 text-green-400" />
                    </div>
                  )}

                  {/* Card Content */}
                  <ScrollArea className="flex-1 w-full px-2 min-h-0">
                    <div className="py-2">
                      <MarkdownContent
                        content={
                          isFlipped
                            ? (currentCard.back ?? currentCard.answer ?? '')
                            : (currentCard.front ?? currentCard.question ?? '')
                        }
                      />
                    </div>
                  </ScrollArea>

                  {/* Tags */}
                  {(currentCard.tags?.length ?? 0) > 0 && (
                    <div className="shrink-0 flex flex-wrap gap-1 mt-2 justify-center max-w-full px-2">
                      {currentCard.tags?.slice(0, 3).map((tag, index) => (
                        <span
                          key={index}
                          className="px-2 py-0.5 rounded-full text-xs bg-white/10 text-white/60 truncate max-w-[100px]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Flip Hint */}
                  <div className="shrink-0 mt-3 pb-1 text-center">
                    <div className="text-xs text-white/40">Clique para virar</div>
                    <div className="text-[10px] text-white/30 mt-0.5">Espaco | ← → navegar</div>
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>

            {/* Navigation */}
            <div className="flex items-center gap-4 mt-6">
              <Button
                variant="ghost"
                size="icon"
                onClick={prevCard}
                disabled={!canGoPrev}
                className="text-white/60 hover:text-white hover:bg-white/10 disabled:opacity-30"
              >
                <ChevronLeft className="w-6 h-6" />
              </Button>

              {/* Know / Review Buttons */}
              <div className="flex gap-2">
                <Button
                  onClick={handleMarkForReviewWithCompletion}
                  variant="ghost"
                  className="bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30"
                >
                  <HelpCircle className="w-4 h-4 mr-2" />
                  Revisar
                </Button>
                <Button
                  onClick={handleMarkAsKnownWithCompletion}
                  variant="ghost"
                  className="bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/30"
                >
                  <Check className="w-4 h-4 mr-2" />
                  Sei
                </Button>
              </div>

              <Button
                variant="ghost"
                size="icon"
                onClick={nextCard}
                disabled={!canGoNext}
                className="text-white/60 hover:text-white hover:bg-white/10 disabled:opacity-30"
              >
                <ChevronRight className="w-6 h-6" />
              </Button>
            </div>
          </>
        )}
      </div>

      {/* Progress Footer */}
      <div className="p-4 border-t border-white/5">
        <div className="flex items-center justify-between text-xs text-white/60 mb-2">
          <span>Progresso</span>
          <span>
            {progress.known} de {progress.total} ({progress.percentage}%)
          </span>
        </div>
        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress.percentage}%` }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="h-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] rounded-full"
          />
        </div>
      </div>
    </div>
  );
}
