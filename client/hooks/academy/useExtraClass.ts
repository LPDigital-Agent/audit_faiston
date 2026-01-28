// =============================================================================
// useExtraClass Hook - Faiston Academy (HeyGen Video Generation)
// =============================================================================
// Hook for generating personalized video lessons when students have doubts.
// Uses HeyGen API for AI avatar videos with NEXO as the instructor.
//
// Features:
// - Video history (last 5 per episode)
// - Extended polling (45 minutes with progressive backoff)
// - Resume pending videos on page reload
// - Toast notifications for background completion
// - Smart retry logic
//
// Flow:
// 1. Student enters doubt in text area
// 2. validateDoubt() checks if doubt relates to transcription
// 3. If invalid: show message, allow retry
// 4. If valid: generateExtraClass() creates video with HeyGen
// 5. Poll for video completion with checkExtraClassStatus()
// 6. Display video when ready
// =============================================================================


import { useState, useEffect, useLayoutEffect, useCallback, useRef, startTransition } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useToast } from '@/components/ui/use-toast';
import {
  validateDoubt,
  generateExtraClass,
  checkExtraClassStatus,
} from '@/services/academyAgentcore';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

// =============================================================================
// Types
// =============================================================================

/**
 * State machine phases for Extra Class generation.
 */
export type ExtraClassPhase =
  | 'idle' // Initial state, waiting for input
  | 'validating' // Checking if doubt relates to content
  | 'invalid' // Doubt not related to content
  | 'generating' // Creating video script and HeyGen video
  | 'polling' // Waiting for HeyGen to complete
  | 'completed' // Video ready to play
  | 'failed'; // Error occurred

/**
 * Video history item status.
 */
export type VideoHistoryStatus =
  | 'pending' // Job created, waiting in queue
  | 'processing' // Video being generated
  | 'completed' // Video ready
  | 'failed' // Generation failed
  | 'timeout'; // Polling timed out

/**
 * Extra class timestamp for video navigation.
 */
export interface ExtraClassTimestamp {
  time: number;
  topic: string;
}

/**
 * Video history item - tracks each generated video.
 */
export interface VideoHistoryItem {
  id: string;
  videoId: string;
  status: VideoHistoryStatus;
  doubt: string;
  createdAt: string;
  completedAt?: string;
  videoUrl?: string;
  thumbnailUrl?: string;
  duration?: number;
  script?: string;
  timestamps?: ExtraClassTimestamp[];
  topics?: string[];
  error?: string;
}

/**
 * Data for a generated extra class video.
 */
export interface ExtraClassData {
  videoId: string;
  videoUrl?: string;
  thumbnailUrl?: string;
  doubt: string;
  script?: string;
  timestamps: ExtraClassTimestamp[];
  duration?: number;
  topics: string[];
  generatedAt: string;
}

/**
 * Progress information for UI display.
 */
export interface ExtraClassProgress {
  phase: ExtraClassPhase;
  message: string;
  percentage: number;
  elapsedSeconds?: number;
}

interface UseExtraClassOptions {
  courseId: string;
  episodeId: string;
  studentName?: string;
  onSeek?: (time: number) => void;
  onVideoReady?: () => void;
}

// =============================================================================
// Constants
// =============================================================================

const MAX_HISTORY_ITEMS = 5;
const MAX_POLL_DURATION_MS = 45 * 60 * 1000; // 45 minutes
const POLL_INTERVALS = [10, 15, 20, 30, 60]; // Progressive backoff in seconds
const MIN_DOUBT_LENGTH = 20;

const getHistoryStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.EXTRACLASS_HISTORY_PREFIX}${courseId}_${episodeId}`;

const getActiveStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.EXTRACLASS_ACTIVE_PREFIX}${courseId}_${episodeId}`;

// =============================================================================
// Utility Functions
// =============================================================================

