// =============================================================================
// useVideoClass Hook - Faiston Academy
// =============================================================================
// Hook for video class generation and playback.
// Uses synchronous generation pattern with AgentCore.
// Stores video URLs from S3 (no local IndexedDB storage for MVP).
//
// Features:
// - Synchronous generation (single request, waits for completion)
// - Settings persistence in localStorage
// - Audio playback controls
// - Slide navigation for slides_tts_mvp mode
// =============================================================================

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { generateVideoClass } from '@/services/academyAgentcore';
import type {
  VideoClassResponse,
  VideoFormat,
  VisualTheme,
  VideoSlideWithUrl,
} from '@/lib/academy/types';
import {
  ACADEMY_STORAGE_KEYS,
  FORMAT_LABELS,
  THEME_LABELS,
  PLAYBACK_RATES,
} from '@/lib/academy/constants';

// =============================================================================
// Types
// =============================================================================

export interface VideoClassSettings {
  format: VideoFormat;
  theme: VisualTheme;
  customPrompt: string;
}

export interface VideoSlide {
  id: number;
  type: string;
  title: string;
  duration_seconds: number;
  image_url: string | null;
}

export interface VideoClassData {
  videoUrl?: string;
  audioUrl?: string;
  duration: number;
  createdAt: string;
  format: VideoFormat;
  theme: VisualTheme;
  projectTitle: string;
  slideCount: number;
  isAudioOnly: boolean;
  phase: 'mvp' | 'phase2' | 'veo3' | 'slides_tts' | 'slides_tts_mvp';
  slides?: VideoSlide[];
  model?: string;
  concepts?: {
    main_concept: string;
    key_points: string[];
    visual_suggestions?: string[];
  };
}

interface UseVideoClassOptions {
  courseId: string;
  episodeId: string;
}

export type PlaybackRate = (typeof PLAYBACK_RATES)[number];

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_SETTINGS: VideoClassSettings = {
  format: 'brief',
  theme: 'educational',
  customPrompt: '',
};

const getSettingsStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.VIDEOCLASS_SETTINGS_PREFIX}${courseId}_${episodeId}`;

const getVideoStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.VIDEOCLASS_PREFIX}${courseId}_${episodeId}`;

// =============================================================================
// Hook Implementation
// =============================================================================

