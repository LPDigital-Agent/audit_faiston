// =============================================================================
// useFlashcards Hook - Faiston Academy
// =============================================================================
// Hook for flashcard generation and study functionality.
// Supports spaced repetition study sessions.
// =============================================================================

'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { generateFlashcards } from '@/services/academyAgentcore';
import type { Flashcard, FlashcardsResponse } from '@/lib/academy/types';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

// Example prompts for custom flashcard generation
export const EXAMPLE_PROMPTS = [
  'Focar em definicoes',
  'Incluir exemplos praticos',
  'Perguntas de multipla escolha',
  'Conceitos-chave apenas',
  'Casos de uso reais',
] as const;

interface FlashcardWithStudy extends Flashcard {
  studied: boolean;
  known: boolean;
  studiedAt: Date | null;
}

interface FlashcardsSettings {
  difficulty: 'easy' | 'medium' | 'hard';
  numCards: number;
  customPrompt: string;
}

interface FlashcardsState {
  flashcards: FlashcardWithStudy[];
  currentIndex: number;
  isFlipped: boolean;
  settings: FlashcardsSettings;
  reviewMode: boolean;
}

const getStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.FLASHCARDS_PREFIX}${courseId}_${episodeId}`;

const getSettingsKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.FLASHCARDS_PREFIX}settings_${courseId}_${episodeId}`;

const DEFAULT_SETTINGS: FlashcardsSettings = {
  difficulty: 'medium',
  numCards: 10,
  customPrompt: '',
};