const generateHistoryId = () =>
  `video-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const getPollInterval = (pollCount: number): number => {
  const index = Math.min(pollCount, POLL_INTERVALS.length - 1);
  return POLL_INTERVALS[index] * 1000;
};

type ExtraClassVideoStatus =
  | 'waiting'
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'error';

const mapHeyGenStatus = (status: ExtraClassVideoStatus): VideoHistoryStatus => {
  switch (status) {
    case 'waiting':
    case 'pending':
      return 'pending';
    case 'processing':
      return 'processing';
    case 'completed':
      return 'completed';
    case 'failed':
    case 'error':
      return 'failed';
    default:
      return 'pending';
  }
};

const sanitizeErrorForUser = (error: unknown): string => {
  const errorStr = error instanceof Error ? error.message : String(error);
  console.error('[ExtraClass] Technical error:', errorStr);

  const technicalPatterns = [
    /avatar.*not found/i,
    /avatar.*unavailable/i,
    /[a-f0-9]{32}/i,
    /api error/i,
    /http.*\d{3}/i,
    /\{.*code.*:.*\}/i,
    /endpoint/i,
    /timeout/i,
    /connection/i,
    /network/i,
  ];

  for (const pattern of technicalPatterns) {
    if (pattern.test(errorStr)) {
      return 'Erro ao gerar video. Por favor, tente novamente.';
    }
  }

  const isUserFriendly =
    errorStr.length < 100 &&
    !errorStr.includes('Error:') &&
    !errorStr.includes('Exception') &&
    /[áàâãéèêíìîóòôõúùûç]/i.test(errorStr);

  if (isUserFriendly) {
    return errorStr;
  }

  return 'Erro ao gerar video. Por favor, tente novamente.';
};

const formatElapsed = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

// =============================================================================
// Hook
// =============================================================================

export function useExtraClass({
  courseId,
  episodeId,
  studentName = 'Aluno',
  onSeek,
  onVideoReady,
}: UseExtraClassOptions) {
  const { toast } = useToast();

  // Phase state machine
  const [phase, setPhase] = useState<ExtraClassPhase>('idle');
  const [message, setMessage] = useState<string>('');

  // Data state
  const [extraClassData, setExtraClassData] = useState<ExtraClassData | null>(
    null
  );
  const [doubt, setDoubt] = useState<string>('');
  const [topics, setTopics] = useState<string[]>([]);

  // History state
  const [history, setHistory] = useState<VideoHistoryItem[]>([]);
  const [activeVideoId, setActiveVideoId] = useState<string | null>(null);

  // Elapsed seconds for progress display (React 19 purity: must use state, not Date.now() during render)
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Polling refs
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollStartTimeRef = useRef<number>(0);
  const pollCountRef = useRef<number>(0);
  const isPollingRef = useRef<boolean>(false);

  // Ref to store pollStatus for self-referencing (React 19 requirement)
  const pollStatusRef = useRef<(videoId: string) => void>(() => {});

  // =============================================================================
  // History Storage
  // =============================================================================

  // Load history from localStorage on mount
  useEffect(() => {
    try {
      const historyKey = getHistoryStorageKey(courseId, episodeId);
      const stored = localStorage.getItem(historyKey);

      if (stored) {
        const parsed = JSON.parse(stored) as VideoHistoryItem[];
        startTransition(() => {
          setHistory(parsed);
        });

        // Check for pending videos to resume polling
        const pendingVideo = parsed.find(
          (v) => v.status === 'pending' || v.status === 'processing'
        );
        if (pendingVideo) {
          console.log(
            `[ExtraClass] Found pending video: ${pendingVideo.videoId}`
          );
        }
      }

      // Load active video
      const activeKey = getActiveStorageKey(courseId, episodeId);
      const activeId = localStorage.getItem(activeKey);
      if (activeId) {
        startTransition(() => {
          setActiveVideoId(activeId);
        });
      }
    } catch (e) {
      console.error('Failed to load extra class history:', e);
    }
  }, [courseId, episodeId]);

  // Save history to localStorage when it changes
  useEffect(() => {
    if (history.length > 0) {
      try {
        const historyKey = getHistoryStorageKey(courseId, episodeId);
        localStorage.setItem(historyKey, JSON.stringify(history));
      } catch (e) {
        console.warn('Failed to save extra class history:', e);
      }
    }
  }, [history, courseId, episodeId]);

  // Save active video ID
  useEffect(() => {
    try {
      const activeKey = getActiveStorageKey(courseId, episodeId);
      if (activeVideoId) {
        localStorage.setItem(activeKey, activeVideoId);
      } else {
        localStorage.removeItem(activeKey);
      }
    } catch (e) {
      console.warn('Failed to save active video ID:', e);
    }
  }, [activeVideoId, courseId, episodeId]);

  // Update elapsed seconds during polling (React 19 purity: interval effect, not render-time computation)
  useEffect(() => {
    if (phase !== 'polling' || !isPollingRef.current) {
      startTransition(() => {
        setElapsedSeconds(0);
      });
      return;
    }

    // Update immediately
    startTransition(() => {
      setElapsedSeconds(
        Math.floor((Date.now() - pollStartTimeRef.current) / 1000)
      );
    });

    // Then update every second
    const interval = setInterval(() => {
      startTransition(() => {
        setElapsedSeconds(
          Math.floor((Date.now() - pollStartTimeRef.current) / 1000)
        );
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [phase]);

  // =============================================================================
  // History Management
  // =============================================================================

  const addToHistory = useCallback((item: VideoHistoryItem) => {
    setHistory((prev) => {
      const existing = prev.find((v) => v.videoId === item.videoId);
      if (existing) return prev;
      return [item, ...prev].slice(0, MAX_HISTORY_ITEMS);
    });
  }, []);

  const updateHistoryItem = useCallback(
    (videoId: string, updates: Partial<VideoHistoryItem>) => {
      setHistory((prev) =>
        prev.map((item) =>
          item.videoId === videoId ? { ...item, ...updates } : item
        )
      );
    },
    []
  );

  const removeFromHistory = useCallback((videoId: string) => {
    setHistory((prev) => prev.filter((item) => item.videoId !== videoId));
  }, []);

  const getPendingVideo = useCallback((): VideoHistoryItem | undefined => {
    return history.find(
      (v) => v.status === 'pending' || v.status === 'processing'
    );
  }, [history]);

  // =============================================================================
  // Polling
  // =============================================================================

  const stopPolling = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    isPollingRef.current = false;
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const pollStatus = useCallback(
    async (videoId: string) => {
      if (!isPollingRef.current) return;

      try {
        const { data } = await checkExtraClassStatus({ video_id: videoId });
        console.log(
          `[ExtraClass] Poll #${pollCountRef.current + 1}: ${data.status}`
        );

        updateHistoryItem(videoId, {
          status: mapHeyGenStatus(data.status as ExtraClassVideoStatus),
        });

        if (data.status === 'completed' && data.video_url) {
          stopPolling();
          setPhase('completed');
          setMessage('Video pronto!');

          updateHistoryItem(videoId, {
            status: 'completed',
            videoUrl: data.video_url,
            thumbnailUrl: data.thumbnail_url,
            duration: data.duration,
            completedAt: new Date().toISOString(),
          });

          setExtraClassData((prev) =>
            prev
              ? {
                  ...prev,
                  videoUrl: data.video_url,
                  thumbnailUrl: data.thumbnail_url,
                  duration: data.duration,
                }
              : null
          );

          toast({
            title: '🎬 Aula Extra Pronta!',
            description: 'Seu video personalizado esta disponivel.',
          });

          onVideoReady?.();
          return;
        }

        if (data.status === 'failed' || data.status === 'error') {
          stopPolling();
          setPhase('failed');
          const errorMsg = sanitizeErrorForUser(
            data.error || 'Falha ao gerar o video'
          );
          setMessage(errorMsg);

          updateHistoryItem(videoId, {
            status: 'failed',
            error: errorMsg,
          });

          toast({
            title: '❌ Erro na Geracao',
            description: errorMsg,
            variant: 'destructive',
          });
          return;
        }

        // Check for timeout
        const elapsed = Date.now() - pollStartTimeRef.current;
        if (elapsed > MAX_POLL_DURATION_MS) {
          stopPolling();
          setPhase('failed');
          setMessage(
            'Tempo limite excedido (45 min). O video pode ainda estar sendo processado.'
          );

          updateHistoryItem(videoId, {
            status: 'timeout',
            error: 'Tempo limite excedido',
          });

          toast({
            title: '⏱️ Tempo Limite Excedido',
            description:
              'O video pode ainda estar sendo processado. Verifique mais tarde.',
          });
          return;
        }

        // Update progress message
        const statusMessages: Record<string, string> = {
          waiting: 'Aguardando na fila do HeyGen...',
          pending: 'Iniciando geracao...',
          processing: 'O NEXO esta gravando seu video...',
          completed: 'Video pronto!',
          failed: 'Falha na geracao',
          error: 'Erro ao gerar video',
        };
        setMessage(statusMessages[data.status] || 'Processando...');

        // Schedule next poll with progressive backoff
        pollCountRef.current += 1;
        const nextInterval = getPollInterval(pollCountRef.current);
        console.log(`[ExtraClass] Next poll in ${nextInterval / 1000}s`);

        pollTimeoutRef.current = setTimeout(() => {
          pollStatusRef.current(videoId);
        }, nextInterval);
      } catch (error) {
        console.error('[ExtraClass] Poll error:', error);
        pollCountRef.current += 1;
        const nextInterval = getPollInterval(pollCountRef.current);
        pollTimeoutRef.current = setTimeout(() => {
          pollStatusRef.current(videoId);
        }, nextInterval);
      }
    },
    [stopPolling, updateHistoryItem, onVideoReady, toast]
  );

  // Sync pollStatus to ref for self-referencing (React 19 requirement)
  useLayoutEffect(() => {
    pollStatusRef.current = pollStatus;
  }, [pollStatus]);

  const startPolling = useCallback(
    (videoId: string, resuming: boolean = false) => {
      stopPolling();
      pollStartTimeRef.current = Date.now();
      pollCountRef.current = 0;
      isPollingRef.current = true;

      setPhase('polling');
      setMessage(
        resuming
          ? 'Retomando verificacao do video...'
          : 'Video sendo gerado pelo NEXO...'
      );

      pollStatus(videoId);
    },
    [pollStatus, stopPolling]
  );

  // Resume polling for pending video on mount
  useEffect(() => {
    const pendingVideo = getPendingVideo();
    if (pendingVideo && !isPollingRef.current) {
      console.log(`[ExtraClass] Resuming polling for: ${pendingVideo.videoId}`);
      startTransition(() => {
        setActiveVideoId(pendingVideo.videoId);
        setDoubt(pendingVideo.doubt);
        setExtraClassData({
          videoId: pendingVideo.videoId,
          doubt: pendingVideo.doubt,
          script: pendingVideo.script,
          timestamps: pendingVideo.timestamps || [],
          topics: pendingVideo.topics || [],
          generatedAt: pendingVideo.createdAt,
        });
      });

      toast({
        title: '🔄 Retomando verificacao',
        description: 'Verificando status do video anterior...',
      });

      startTransition(() => {
        startPolling(pendingVideo.videoId, true);
      });
    }
  }, [getPendingVideo, startPolling, toast]);

  // =============================================================================
  // Mutations
  // =============================================================================

  const validateMutation = useMutation({
    mutationFn: async (params: { transcription: string; doubt: string }) => {
      const { data } = await validateDoubt(params);
      return data;
    },
  });

  const generateMutation = useMutation({
    mutationFn: async (params: {
      transcription: string;
      doubt: string;
      episode_id: string;
      student_name: string;
    }) => {
      const { data } = await generateExtraClass(params);
      return data;
    },
  });

  // =============================================================================
  // Actions
  // =============================================================================

  const checkDoubt = useCallback(
    async (transcription: string, inputDoubt: string): Promise<boolean> => {
      if (!inputDoubt || inputDoubt.trim().length < MIN_DOUBT_LENGTH) {
        setPhase('invalid');
        setMessage(
          `Por favor, descreva sua duvida com mais detalhes (minimo ${MIN_DOUBT_LENGTH} caracteres).`
        );
        return false;
      }

      setPhase('validating');
      setMessage('Analisando sua duvida...');
      setDoubt(inputDoubt);

      try {
        const result = await validateMutation.mutateAsync({
          transcription,
          doubt: inputDoubt,
        });

        if (!result.is_valid) {
          setPhase('invalid');
          setMessage(
            result.message ||
              'Sua duvida nao parece estar relacionada ao conteudo desta aula.'
          );
          setTopics([]);
          return false;
        }

        setTopics(result.topics || []);
        return true;
      } catch (error) {
        setPhase('failed');
        setMessage(sanitizeErrorForUser(error));
        return false;
      }
    },
    [validateMutation]
  );

  const generateVideo = useCallback(
    async (transcription: string, inputDoubt: string) => {
      const pendingVideo = getPendingVideo();
      if (pendingVideo) {
        setActiveVideoId(pendingVideo.videoId);
        setDoubt(pendingVideo.doubt);
        startPolling(pendingVideo.videoId, true);
        return;
      }

      setPhase('generating');
      setMessage('Criando sua aula personalizada...');
      setDoubt(inputDoubt);

      try {
        const result = await generateMutation.mutateAsync({
          transcription,
          doubt: inputDoubt,
          episode_id: `${courseId}-${episodeId}`,
          student_name: studentName,
        });

        if (!result.is_valid) {
          setPhase('invalid');
          setMessage(
            result.message || 'Sua duvida nao esta relacionada ao conteudo.'
          );
          return;
        }

        if (result.phase === 'video_error' || result.error) {
          setPhase('failed');
          setMessage(sanitizeErrorForUser(result.error || 'Erro ao criar o video'));
          return;
        }

        if (result.video_id) {
          const historyItem: VideoHistoryItem = {
            id: generateHistoryId(),
            videoId: result.video_id,
            status: 'pending',
            doubt: inputDoubt,
            createdAt: new Date().toISOString(),
            script: result.script,
            timestamps: result.timestamps,
            topics: result.topics,
          };

          addToHistory(historyItem);
          setActiveVideoId(result.video_id);

          setExtraClassData({
            videoId: result.video_id,
            doubt: inputDoubt,
            script: result.script,
            timestamps: result.timestamps || [],
            topics: result.topics || [],
            generatedAt: new Date().toISOString(),
          });

          startPolling(result.video_id);
        } else {
          setPhase('failed');
          setMessage('Resposta inesperada do servidor. Tente novamente.');
        }
      } catch (error) {
        setPhase('failed');
        setMessage(sanitizeErrorForUser(error));
      }
    },
    [
      generateMutation,
      courseId,
      episodeId,
      studentName,
      startPolling,
      addToHistory,
      getPendingVideo,
    ]
  );

  const selectFromHistory = useCallback(
    (historyItem: VideoHistoryItem) => {
      setActiveVideoId(historyItem.videoId);
      setDoubt(historyItem.doubt);
      setTopics(historyItem.topics || []);

      setExtraClassData({
        videoId: historyItem.videoId,
        videoUrl: historyItem.videoUrl,
        thumbnailUrl: historyItem.thumbnailUrl,
        doubt: historyItem.doubt,
        script: historyItem.script,
        timestamps: historyItem.timestamps || [],
        duration: historyItem.duration,
        topics: historyItem.topics || [],
        generatedAt: historyItem.createdAt,
      });

      if (historyItem.status === 'completed' && historyItem.videoUrl) {
        setPhase('completed');
        setMessage('Video pronto!');
      } else if (historyItem.status === 'completed' && !historyItem.videoUrl) {
        setPhase('polling');
        setMessage('Carregando video...');
        startPolling(historyItem.videoId, true);
      } else if (
        historyItem.status === 'pending' ||
        historyItem.status === 'processing'
      ) {
        startPolling(historyItem.videoId, true);
      } else if (historyItem.status === 'timeout') {
        startPolling(historyItem.videoId, true);
      } else if (historyItem.status === 'failed') {
        setPhase('failed');
        setMessage(historyItem.error || 'Este video falhou na geracao.');
      } else {
        setPhase('idle');
        setMessage('');
      }
    },
    [startPolling]
  );

  const deleteFromHistory = useCallback(
    (videoId: string) => {
      removeFromHistory(videoId);

      if (activeVideoId === videoId) {
        stopPolling();
        setActiveVideoId(null);
        setExtraClassData(null);
        setPhase('idle');
        setMessage('');
        setDoubt('');
      }
    },
    [removeFromHistory, activeVideoId, stopPolling]
  );

  const seekToTimestamp = useCallback(
    (time: number) => {
      onSeek?.(time);
    },
    [onSeek]
  );

  const reset = useCallback(() => {
    stopPolling();
    setPhase('idle');
    setMessage('');
    setDoubt('');
    setTopics([]);
    setActiveVideoId(null);
  }, [stopPolling]);

  const clearAll = useCallback(() => {
    stopPolling();
    setPhase('idle');
    setMessage('');
    setDoubt('');
    setTopics([]);
    setExtraClassData(null);
    setActiveVideoId(null);
    setHistory([]);

    try {
      const historyKey = getHistoryStorageKey(courseId, episodeId);
      const activeKey = getActiveStorageKey(courseId, episodeId);
      localStorage.removeItem(historyKey);
      localStorage.removeItem(activeKey);
    } catch (e) {
      console.warn('Failed to clear extra class storage:', e);
    }
  }, [stopPolling, courseId, episodeId]);

  const showPreviousVideo = useCallback(() => {
    if (extraClassData?.videoUrl) {
      setPhase('completed');
      setMessage('Video pronto!');
    }
  }, [extraClassData?.videoUrl]);

  // =============================================================================
  // Progress
  // =============================================================================

  // Note: elapsedSeconds is now state, updated by the interval effect above
  // (React 19 purity: no Date.now() calls during render)

  const progress: ExtraClassProgress = {
    phase,
    message,
    elapsedSeconds,
    percentage:
      phase === 'idle'
        ? 0
        : phase === 'validating'
        ? 10
        : phase === 'invalid'
        ? 0
        : phase === 'generating'
        ? 30
        : phase === 'polling'
        ? 60 +
          Math.min(
            30,
            ((elapsedSeconds * 1000) / MAX_POLL_DURATION_MS) * 30
          )
        : phase === 'completed'
        ? 100
        : 0,
  };

  // =============================================================================
  // Return
  // =============================================================================

  return {
    // User info
    studentName,

    // State
    phase,
    message,
    doubt,
    topics,
    extraClassData,
    progress,

    // History
    history,
    activeVideoId,
    hasPendingVideo: !!getPendingVideo(),

    // Actions
    checkDoubt,
    generateVideo,
    seekToTimestamp,
    reset,
    clearAll,
    setDoubt,
    showPreviousVideo,
    selectFromHistory,
    deleteFromHistory,

    // Mutation states
    isValidating: validateMutation.isPending,
    isGenerating: generateMutation.isPending,
    isPolling: phase === 'polling',
    isLoading:
      phase === 'validating' || phase === 'generating' || phase === 'polling',

    // Helpers
    hasVideo: !!extraClassData?.videoUrl,
    canGenerate: phase === 'idle' || phase === 'invalid' || phase === 'failed',
    minDoubtLength: MIN_DOUBT_LENGTH,
    elapsedTime: formatElapsed(elapsedSeconds),
    maxPollMinutes: MAX_POLL_DURATION_MS / 60000,
  };
}
