// =============================================================================
// useYouTubeRecommendations Hook - Faiston Academy
// =============================================================================
// Hook for fetching and caching YouTube video recommendations.
// Uses AgentCore search_youtube action for AI-powered video discovery.
// =============================================================================

'use client';

import { useState, useEffect, useCallback } from 'react';
import { searchYouTube } from '@/services/academyAgentcore';
import type { YouTubeVideo } from '@/lib/academy/types';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

interface UseYouTubeRecommendationsOptions {
  courseId: string;
  episodeId: string;
  episodeTitle?: string;
  courseCategory?: string;
}

interface YouTubeRecommendation extends YouTubeVideo {
  id: string;
}

interface CachedRecommendations {
  recommendations: YouTubeRecommendation[];
  queries: string[];
  fetchedAt: number;
}

// Cache TTL: 24 hours
const CACHE_TTL = 24 * 60 * 60 * 1000;

const getCacheKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.YOUTUBE_RECOMMENDATIONS_PREFIX}${courseId}_${episodeId}`;

// Generate YouTube watch URL
function generateWatchUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

// Generate YouTube search URL (fallback)
function generateSearchUrl(query: string): string {
  const encodedQuery = encodeURIComponent(query);
  return `https://www.youtube.com/results?search_query=${encodedQuery}`;
}

// Transform AgentCore response to recommendations
function transformToRecommendations(
  videos: YouTubeVideo[]
): YouTubeRecommendation[] {
  return videos.map((video, index) => ({
    ...video,
    id: `yt-rec-${index}-${Date.now()}`,
  }));
}

// Check if cache exists and is valid
function hasCachedRecommendations(courseId: string, episodeId: string): boolean {
  if (typeof window === 'undefined') return false;

  const cacheKey = getCacheKey(courseId, episodeId);
  try {
    const cached = localStorage.getItem(cacheKey);
    if (!cached) return false;

    const data: CachedRecommendations = JSON.parse(cached);
    return Date.now() - data.fetchedAt < CACHE_TTL;
  } catch {
    return false;
  }
}

/**
 * Prefetch YouTube recommendations in background.
 * Call this when classroom loads to have data ready when user opens Library panel.
 */
export async function prefetchYouTubeRecommendations(
  courseId: string,
  episodeId: string,
  episodeTitle: string,
  courseCategory: string,
  transcription: string
): Promise<void> {
  // Skip if already cached
  if (hasCachedRecommendations(courseId, episodeId)) {
    return;
  }

  // Skip if no transcription
  if (!transcription) {
    return;
  }

  const cacheKey = getCacheKey(courseId, episodeId);

  try {
    const response = await searchYouTube({
      transcription: transcription.slice(0, 2000),
      episode_title: episodeTitle,
      category: courseCategory,
    });

    const data = response.data;

    if (!data.success || !data.videos || data.videos.length === 0) {
      console.warn('YouTube prefetch: No videos found');
      return;
    }

    const recommendations = transformToRecommendations(data.videos);

    const cacheData: CachedRecommendations = {
      recommendations,
      queries: data.queries || [],
      fetchedAt: Date.now(),
    };
    localStorage.setItem(cacheKey, JSON.stringify(cacheData));

    console.log(
      `YouTube recommendations prefetched: ${recommendations.length} videos`
    );
  } catch (err) {
    console.warn('YouTube prefetch failed:', err);
  }
}

export function useYouTubeRecommendations({
  courseId,
  episodeId,
  episodeTitle = 'Aula',
  courseCategory = 'Educacao',
}: UseYouTubeRecommendationsOptions) {
  const [recommendations, setRecommendations] = useState<
    YouTubeRecommendation[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVideo, setSelectedVideo] =
    useState<YouTubeRecommendation | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const cacheKey = getCacheKey(courseId, episodeId);

  // Load from cache on mount
  useEffect(() => {
    try {
      const cached = localStorage.getItem(cacheKey);
      if (cached) {
        const data: CachedRecommendations = JSON.parse(cached);
        if (Date.now() - data.fetchedAt < CACHE_TTL) {
          setRecommendations(data.recommendations);
        }
      }
    } catch {
      // Ignore cache errors
    }
  }, [cacheKey]);

  // Fetch recommendations
  const fetchRecommendations = useCallback(
    async (transcription: string) => {
      if (!transcription || isLoading) return;

      setIsLoading(true);
      setError(null);

      try {
        const response = await searchYouTube({
          transcription: transcription.slice(0, 2000),
          episode_title: episodeTitle,
          category: courseCategory,
        });

        const data = response.data;

        if (!data.success) {
          throw new Error(data.error || 'Busca falhou');
        }

        if (!data.videos || data.videos.length === 0) {
          throw new Error('Nenhum video encontrado');
        }

        const newRecommendations = transformToRecommendations(data.videos);
        setRecommendations(newRecommendations);

        // Save to cache
        const cacheData: CachedRecommendations = {
          recommendations: newRecommendations,
          queries: data.queries || [],
          fetchedAt: Date.now(),
        };
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Erro ao buscar recomendacoes';
        setError(message);
        console.error('YouTube recommendations error:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [cacheKey, courseCategory, episodeTitle, isLoading]
  );

  // Clear cache and refetch
  const refreshRecommendations = useCallback(
    async (transcription: string) => {
      try {
        localStorage.removeItem(cacheKey);
      } catch {
        // Ignore
      }
      setRecommendations([]);
      await fetchRecommendations(transcription);
    },
    [cacheKey, fetchRecommendations]
  );

  // Video modal handlers
  const openVideo = useCallback((video: YouTubeRecommendation) => {
    setSelectedVideo(video);
    setIsModalOpen(true);
  }, []);

  const closeVideo = useCallback(() => {
    setSelectedVideo(null);
    setIsModalOpen(false);
  }, []);

  // Open YouTube video in new tab
  const openInYouTube = useCallback((video: YouTubeRecommendation) => {
    if (video.videoId) {
      window.open(generateWatchUrl(video.videoId), '_blank', 'noopener,noreferrer');
    } else {
      window.open(
        generateSearchUrl(video.searchQuery),
        '_blank',
        'noopener,noreferrer'
      );
    }
  }, []);

  return {
    recommendations,
    isLoading,
    error,
    hasRecommendations: recommendations.length > 0,
    hasCachedData: recommendations.length > 0,
    fetchRecommendations,
    refreshRecommendations,
    selectedVideo,
    isModalOpen,
    openVideo,
    closeVideo,
    openInYouTube,
  };
}

// Re-export types
export type { YouTubeRecommendation };