export function useFlashcards(courseId: string, episodeId: string) {
  const [state, setState] = useState<FlashcardsState | null>(null);
  const [settings, setSettings] = useState<FlashcardsSettings>(DEFAULT_SETTINGS);

  // Load from localStorage on mount
  useEffect(() => {
    const storageKey = getStorageKey(courseId, episodeId);
    const settingsKey = getSettingsKey(courseId, episodeId);
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        setState({
          ...parsed,
          flashcards: parsed.flashcards.map((fc: FlashcardWithStudy) => ({
            ...fc,
            studiedAt: fc.studiedAt ? new Date(fc.studiedAt) : null,
          })),
        });
      }

      const storedSettings = localStorage.getItem(settingsKey);
      if (storedSettings) {
        setSettings(JSON.parse(storedSettings));
      }
    } catch (e) {
      console.error('Failed to load flashcards:', e);
    }
  }, [courseId, episodeId]);

  // Save to localStorage when state changes
  useEffect(() => {
    if (state) {
      const storageKey = getStorageKey(courseId, episodeId);
      try {
        localStorage.setItem(storageKey, JSON.stringify(state));
      } catch (e) {
        console.error('Failed to save flashcards:', e);
      }
    }
  }, [state, courseId, episodeId]);

  // Save settings
  useEffect(() => {
    const settingsKey = getSettingsKey(courseId, episodeId);
    try {
      localStorage.setItem(settingsKey, JSON.stringify(settings));
    } catch (e) {
      console.error('Failed to save settings:', e);
    }
  }, [settings, courseId, episodeId]);

  // Update settings
  const updateSettings = useCallback((newSettings: Partial<FlashcardsSettings>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
  }, []);

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: async (transcription: string): Promise<FlashcardsResponse> => {
      const { data } = await generateFlashcards({
        transcription,
        difficulty: settings.difficulty,
        count: settings.numCards,
        custom_prompt: settings.customPrompt || undefined,
      });
      return data;
    },
    onSuccess: (data) => {
      const flashcardsWithStudy: FlashcardWithStudy[] = data.flashcards.map(
        (fc, index) => ({
          ...fc,
          id: fc.id || `fc-${index}`,
          studied: false,
          known: false,
          studiedAt: null,
        })
      );

      setState({
        flashcards: flashcardsWithStudy,
        currentIndex: 0,
        isFlipped: false,
        settings,
        reviewMode: false,
      });
    },
  });

  // Derived values
  const currentCard = state?.flashcards[state.currentIndex] || null;
  const hasCards = state !== null && state.flashcards.length > 0;

  const cardsForReview = useMemo(() => {
    if (!state) return [];
    return state.flashcards.filter((fc) => !fc.known);
  }, [state]);

  const progress = useMemo(() => {
    if (!state) return { total: 0, known: 0, percentage: 0 };
    const known = state.flashcards.filter((fc) => fc.known).length;
    const total = state.flashcards.length;
    return {
      total,
      known,
      percentage: total > 0 ? Math.round((known / total) * 100) : 0,
    };
  }, [state]);

  // Flip current card
  const flipCard = useCallback(() => {
    setState((prev) => (prev ? { ...prev, isFlipped: !prev.isFlipped } : null));
  }, []);

  // Mark current card as known
  const markAsKnown = useCallback(() => {
    setState((prev) => {
      if (!prev) return null;

      const updatedFlashcards = [...prev.flashcards];
      const currentCard = updatedFlashcards[prev.currentIndex];
      currentCard.studied = true;
      currentCard.known = true;
      currentCard.studiedAt = new Date();

      // Move to next card if available
      let nextIndex = prev.currentIndex;
      if (prev.reviewMode) {
        // In review mode, find next non-known card
        const reviewCards = updatedFlashcards.filter((fc) => !fc.known);
        if (reviewCards.length > 0) {
          const nextReviewCard = reviewCards[0];
          nextIndex = updatedFlashcards.findIndex((fc) => fc.id === nextReviewCard.id);
        }
      } else if (prev.currentIndex < prev.flashcards.length - 1) {
        nextIndex = prev.currentIndex + 1;
      }

      return {
        ...prev,
        flashcards: updatedFlashcards,
        currentIndex: nextIndex,
        isFlipped: false,
      };
    });
  }, []);

  // Mark current card for review
  const markForReview = useCallback(() => {
    setState((prev) => {
      if (!prev) return null;

      const updatedFlashcards = [...prev.flashcards];
      const currentCard = updatedFlashcards[prev.currentIndex];
      currentCard.studied = true;
      currentCard.known = false;
      currentCard.studiedAt = new Date();

      // Move to next card if available
      const nextIndex =
        prev.currentIndex < prev.flashcards.length - 1
          ? prev.currentIndex + 1
          : prev.currentIndex;

      return {
        ...prev,
        flashcards: updatedFlashcards,
        currentIndex: nextIndex,
        isFlipped: false,
      };
    });
  }, []);

  // Navigate to next card
  const nextCard = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.currentIndex >= prev.flashcards.length - 1) return prev;
      return { ...prev, currentIndex: prev.currentIndex + 1, isFlipped: false };
    });
  }, []);

  // Navigate to previous card
  const prevCard = useCallback(() => {
    setState((prev) => {
      if (!prev || prev.currentIndex <= 0) return prev;
      return { ...prev, currentIndex: prev.currentIndex - 1, isFlipped: false };
    });
  }, []);

  // Reset flashcards (clear all)
  const resetFlashcards = useCallback(() => {
    setState(null);
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      localStorage.removeItem(storageKey);
    } catch (e) {
      console.error('Failed to clear flashcards:', e);
    }
  }, [courseId, episodeId]);

  // Restart study (keep cards, reset progress)
  const restartStudy = useCallback(() => {
    setState((prev) => {
      if (!prev) return null;

      return {
        ...prev,
        flashcards: prev.flashcards.map((fc) => ({
          ...fc,
          studied: false,
          known: false,
          studiedAt: null,
        })),
        currentIndex: 0,
        isFlipped: false,
        reviewMode: false,
      };
    });
  }, []);

  // Start review mode (only cards not known)
  const startReviewMode = useCallback(() => {
    setState((prev) => {
      if (!prev) return null;

      const firstReviewIndex = prev.flashcards.findIndex((fc) => !fc.known);

      return {
        ...prev,
        currentIndex: firstReviewIndex >= 0 ? firstReviewIndex : 0,
        isFlipped: false,
        reviewMode: true,
      };
    });
  }, []);

  // Computed helpers
  const isCurrentKnown = currentCard?.known ?? false;
  const canGoNext = state ? state.currentIndex < state.flashcards.length - 1 : false;
  const canGoPrev = state ? state.currentIndex > 0 : false;
  const isLastCard = state ? state.currentIndex === state.flashcards.length - 1 : false;
  const hasCardsForReview = cardsForReview.length > 0;

  return {
    // State
    currentCard,
    currentIndex: state?.currentIndex ?? 0,
    isFlipped: state?.isFlipped ?? false,
    settings,
    progress,

    // Navigation
    nextCard,
    prevCard,
    flipCard,

    // Actions
    markAsKnown,
    markForReview,
    updateSettings,
    resetFlashcards,
    restartStudy,
    startReviewMode,

    // Generation
    generate: generateMutation.mutate,
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    // Helpers
    hasCards,
    isCurrentKnown,
    canGoNext,
    canGoPrev,
    isLastCard,
    hasCardsForReview,
    cardsForReview,
  };
}
