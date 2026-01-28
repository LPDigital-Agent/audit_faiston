// =============================================================================
// useSlideDeck Hook - Faiston Academy
// =============================================================================
// Hook for slide deck generation with batch-based parallel architecture.
// Supports deck archetypes, history, and progressive slide navigation.
//
// v4 Architecture (solves 120s timeout):
// 1. Plan: Extract concepts and create batch assignments (~10-15s)
// 2. Generate: Parallel batch generation (each batch 2-3 slides, ~60-90s)
// 3. Aggregate: Combine all batches into final deck
// =============================================================================


import { useState, useEffect, useCallback, useRef, startTransition } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  generateSlideDeckV4,
  type GenerationProgress,
} from '@/services/academyAgentcore';
import type {
  Slide,
  SlideDeckResponse,
  DeckArchetype,
} from '@/lib/academy/types';
import { ACADEMY_STORAGE_KEYS, DECK_ARCHETYPES } from '@/lib/academy/constants';

interface UseSlideDeckOptions {
  courseId: string;
  episodeId: string;
  episodeTitle?: string;
}

interface SlideDeckData {
  deck_title: string;
  slides: Slide[];
  generatedAt: string;
  model?: string;
}

interface SlideDeckSettings {
  archetype: DeckArchetype;
}

interface SlideDeckHistoryItem {
  id: string;
  data: SlideDeckData;
  createdAt: string;
  thumbnailUrl?: string;
}

// Constants
const MAX_HISTORY_ITEMS = 3;

// Storage key generators
const getStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.SLIDEDECK_PREFIX}${courseId}_${episodeId}`;

const getSettingsStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.SLIDEDECK_SETTINGS_PREFIX}${courseId}_${episodeId}`;

const getHistoryStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.SLIDEDECK_HISTORY_PREFIX}${courseId}_${episodeId}`;

export function useSlideDeck({
  courseId,
  episodeId,
  episodeTitle = 'Aula',
}: UseSlideDeckOptions) {
  // Slide deck data state
  const [deckData, setDeckData] = useState<SlideDeckData | null>(null);

  // Navigation state
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

  // Settings state - default to 'deep_dive' archetype
  const [settings, setSettings] = useState<SlideDeckSettings>({
    archetype: 'deep_dive',
  });

  // History state (last 3 presentations)
  const [history, setHistory] = useState<SlideDeckHistoryItem[]>([]);

  // Progress state for batch-based generation
  const [progress, setProgress] = useState<GenerationProgress | null>(null);

  // Ref to track progress updates (for use in mutation)
  const progressRef = useRef<(p: GenerationProgress) => void>((p) =>
    setProgress(p)
  );

  // Load from localStorage on mount
  useEffect(() => {
    try {
      // Load deck data
      const storageKey = getStorageKey(courseId, episodeId);
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.slides) {
          startTransition(() => {
            setDeckData(parsed as SlideDeckData);
          });
        }
      }

      // Load settings
      const settingsKey = getSettingsStorageKey(courseId, episodeId);
      const storedSettings = localStorage.getItem(settingsKey);
      if (storedSettings) {
        const parsedSettings = JSON.parse(storedSettings);
        if (parsedSettings) {
          startTransition(() => {
            setSettings(parsedSettings as SlideDeckSettings);
          });
        }
      }

      // Load history
      const historyKey = getHistoryStorageKey(courseId, episodeId);
      const storedHistory = localStorage.getItem(historyKey);
      if (storedHistory) {
        const parsedHistory = JSON.parse(storedHistory);
        if (Array.isArray(parsedHistory)) {
          startTransition(() => {
            setHistory(parsedHistory as SlideDeckHistoryItem[]);
          });
        }
      }
    } catch (e) {
      console.error('Failed to load slide deck from storage:', e);
    }
  }, [courseId, episodeId]);

  // Save deck data to localStorage when it changes
  useEffect(() => {
    if (deckData) {
      try {
        const storageKey = getStorageKey(courseId, episodeId);
        localStorage.setItem(storageKey, JSON.stringify(deckData));
      } catch (e) {
        console.warn('Failed to save slide deck to storage:', e);
      }
    }
  }, [deckData, courseId, episodeId]);

  // Save settings to localStorage when they change
  useEffect(() => {
    try {
      const settingsKey = getSettingsStorageKey(courseId, episodeId);
      localStorage.setItem(settingsKey, JSON.stringify(settings));
    } catch (e) {
      console.warn('Failed to save slide deck settings:', e);
    }
  }, [settings, courseId, episodeId]);

  // Save history to localStorage when it changes
  useEffect(() => {
    try {
      const historyKey = getHistoryStorageKey(courseId, episodeId);
      localStorage.setItem(historyKey, JSON.stringify(history));
    } catch (e) {
      console.warn('Failed to save slide deck history:', e);
    }
  }, [history, courseId, episodeId]);

  // Add deck to history (FIFO: max 3 items)
  const addToHistory = useCallback((newDeck: SlideDeckData) => {
    const historyItem: SlideDeckHistoryItem = {
      id: `deck-${Date.now()}`,
      data: newDeck,
      createdAt: newDeck.generatedAt || new Date().toISOString(),
      thumbnailUrl: newDeck.slides[0]?.image_url,
    };

    setHistory((prev) => {
      const updated = [historyItem, ...prev];
      return updated.slice(0, MAX_HISTORY_ITEMS);
    });
  }, []);

  // Load deck from history
  const loadFromHistory = useCallback(
    (historyId: string) => {
      const item = history.find((h) => h.id === historyId);
      if (item) {
        setDeckData(item.data);
        setCurrentSlideIndex(0);
        try {
          const storageKey = getStorageKey(courseId, episodeId);
          localStorage.setItem(storageKey, JSON.stringify(item.data));
        } catch (e) {
          console.warn('Failed to save loaded deck to storage:', e);
        }
      }
    },
    [history, courseId, episodeId]
  );

  // Generate mutation with batch-based parallel generation
  const generateMutation = useMutation({
    mutationFn: async (transcription: string): Promise<SlideDeckResponse> => {
      setProgress({
        phase: 'planning',
        current: 0,
        total: 1,
        message: 'Analisando conteudo...',
      });

      const result = await generateSlideDeckV4(
        {
          transcription,
          episode_title: episodeTitle,
          episode_id: `${courseId}-${episodeId}`,
          archetype: settings.archetype,
        },
        (p) => progressRef.current(p)
      );

      return result;
    },
    onSuccess: (data) => {
      const newDeck: SlideDeckData = {
        deck_title: data.deck_title,
        slides: data.slides,
        generatedAt: data.generatedAt,
        model: data.model,
      };
      setDeckData(newDeck);
      setCurrentSlideIndex(0);
      addToHistory(newDeck);
      setProgress(null);
    },
    onError: () => {
      setProgress(null);
    },
  });

  // Navigation functions
  const nextSlide = useCallback(() => {
    if (deckData && currentSlideIndex < deckData.slides.length - 1) {
      setCurrentSlideIndex((prev) => prev + 1);
    }
  }, [deckData, currentSlideIndex]);

  const prevSlide = useCallback(() => {
    if (currentSlideIndex > 0) {
      setCurrentSlideIndex((prev) => prev - 1);
    }
  }, [currentSlideIndex]);

  const goToSlide = useCallback(
    (index: number) => {
      if (deckData && index >= 0 && index < deckData.slides.length) {
        setCurrentSlideIndex(index);
      }
    },
    [deckData]
  );

  // Update settings
  const updateSettings = useCallback(
    (newSettings: Partial<SlideDeckSettings>) => {
      setSettings((prev) => ({ ...prev, ...newSettings }));
    },
    []
  );

  // Reset slide deck
  const resetDeck = useCallback(() => {
    setDeckData(null);
    setCurrentSlideIndex(0);
    try {
      const storageKey = getStorageKey(courseId, episodeId);
      localStorage.removeItem(storageKey);
    } catch (e) {
      console.warn('Failed to remove slide deck from storage:', e);
    }
  }, [courseId, episodeId]);

  // Current slide helper
  const currentSlide: Slide | null = deckData?.slides[currentSlideIndex] ?? null;
  const totalSlides = deckData?.slides.length ?? 0;

  return {
    // Data
    deckData,
    currentSlide,
    currentSlideIndex,
    totalSlides,

    // Navigation
    nextSlide,
    prevSlide,
    goToSlide,

    // Settings
    settings,
    updateSettings,
    archetypes: DECK_ARCHETYPES,

    // History
    history,
    loadFromHistory,
    hasHistory: history.length > 0,

    // Actions
    generate: generateMutation.mutate,
    resetDeck,

    // Mutation state
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    // Progress state for batch-based generation
    progress,

    // Helpers
    hasDeck: deckData !== null && deckData.slides.length > 0,
    isFirstSlide: currentSlideIndex === 0,
    isLastSlide: deckData
      ? currentSlideIndex === deckData.slides.length - 1
      : true,
  };
}

// Re-export types and constants for convenience
export type { SlideDeckData, SlideDeckSettings, SlideDeckHistoryItem };
export type { GenerationProgress } from '@/services/academyAgentcore';
export { DECK_ARCHETYPES } from '@/lib/academy/constants';
