// =============================================================================
// Video Player Panel - Faiston Academy
// =============================================================================
// HTML5 video player with custom controls, progress tracking, and seeking.
// Supports external seek requests from MindMap/Transcription panels.
// =============================================================================

'use client';

import { useRef, useState, useEffect, startTransition } from 'react';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  SkipBack,
  SkipForward,
  Loader2,
  Video,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

interface Episode {
  id: string;
  title: string;
  description?: string;
  thumbnailUrl?: string;
  videoUrl: string;
  duration?: number;
}

interface VideoPlayerPanelProps {
  episode: Episode;
  courseId: string;
  episodeId: string;
  onTimeUpdate?: (time: number) => void;
  onVideoRef?: (ref: HTMLVideoElement | null) => void;
  pendingSeekTime?: number | null;
  onSeekComplete?: () => void;
  onVideoEnded?: () => void;
}

export function VideoPlayerPanel({
  episode,
  courseId,
  episodeId,
  onTimeUpdate,
  onVideoRef,
  pendingSeekTime,
  onSeekComplete,
  onVideoEnded,
}: VideoPlayerPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showControls, setShowControls] = useState(true);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const controlsTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const hasRestoredProgressRef = useRef(false);
  const prevEpisodeIdRef = useRef<string | null>(null);
  const pendingSeekTimeRef = useRef<number | null>(pendingSeekTime ?? null);

  useEffect(() => {
    pendingSeekTimeRef.current = pendingSeekTime ?? null;
  }, [pendingSeekTime]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const time = videoRef.current.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleFullscreen = () => {
    if (videoRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        videoRef.current.requestFullscreen();
      }
    }
  };

  const handleSkip = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(
        0,
        Math.min(duration, videoRef.current.currentTime + seconds)
      );
    }
  };

  const resetControlsTimeout = () => {
    setShowControls(true);
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current);
    }
    controlsTimeoutRef.current = setTimeout(() => {
      if (isPlaying) {
        setShowControls(false);
      }
    }, 3000);
  };

  useEffect(() => {
    return () => {
      if (controlsTimeoutRef.current) {
        clearTimeout(controlsTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    onVideoRef?.(videoRef.current);
    return () => onVideoRef?.(null);
  }, [onVideoRef]);

  // Save video progress
  useEffect(() => {
    if (currentTime < 5) return;

    const timeout = setTimeout(() => {
      const key = `${ACADEMY_STORAGE_KEYS.PROGRESS_PREFIX}video_${courseId}_${episodeId}`;
      localStorage.setItem(key, String(currentTime));
    }, 2000);

    return () => clearTimeout(timeout);
  }, [currentTime, courseId, episodeId]);

  // Reset video when episode changes
  useEffect(() => {
    if (prevEpisodeIdRef.current === null) {
      prevEpisodeIdRef.current = episode.id;
      return;
    }

    if (prevEpisodeIdRef.current !== episode.id && videoRef.current) {
      startTransition(() => {
        setIsPlaying(false);
        setCurrentTime(0);
        setIsInitialLoading(true);
      });
      hasRestoredProgressRef.current = false;
      videoRef.current.load();
      prevEpisodeIdRef.current = episode.id;
    }
  }, [episode.id]);

  // Hide loading overlay when video is ready
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleCanPlay = () => {
      startTransition(() => {
        setIsInitialLoading(false);
      });
    };

    if (video.readyState >= 3) {
      startTransition(() => {
        setIsInitialLoading(false);
      });
    }

    video.addEventListener('canplay', handleCanPlay);
    return () => video.removeEventListener('canplay', handleCanPlay);
  }, [episode.id]);

  // Resume video from saved position or perform pending seek
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadataForRestore = () => {
      if (hasRestoredProgressRef.current) return;
      hasRestoredProgressRef.current = true;

      const seekTime = pendingSeekTimeRef.current;
      if (seekTime !== null && seekTime !== undefined) {
        video.currentTime = seekTime;
        startTransition(() => {
          setCurrentTime(seekTime);
        });
        video.play().catch(() => {});
        onSeekComplete?.();
        return;
      }

      const key = `${ACADEMY_STORAGE_KEYS.PROGRESS_PREFIX}video_${courseId}_${episodeId}`;
      const saved = localStorage.getItem(key);

      if (saved && video.duration) {
        const savedTime = parseFloat(saved);
        if (savedTime > 0 && savedTime < video.duration * 0.95) {
          video.currentTime = savedTime;
          startTransition(() => {
            setCurrentTime(savedTime);
          });
        }
      }
    };

    video.addEventListener('loadedmetadata', handleLoadedMetadataForRestore);

    if (video.readyState >= 1) {
      handleLoadedMetadataForRestore();
    }

    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadataForRestore);
    };
  }, [episode.id, courseId, episodeId, onSeekComplete]);

  // Handle external seek requests
  useEffect(() => {
    const video = videoRef.current;

    if (!video || pendingSeekTime === null || pendingSeekTime === undefined) return;

    const targetTime = pendingSeekTime;
    hasRestoredProgressRef.current = true;

    const performSeek = () => {
      video.currentTime = targetTime;
      setCurrentTime(targetTime);
      video.play().catch(() => {});
      onSeekComplete?.();
    };

    if (video.readyState >= 1) {
      performSeek();
    } else {
      const handleLoadedMetadataForSeek = () => {
        video.removeEventListener('loadedmetadata', handleLoadedMetadataForSeek);
        performSeek();
      };
      video.addEventListener('loadedmetadata', handleLoadedMetadataForSeek);

      return () => {
        video.removeEventListener('loadedmetadata', handleLoadedMetadataForSeek);
      };
    }
  }, [pendingSeekTime, onSeekComplete]);

  return (
    <div
      className="h-full flex flex-col bg-black/20"
      onMouseMove={resetControlsTimeout}
      onMouseLeave={() => isPlaying && setShowControls(false)}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
            <Video className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-white truncate">{episode.title}</h3>
            {episode.description && (
              <p className="text-xs text-white/40 truncate">{episode.description}</p>
            )}
          </div>
        </div>
      </div>

      {/* Video Container */}
      <div className="relative flex-1 flex items-center justify-center overflow-hidden">
        <video
          ref={videoRef}
          src={episode.videoUrl}
          poster={episode.thumbnailUrl}
          className="w-full h-full object-contain"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => {
            setIsPlaying(false);
            onVideoEnded?.();
          }}
          onClick={handlePlay}
        />

        {/* Loading Overlay */}
        <AnimatePresence>
          {isInitialLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-black/70 backdrop-blur-sm flex flex-col items-center justify-center z-10"
            >
              <Loader2 className="w-12 h-12 text-[var(--faiston-magenta-mid,#C31B8C)] animate-spin mb-4" />
              <p className="text-white/90 text-lg font-medium">Carregando aula...</p>
              <p className="text-white/60 text-sm mt-2">Preparando o video do treinamento</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Center Play Button */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: showControls ? 1 : 0 }}
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          {!isPlaying && (
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={handlePlay}
              className="w-16 h-16 rounded-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] flex items-center justify-center pointer-events-auto shadow-lg"
            >
              <Play className="w-8 h-8 text-white fill-white ml-1" />
            </motion.button>
          )}
        </motion.div>

        {/* Controls Overlay */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: showControls ? 1 : 0 }}
          className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-4"
        >
          {/* Progress Bar */}
          <div className="mb-3">
            <input
              type="range"
              min={0}
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1 bg-white/30 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-[var(--faiston-magenta-mid,#C31B8C)] [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
              style={{
                background: `linear-gradient(to right, var(--faiston-magenta-mid,#C31B8C) 0%, var(--faiston-magenta-mid,#C31B8C) ${(currentTime / (duration || 1)) * 100}%, rgba(255,255,255,0.3) ${(currentTime / (duration || 1)) * 100}%, rgba(255,255,255,0.3) 100%)`,
              }}
            />
          </div>

          {/* Controls Row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => handleSkip(-10)}
                className="text-white/80 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-colors"
              >
                <SkipBack className="w-5 h-5" />
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={handlePlay}
                className="w-10 h-10 rounded-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] flex items-center justify-center text-white"
              >
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => handleSkip(10)}
                className="text-white/80 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-colors"
              >
                <SkipForward className="w-5 h-5" />
              </motion.button>

              <span className="text-white/70 text-sm ml-2">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={handleMute}
                className="text-white/80 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-colors"
              >
                {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={handleFullscreen}
                className="text-white/80 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-colors"
              >
                <Maximize2 className="w-5 h-5" />
              </motion.button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