export function useVideoClass({ courseId, episodeId }: UseVideoClassOptions) {
  // Settings state
  const [settings, setSettings] = useState<VideoClassSettings>(DEFAULT_SETTINGS);

  // Video data state
  const [videoData, setVideoData] = useState<VideoClassData | null>(null);

  // Playback state
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(1);
  const [playbackRate, setPlaybackRateState] = useState<PlaybackRate>(1);

  // Slide navigation
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);

  // Abort controller for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load settings from localStorage on mount
  useEffect(() => {
    try {
      const settingsKey = getSettingsStorageKey(courseId, episodeId);
      const stored = localStorage.getItem(settingsKey);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<VideoClassSettings>;
        setSettings({
          format: parsed.format || DEFAULT_SETTINGS.format,
          theme: parsed.theme || DEFAULT_SETTINGS.theme,
          customPrompt: parsed.customPrompt ?? DEFAULT_SETTINGS.customPrompt,
        });
      }

      // Load cached video data
      const videoKey = getVideoStorageKey(courseId, episodeId);
      const storedVideo = localStorage.getItem(videoKey);
      if (storedVideo) {
        const parsedVideo = JSON.parse(storedVideo) as VideoClassData;
        if (parsedVideo.videoUrl || parsedVideo.audioUrl) {
          setVideoData(parsedVideo);
        }
      }
    } catch (e) {
      console.error('Failed to load video class settings:', e);
    }
  }, [courseId, episodeId]);

  // Save settings to localStorage when they change
  useEffect(() => {
    try {
      const settingsKey = getSettingsStorageKey(courseId, episodeId);
      localStorage.setItem(settingsKey, JSON.stringify(settings));
    } catch (e) {
      console.warn('Failed to save video class settings:', e);
    }
  }, [settings, courseId, episodeId]);

  // Create audio element when we have video data
  useEffect(() => {
    const audioUrl = videoData?.audioUrl || videoData?.videoUrl;
    if (!audioUrl) return;

    const audio = new Audio(audioUrl);

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

      // Auto-advance slides based on audio time
      if (videoData?.slides && videoData.slides.length > 0) {
        let accumulatedTime = 0;
        for (let i = 0; i < videoData.slides.length; i++) {
          accumulatedTime += videoData.slides[i].duration_seconds;
          if (audio.currentTime < accumulatedTime) {
            setCurrentSlideIndex(i);
            break;
          }
        }
      }
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
  }, [videoData?.audioUrl, videoData?.videoUrl, videoData?.slides]);

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
    mutationFn: async (transcription: string): Promise<VideoClassResponse> => {
      abortControllerRef.current = new AbortController();

      const { data } = await generateVideoClass(
        {
          transcription,
          format: settings.format,
          visual_theme: settings.theme,
          custom_prompt: settings.customPrompt || undefined,
          episode_id: episodeId,
        },
        abortControllerRef.current.signal
      );

      if (data.error) {
        throw new Error(data.error);
      }

      return data;
    },
    onSuccess: (data) => {
      // Transform slides
      const slides: VideoSlide[] =
        data.slides?.map((s) => ({
          id: s.id,
          type: s.type,
          title: s.title,
          duration_seconds: s.duration_seconds,
          image_url: s.image_url,
        })) || [];

      const newVideoData: VideoClassData = {
        videoUrl: data.video_url,
        audioUrl: data.audio_url,
        duration: data.duration_seconds,
        createdAt: new Date().toISOString(),
        format: data.format,
        theme: data.visual_theme,
        projectTitle: data.project_title,
        slideCount: data.slide_count || slides.length || 0,
        isAudioOnly: data.is_audio_only,
        phase: data.phase,
        slides: slides.length > 0 ? slides : undefined,
        model: data.model,
        concepts: data.concepts,
      };

      setVideoData(newVideoData);
      setCurrentTime(0);
      setIsPlaying(false);
      setCurrentSlideIndex(0);

      // Cache video data in localStorage (only metadata, not the actual video)
      try {
        const videoKey = getVideoStorageKey(courseId, episodeId);
        localStorage.setItem(videoKey, JSON.stringify(newVideoData));
      } catch (e) {
        console.warn('Failed to cache video data:', e);
      }
    },
  });

  // Playback controls
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

  const setVolume = useCallback((vol: number) => {
    const clampedVolume = Math.max(0, Math.min(1, vol));
    if (audioRef.current) {
      audioRef.current.volume = clampedVolume;
    }
    setVolumeState(clampedVolume);
  }, []);

  const setPlaybackRate = useCallback((rate: PlaybackRate) => {
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
    setPlaybackRateState(rate);
  }, []);

  // Slide navigation
  const goToSlide = useCallback(
    (index: number) => {
      if (!videoData?.slides || index < 0 || index >= videoData.slides.length) {
        return;
      }

      // Calculate the audio time for this slide
      let accumulatedTime = 0;
      for (let i = 0; i < index; i++) {
        accumulatedTime += videoData.slides[i].duration_seconds;
      }

      seek(accumulatedTime);
      setCurrentSlideIndex(index);
    },
    [videoData?.slides, seek]
  );

  const nextSlide = useCallback(() => {
    if (videoData?.slides) {
      goToSlide(currentSlideIndex + 1);
    }
  }, [videoData?.slides, currentSlideIndex, goToSlide]);

  const prevSlide = useCallback(() => {
    goToSlide(currentSlideIndex - 1);
  }, [currentSlideIndex, goToSlide]);

  // Settings actions
  const updateSettings = useCallback((newSettings: Partial<VideoClassSettings>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
  }, []);

  const setFormat = useCallback((format: VideoFormat) => {
    setSettings((prev) => ({ ...prev, format }));
  }, []);

  const setTheme = useCallback((theme: VisualTheme) => {
    setSettings((prev) => ({ ...prev, theme }));
  }, []);

  const setCustomPrompt = useCallback((customPrompt: string) => {
    setSettings((prev) => ({ ...prev, customPrompt }));
  }, []);

  // Cancel generation
  const cancelGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // Reset everything
  const reset = useCallback(() => {
    // Abort any pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // Stop audio playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }

    // Reset state
    setVideoData(null);
    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);
    setCurrentSlideIndex(0);
    setSettings(DEFAULT_SETTINGS);

    // Clear storage
    try {
      const settingsKey = getSettingsStorageKey(courseId, episodeId);
      const videoKey = getVideoStorageKey(courseId, episodeId);
      localStorage.removeItem(settingsKey);
      localStorage.removeItem(videoKey);
    } catch (e) {
      console.warn('Failed to clear video class storage:', e);
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

  // Current slide
  const currentSlide = videoData?.slides?.[currentSlideIndex] || null;

  return {
    // Settings
    settings,
    updateSettings,
    setFormat,
    setTheme,
    setCustomPrompt,

    // Video data
    videoData,
    hasVideo: videoData !== null,

    // Playback state
    isPlaying,
    currentTime,
    duration,
    volume,
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
    setVolume,
    setPlaybackRate,

    // Slide navigation
    currentSlideIndex,
    currentSlide,
    goToSlide,
    nextSlide,
    prevSlide,
    slideCount: videoData?.slides?.length || 0,

    // Actions
    generate: generateMutation.mutate,
    generateAsync: generateMutation.mutateAsync,
    cancelGeneration,
    reset,

    // Mutation state
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    // Helpers
    formatTime,
    formatLabel: FORMAT_LABELS[settings.format],
    themeLabel: THEME_LABELS[settings.theme],
  };
}

// Re-export types
export type { VideoFormat, VisualTheme };
