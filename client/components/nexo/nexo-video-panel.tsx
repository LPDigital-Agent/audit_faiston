"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Play, Pause, Volume2, VolumeX, Maximize, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * NexoVideoPanel - Glass panel with NEXO Avatar presentation video
 *
 * Features:
 * - HTML5 native video player
 * - Custom controls overlay
 * - Glassmorphism container
 * - Lazy loading with preload="metadata" for performance
 */

export function NexoVideoPanel() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [progress, setProgress] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);

  const togglePlay = () => {
    if (!videoRef.current) return;

    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
      setHasStarted(true);
    }
    setIsPlaying(!isPlaying);
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const progress = (videoRef.current.currentTime / videoRef.current.duration) * 100;
    setProgress(progress);
  };

  const handleVideoEnd = () => {
    setIsPlaying(false);
    setProgress(0);
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    videoRef.current.currentTime = percentage * videoRef.current.duration;
  };

  const handleFullscreen = () => {
    if (!videoRef.current) return;
    if (videoRef.current.requestFullscreen) {
      videoRef.current.requestFullscreen();
    }
  };

  const handleRestart = () => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = 0;
    videoRef.current.play();
    setIsPlaying(true);
    setHasStarted(true);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className={cn(
        "glass-elevated rounded-2xl overflow-hidden",
        "border border-border",
        "flex flex-col"
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h2 className="text-xl font-bold text-text-primary">
          <span className="gradient-text-nexo">Nexo</span> se apresenta
        </h2>
      </div>

      {/* Video Container - portrait aspect ratio (9:16) */}
      <div
        className="relative aspect-[9/16] bg-black/20"
        onMouseEnter={() => setShowControls(true)}
        onMouseLeave={() => isPlaying && setShowControls(false)}
      >
        {/* Video Element - fills container */}
        <video
          ref={videoRef}
          src="/Videos/Nexo%20Apresenta%C3%A7%C3%A3o.mp4"
          className="absolute inset-0 w-full h-full object-cover"
          preload="metadata"
          onTimeUpdate={handleTimeUpdate}
          onEnded={handleVideoEnd}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          playsInline
        >
          Seu navegador não suporta vídeo HTML5.
        </video>

        {/* Play Overlay (before first play) */}
        {!hasStarted && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0 flex items-center justify-center bg-black/40 cursor-pointer"
            onClick={togglePlay}
          >
            <motion.div
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              className={cn(
                "w-20 h-20 rounded-full",
                "gradient-nexo",
                "flex items-center justify-center",
                "shadow-lg shadow-magenta-mid/30"
              )}
            >
              <Play className="w-10 h-10 text-white ml-1" fill="white" />
            </motion.div>
            <p className="absolute bottom-8 text-white/80 text-sm">
              Clique para assistir
            </p>
          </motion.div>
        )}

        {/* Custom Controls Overlay */}
        {hasStarted && (
          <motion.div
            initial={false}
            animate={{ opacity: showControls ? 1 : 0 }}
            transition={{ duration: 0.2 }}
            className={cn(
              "absolute bottom-0 left-0 right-0",
              "bg-gradient-to-t from-black/80 to-transparent",
              "p-4 pt-12",
              "pointer-events-none"
            )}
            style={{ pointerEvents: showControls ? "auto" : "none" }}
          >
            {/* Progress Bar */}
            <div
              className="h-1.5 bg-white/20 rounded-full mb-4 cursor-pointer group"
              onClick={handleSeek}
            >
              <div
                className="h-full gradient-nexo rounded-full relative transition-all"
                style={{ width: `${progress}%` }}
              >
                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow-md opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>

            {/* Control Buttons */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {/* Play/Pause */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={togglePlay}
                  className="text-white hover:bg-white/20"
                >
                  {isPlaying ? (
                    <Pause className="w-5 h-5" />
                  ) : (
                    <Play className="w-5 h-5" />
                  )}
                </Button>

                {/* Restart */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleRestart}
                  className="text-white hover:bg-white/20"
                >
                  <RotateCcw className="w-4 h-4" />
                </Button>

                {/* Volume */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleMute}
                  className="text-white hover:bg-white/20"
                >
                  {isMuted ? (
                    <VolumeX className="w-5 h-5" />
                  ) : (
                    <Volume2 className="w-5 h-5" />
                  )}
                </Button>
              </div>

              {/* Fullscreen */}
              <Button
                variant="ghost"
                size="icon"
                onClick={handleFullscreen}
                className="text-white hover:bg-white/20"
              >
                <Maximize className="w-5 h-5" />
              </Button>
            </div>
          </motion.div>
        )}
      </div>

    </motion.div>
  );
}

export default NexoVideoPanel;
