// =============================================================================
// useAudioClass Hook - Faiston Academy
// =============================================================================
// Hook for audio class generation using ElevenLabs TTS.
// Supports podcast-style lessons with two hosts (debate mode),
// deep explanations, or quick summaries.
// =============================================================================


import { useState, useEffect, useCallback, useRef, startTransition } from 'react';
import { useMutation } from '@tanstack/react-query';
import { generateAudioClass } from '@/services/academyAgentcore';
import type { AudioClassResponse, AudioMode } from '@/lib/academy/types';
import {
  ACADEMY_STORAGE_KEYS,
  VOICE_OPTIONS,
  DEFAULT_MALE_VOICE,
  DEFAULT_FEMALE_VOICE,
  AUDIO_MODE_LABELS,
  PLAYBACK_RATES,
} from '@/lib/academy/constants';

interface UseAudioClassOptions {
  courseId: string;
  episodeId: string;
  studentName?: string;
}

interface AudioClassSettings {
  mode: AudioMode;
  customPrompt: string;
  maleVoiceId: string;
  femaleVoiceId: string;
}

interface AudioClassData {
  audioBase64: string;
  audioUrl?: string;
  durationSeconds: number;
  mode: AudioMode | string;
  studentName: string;
  generatedAt: string;
}

export type PlaybackRate = (typeof PLAYBACK_RATES)[number];

const getSettingsStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.AUDIOCLASS_SETTINGS_PREFIX}${courseId}_${episodeId}`;

const getAudioStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.AUDIOCLASS_PREFIX}${courseId}_${episodeId}`;

