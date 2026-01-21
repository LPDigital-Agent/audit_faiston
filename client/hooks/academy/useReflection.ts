// =============================================================================
// useReflection Hook - Faiston Academy
// =============================================================================
// Hook for student reflection analysis and learning assessment.
// Provides feedback on student understanding with video timestamps.
// =============================================================================

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { analyzeReflection } from '@/services/academyAgentcore';
import type { ReflectionResponse, ProximoPasso } from '@/lib/academy/types';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

interface UseReflectionOptions {
  courseId: string;
  episodeId: string;
  onSeek?: (time: number) => void;
}

interface StoredReflection {
  attempts: number;
  bestScore: number;
  lastExplanation: string;
  lastAnalysis: ReflectionResponse | null;
  completedAt: string | null;
  xpEarned: number;
}

// Constants
const MAX_ATTEMPTS = 3;
const MIN_CHARS = 60;
const MAX_CHARS = 1000;

const getStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.REFLECTION_PREFIX}${courseId}_${episodeId}`;

const getTotalReflectionsKey = () => 'faiston_academy_reflection_count';
const getQualityReflectionsKey = () => 'faiston_academy_reflection_quality_count';

export function useReflection({ courseId, episodeId, onSeek }: UseReflectionOptions) {
  // State
  const [explanation, setExplanation] = useState('');
  const [analysis, setAnalysis] = useState<ReflectionResponse | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [bestScore, setBestScore] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);

  // Load stored reflection on mount
  useEffect(() => {
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed: StoredReflection = JSON.parse(stored);
        setAttempts(parsed.attempts || 0);
        setBestScore(parsed.bestScore || 0);
        if (parsed.lastExplanation) {
          setExplanation(parsed.lastExplanation);
        }
        if (parsed.lastAnalysis) {
          setAnalysis(parsed.lastAnalysis);
        }
        if (parsed.completedAt) {
          setIsCompleted(true);
        }
      }
    } catch (e) {
      console.error('Failed to parse stored reflection:', e);
    }
  }, [courseId, episodeId]);

  // Save reflection to localStorage
  const saveToStorage = useCallback(
    (
      newAnalysis: ReflectionResponse | null,
      newAttempts: number,
      newExplanation: string,
      completed: boolean
    ) => {
      const storageKey = getStorageKey(courseId, episodeId);
      const currentBest = Math.max(bestScore, newAnalysis?.overall_score || 0);

      const data: StoredReflection = {
        attempts: newAttempts,
        bestScore: currentBest,
        lastExplanation: newExplanation,
        lastAnalysis: newAnalysis,
        completedAt: completed ? new Date().toISOString() : null,
        xpEarned: newAnalysis?.xp_earned || 0,
      };

      try {
        localStorage.setItem(storageKey, JSON.stringify(data));

        // Update global counters for achievements
        if (completed && newAttempts === 1) {
          // First completion - increment total count
          const totalKey = getTotalReflectionsKey();
          const currentTotal = parseInt(localStorage.getItem(totalKey) || '0', 10);
          localStorage.setItem(totalKey, String(currentTotal + 1));

          // If score >= 70%, increment quality count
          if ((newAnalysis?.overall_score || 0) >= 70) {
            const qualityKey = getQualityReflectionsKey();
            const currentQuality = parseInt(
              localStorage.getItem(qualityKey) || '0',
              10
            );
            localStorage.setItem(qualityKey, String(currentQuality + 1));
          }
        }
      } catch (e) {
        console.error('Failed to save reflection:', e);
      }
    },
    [courseId, episodeId, bestScore]
  );

  // Analyze reflection mutation
  const analyzeMutation = useMutation({
    mutationFn: async (transcription: string): Promise<ReflectionResponse> => {
      const { data } = await analyzeReflection({
        reflection: explanation,
        transcription,
      });
      return data;
    },
    onSuccess: (data) => {
      const newAttempts = attempts + 1;
      setAnalysis(data);
      setAttempts(newAttempts);
      setBestScore((prev) => Math.max(prev, data.overall_score));
      saveToStorage(data, newAttempts, explanation, true);
      setIsCompleted(true);
    },
  });

  // Submit reflection for analysis
  const submit = useCallback(
    (transcription: string) => {
      if (explanation.trim().length < MIN_CHARS) return;
      if (attempts >= MAX_ATTEMPTS) return;

      analyzeMutation.mutate(transcription);
    },
    [explanation, attempts, analyzeMutation]
  );

  // Navigate to timestamp
  const navigateToTimestamp = useCallback(
    (passo: ProximoPasso) => {
      if (passo.timestamp !== null && onSeek) {
        onSeek(passo.timestamp);
      }
    },
    [onSeek]
  );

  // Reset for new attempt (but keep history)
  const retry = useCallback(() => {
    setAnalysis(null);
    setExplanation('');
  }, []);

  // Full reset (clear everything)
  const reset = useCallback(() => {
    setExplanation('');
    setAnalysis(null);
    setAttempts(0);
    setBestScore(0);
    setIsCompleted(false);
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      localStorage.removeItem(storageKey);
    } catch (e) {
      console.error('Failed to reset reflection:', e);
    }
  }, [courseId, episodeId]);

  // Character count and validation
  const charCount = explanation.length;
  const wordCount = explanation.trim() ? explanation.trim().split(/\s+/).length : 0;
  const isValidLength = charCount >= MIN_CHARS && charCount <= MAX_CHARS;
  const canSubmit =
    isValidLength && attempts < MAX_ATTEMPTS && !analyzeMutation.isPending;
  const canRetry = attempts < MAX_ATTEMPTS && analysis !== null;
  const remainingAttempts = MAX_ATTEMPTS - attempts;

  // Score color helper
  const getScoreColor = (score: number) => {
    if (score >= 70) return 'green';
    if (score >= 50) return 'yellow';
    return 'orange';
  };

  return {
    // State
    explanation,
    setExplanation,
    analysis,
    attempts,
    bestScore,
    isCompleted,

    // Validation
    charCount,
    wordCount,
    isValidLength,
    minChars: MIN_CHARS,
    maxChars: MAX_CHARS,

    // Actions
    submit,
    retry,
    reset,
    navigateToTimestamp,

    // Mutation state
    isAnalyzing: analyzeMutation.isPending,
    analyzeError: analyzeMutation.error,

    // Helpers
    canSubmit,
    canRetry,
    remainingAttempts,
    maxAttempts: MAX_ATTEMPTS,
    hasAnalysis: analysis !== null,
    getScoreColor,
  };
}

// Re-export types for convenience
export type { ProximoPasso } from '@/lib/academy/types';