export function useAudioClass({
  courseId,
  episodeId,
  studentName = 'Estudante',
}: UseAudioClassOptions) {
  // Audio data state
  const [audioData, setAudioData] = useState<AudioClassData | null>(null);

  // Settings state (includes voice selection with defaults)
  const [settings, setSettings] = useState<AudioClassSettings>({
    mode: 'deep_explanation',
    customPrompt: '',
    maleVoiceId: DEFAULT_MALE_VOICE,
    femaleVoiceId: DEFAULT_FEMALE_VOICE,
  });

  // Audio player state
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRateState] = useState<PlaybackRate>(1);

  // Abort controller for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load saved settings from localStorage on mount
  useEffect(() => {
    try {
      const storageKey = getSettingsStorageKey(courseId, episodeId);
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<AudioClassSettings>;
        if (parsed.mode) {
          // Capture mode to narrow the type (TypeScript doesn't narrow Partial<T> in callbacks)
          const mode = parsed.mode;
          startTransition(() => {
            setSettings({
              mode,
              customPrompt: parsed.customPrompt || '',
              maleVoiceId: parsed.maleVoiceId || DEFAULT_MALE_VOICE,
              femaleVoiceId: parsed.femaleVoiceId || DEFAULT_FEMALE_VOICE,
            });
          });
        }
      }

      // Try to load cached audio data
      const audioKey = getAudioStorageKey(courseId, episodeId);
      const storedAudio = localStorage.getItem(audioKey);
      if (storedAudio) {
        const parsedAudio = JSON.parse(storedAudio) as AudioClassData;
        // Only restore if we have audio content
        if (parsedAudio.audioBase64 || parsedAudio.audioUrl) {
          startTransition(() => {
            setAudioData(parsedAudio);
          });
        }
      }
    } catch (e) {
      console.error('Failed to load audio class settings:', e);
    }
  }, [courseId, episodeId]);

  // Save settings to localStorage when they change
  useEffect(() => {
    try {
      const storageKey = getSettingsStorageKey(courseId, episodeId);
      localStorage.setItem(storageKey, JSON.stringify(settings));
    } catch (e) {
      console.warn('Failed to save audio class settings:', e);
    }
  }, [settings, courseId, episodeId]);

  // Create audio element when we have audio data
  useEffect(() => {
    const audioSource = audioData?.audioBase64
      ? `data:audio/mp3;base64,${audioData.audioBase64}`
      : audioData?.audioUrl || null;

    if (audioSource) {
      const audio = new Audio(audioSource);

      audio.addEventListener('loadedmetadata', () => {
        if (isFinite(audio.duration) && audio.duration > 0) {
          setDuration(audio.duration);
        }
      });

      audio.addEventListener('durationchange', () => {
        if (isFinite(audio.duration) && audio.duration > 0) {
          setDuration(audio.duration);
        }
      });

      audio.addEventListener('timeupdate', () => {
        setCurrentTime(audio.currentTime);
      });

      audio.addEventListener('ended', () => {
        setIsPlaying(false);
        setCurrentTime(0);
      });

      audio.addEventListener('play', () => setIsPlaying(true));
      audio.addEventListener('pause', () => setIsPlaying(false));

      audioRef.current = audio;

      return () => {
        audio.pause();
        audio.src = '';
        audioRef.current = null;
      };
    }
  }, [audioData?.audioBase64, audioData?.audioUrl]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: async (transcription: string): Promise<AudioClassResponse> => {
      abortControllerRef.current = new AbortController();

      const { data } = await generateAudioClass(
        {
          transcription,
          mode: settings.mode,
          student_name: studentName,
          custom_prompt: settings.customPrompt || undefined,
          male_voice_id: settings.maleVoiceId,
          female_voice_id: settings.femaleVoiceId,
          male_voice_name:
            VOICE_OPTIONS.male.find((v) => v.id === settings.maleVoiceId)?.name ||
            'Eric',
          female_voice_name:
            VOICE_OPTIONS.female.find((v) => v.id === settings.femaleVoiceId)
              ?.name || 'Sarah',
        },
        abortControllerRef.current.signal
      );

      return data;
    },
    onSuccess: (data) => {
      const newAudioData: AudioClassData = {
        audioBase64: data.audio_base64 || '',
        audioUrl: data.audio_url,
        durationSeconds: data.duration_seconds,
        mode: data.mode,
        studentName: data.student_name,
        generatedAt: new Date().toISOString(),
      };

      setAudioData(newAudioData);
      setCurrentTime(0);
      setIsPlaying(false);

      // Cache audio data (if base64 is small enough for localStorage)
      try {
        if (
          newAudioData.audioBase64 &&
          newAudioData.audioBase64.length < 4 * 1024 * 1024
        ) {
          const audioKey = getAudioStorageKey(courseId, episodeId);
          localStorage.setItem(audioKey, JSON.stringify(newAudioData));
        }
      } catch (e) {
        console.warn('Failed to cache audio data:', e);
      }
    },
  });

  // Audio controls
  const play = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.play();
    }
  }, []);

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
  }, []);

  const togglePlay = useCallback(() => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }, [isPlaying, play, pause]);

  const seek = useCallback(
    (time: number) => {
      if (audioRef.current) {
        audioRef.current.currentTime = Math.max(0, Math.min(time, duration));
        setCurrentTime(audioRef.current.currentTime);
      }
    },
    [duration]
  );

  const skipForward = useCallback(
    (seconds: number = 10) => {
      seek(currentTime + seconds);
    },
    [currentTime, seek]
  );

  const skipBackward = useCallback(
    (seconds: number = 10) => {
      seek(currentTime - seconds);
    },
    [currentTime, seek]
  );

  const setPlaybackRate = useCallback((rate: PlaybackRate) => {
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
    setPlaybackRateState(rate);
  }, []);

  // Update settings
  const updateSettings = useCallback(
    (newSettings: Partial<AudioClassSettings>) => {
      setSettings((prev) => ({ ...prev, ...newSettings }));
    },
    []
  );

  // Cancel generation
  const cancelGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // Reset audio (clear current audio data from memory)
  const resetAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }
    setAudioData(null);
    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);

    try {
      const audioKey = getAudioStorageKey(courseId, episodeId);
      localStorage.removeItem(audioKey);
    } catch (e) {
      console.warn('Failed to clear audio cache:', e);
    }
  }, [courseId, episodeId]);

  // Format time helper (mm:ss)
  const formatTime = useCallback((seconds: number): string => {
    if (!isFinite(seconds) || isNaN(seconds) || seconds < 0) {
      return '--:--';
    }
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  // Progress percentage
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return {
    // User info
    studentName,

    // Audio data
    audioData,
    hasAudio: !!audioData,

    // Settings
    settings,
    updateSettings,
    voiceOptions: VOICE_OPTIONS,

    // Playback state
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    progress,
    playbackRates: PLAYBACK_RATES,

    // Playback controls
    play,
    pause,
    togglePlay,
    seek,
    skipForward,
    skipBackward,
    setPlaybackRate,

    // Actions
    generate: generateMutation.mutate,
    cancelGeneration,
    resetAudio,

    // Mutation state
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    // Helpers
    formatTime,
    modeLabel: AUDIO_MODE_LABELS[settings.mode],
    modeLables: AUDIO_MODE_LABELS,
  };
}

// Re-export types
export type { AudioClassSettings, AudioClassData };

// Re-export constants for convenience
export { PLAYBACK_RATES, VOICE_OPTIONS, AUDIO_MODE_LABELS as MODE_LABELS } from '@/lib/academy/constants';
export type { AudioMode } from '@/lib/academy/types';
