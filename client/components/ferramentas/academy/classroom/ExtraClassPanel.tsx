// =============================================================================
// Extra Class Panel - Faiston Academy
// =============================================================================
// Personalized video lessons with HeyGen API for avatar-based explanations.
// Students can describe their doubts and receive custom AI-generated videos.
// =============================================================================

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GraduationCap,
  Loader2,
  AlertCircle,
  RefreshCw,
  Play,
  Clock,
  Video,
  Lightbulb,
  CheckCircle,
  XCircle,
  Sparkles,
  Trash2,
  History,
  Circle,
  Timer,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import {
  useExtraClass,
  type VideoHistoryItem,
  type VideoHistoryStatus,
} from '@/hooks/academy/useExtraClass';

interface ExtraClassPanelProps {
  episodeId: string;
  onSeek?: (time: number) => void;
  transcription?: string;
}

// Generate transcription path based on courseId and episodeId
function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

// Get original video URL from course data
function getOriginalVideoPath(courseId: string, episodeId: string): string {
  return `/videos/course-${courseId}/ep${episodeId}.mp4`;
}

// Example doubts for inspiration
const EXAMPLE_DOUBTS = [
  'Nao entendi bem a parte sobre...',
  'Pode explicar melhor como funciona...',
  'Qual a diferenca entre... e...?',
  'Por que isso e importante na pratica?',
];

// Status badge configuration
const STATUS_CONFIG: Record<
  VideoHistoryStatus,
  { color: string; bgColor: string; label: string; pulse?: boolean }
> = {
  pending: {
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/20',
    label: 'Pendente',
    pulse: true,
  },
  processing: {
    color: 'text-[var(--faiston-magenta-mid,#C31B8C)]',
    bgColor: 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20',
    label: 'Processando',
    pulse: true,
  },
  completed: { color: 'text-green-400', bgColor: 'bg-green-500/20', label: 'Concluido' },
  failed: { color: 'text-red-400', bgColor: 'bg-red-500/20', label: 'Erro' },
  timeout: { color: 'text-orange-400', bgColor: 'bg-orange-500/20', label: 'Tempo Excedido' },
};

// Format relative time
const formatRelativeTime = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Agora';
  if (diffMins < 60) return `${diffMins} min atras`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h atras`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d atras`;
};

export function ExtraClassPanel({ episodeId, onSeek }: ExtraClassPanelProps) {
  const { courseId, setExtraclassReady } = useAcademyClassroom();
  const [transcription, setTranscription] = useState<string>('');
  const [loadingTranscription, setLoadingTranscription] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Inline video popup state
  const [popupVideoTime, setPopupVideoTime] = useState<number | null>(null);
  const [popupVideoTopic, setPopupVideoTopic] = useState<string>('');
  const popupVideoRef = useRef<HTMLVideoElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  const {
    studentName,
    phase,
    message,
    doubt,
    extraClassData,
    progress,
    generateVideo,
    reset,
    clearAll,
    setDoubt,
    isLoading,
    hasPendingVideo,
    minDoubtLength,
    history,
    activeVideoId,
    selectFromHistory,
    deleteFromHistory,
    elapsedTime,
    maxPollMinutes,
  } = useExtraClass({ courseId, episodeId, onSeek, onVideoReady: () => setExtraclassReady(true) });

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

  // Handle generate button
  const handleGenerate = () => {
    if (transcription && doubt.trim().length >= minDoubtLength) {
      generateVideo(transcription, doubt);
    }
  };

  // Handle timestamp click - opens inline video popup
  const handleTimestampClick = (time: number, topic: string) => {
    setPopupVideoTime(time);
    setPopupVideoTopic(topic);
  };

  // Close popup
  const closePopup = useCallback(() => {
    setPopupVideoTime(null);
    setPopupVideoTopic('');
  }, []);

  // Seek popup video when opened
  useEffect(() => {
    if (popupVideoTime !== null && popupVideoRef.current) {
      const video = popupVideoRef.current;
      video.currentTime = popupVideoTime;
      video.addEventListener(
        'seeked',
        () => {
          video.play().catch(() => {});
        },
        { once: true }
      );
    }
  }, [popupVideoTime]);

  // Close popup on click outside
  useEffect(() => {
    if (popupVideoTime === null) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        closePopup();
      }
    };

    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [popupVideoTime, closePopup]);

  // Close popup on Escape key
  useEffect(() => {
    if (popupVideoTime === null) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closePopup();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [popupVideoTime, closePopup]);

  // Format duration (mm:ss)
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Render phase-specific content
  const renderContent = () => {
    // Completed state - two-column layout: video | info
    if (phase === 'completed' && extraClassData?.videoUrl) {
      return (
        <div className="relative flex gap-5 h-full">
          {/* Left Column - Video Player */}
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="relative aspect-video bg-black rounded-xl overflow-hidden">
              <video
                ref={videoRef}
                src={extraClassData.videoUrl}
                controls
                className="w-full h-full object-contain"
                poster={extraClassData.thumbnailUrl}
              />
            </div>
          </div>

          {/* Right Column - Info */}
          <div className="w-[320px] flex flex-col shrink-0">
            {/* Doubt Card */}
            <div className="p-4 bg-white/5 rounded-xl border border-white/10 mb-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center shrink-0">
                  <Lightbulb className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white/80 font-medium mb-1">Sua duvida:</p>
                  <p className="text-sm text-white/60">{extraClassData.doubt}</p>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            {extraClassData.timestamps.length > 0 && (
              <div className="flex-1 min-h-0 flex flex-col">
                <h4 className="text-sm font-medium text-white/80 mb-3 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                  Referencias no Video Original
                </h4>
                <ScrollArea className="flex-1">
                  <div className="space-y-2 pr-2">
                    {extraClassData.timestamps.map((ts, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleTimestampClick(ts.time, ts.topic)}
                        className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-all text-left group"
                      >
                        <span className="px-2 py-1 rounded bg-[var(--faiston-magenta-mid,#C31B8C)]/20 text-[var(--faiston-magenta-mid,#C31B8C)] text-xs font-mono shrink-0 group-hover:bg-[var(--faiston-magenta-mid,#C31B8C)]/30">
                          {formatDuration(ts.time)}
                        </span>
                        <span className="text-sm text-white/70 group-hover:text-white/90">
                          {ts.topic}
                        </span>
                        <Play className="w-4 h-4 text-white/30 group-hover:text-[var(--faiston-magenta-mid,#C31B8C)] ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            {/* Actions */}
            <div className="mt-4 pt-4 border-t border-white/10 flex gap-2">
              <Button
                onClick={reset}
                className="flex-1 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white border-0"
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Nova Aula
              </Button>
              <Button
                onClick={clearAll}
                variant="ghost"
                className="bg-white/5 hover:bg-white/10 text-white/60 hover:text-red-400"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Inline Video Popup */}
          <AnimatePresence>
            {popupVideoTime !== null && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm rounded-xl"
              >
                <motion.div
                  ref={popupRef}
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.9, opacity: 0 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                  className="relative w-[90%] max-w-[800px] bg-[#151720] rounded-xl overflow-hidden border border-white/20 shadow-2xl"
                >
                  {/* Popup Header */}
                  <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)]/10 to-[var(--faiston-blue-mid,#2226C0)]/10 border-b border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="px-2 py-1 rounded bg-[var(--faiston-magenta-mid,#C31B8C)]/20 text-[var(--faiston-magenta-mid,#C31B8C)] text-sm font-mono">
                        {formatDuration(popupVideoTime)}
                      </div>
                      <span className="text-sm text-white/80 truncate max-w-[400px]">
                        {popupVideoTopic}
                      </span>
                    </div>
                    <button
                      onClick={closePopup}
                      className="p-1.5 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                      title="Fechar (ESC)"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Video Player */}
                  <div className="aspect-video bg-black">
                    <video
                      ref={popupVideoRef}
                      src={getOriginalVideoPath(courseId, episodeId)}
                      controls
                      className="w-full h-full"
                    />
                  </div>

                  {/* Popup Footer */}
                  <div className="px-4 py-2 bg-white/5 border-t border-white/10 text-xs text-white/40 text-center">
                    Pressione{' '}
                    <kbd className="px-1.5 py-0.5 rounded bg-white/10 text-white/60 font-mono">
                      ESC
                    </kbd>{' '}
                    ou clique fora para fechar
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      );
    }

    // Loading/Processing states
    if (phase === 'validating' || phase === 'generating' || phase === 'polling') {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          {/* Animated Icon */}
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            className="w-16 h-16 rounded-full bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center mb-6 border border-[var(--faiston-magenta-mid,#C31B8C)]/30"
          >
            {phase === 'polling' ? (
              <Video className="w-8 h-8 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            ) : (
              <Loader2 className="w-8 h-8 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            )}
          </motion.div>

          {/* Message */}
          <h3 className="text-lg font-semibold text-white mb-2">
            {phase === 'validating' && 'Analisando sua duvida...'}
            {phase === 'generating' && 'Criando sua aula personalizada...'}
            {phase === 'polling' && 'O NEXO esta gravando seu video...'}
          </h3>
          <p className="text-sm text-white/60 mb-6 max-w-xs">{message}</p>

          {/* Progress Bar */}
          <div className="w-full max-w-xs">
            <div className="flex justify-between text-xs text-white/40 mb-2">
              <span>Progresso</span>
              <span>{Math.round(progress.percentage)}%</span>
            </div>
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progress.percentage}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="h-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] via-[var(--faiston-blue-mid,#2226C0)] to-[var(--faiston-magenta-mid,#C31B8C)] rounded-full"
              />
            </div>
          </div>

          {/* Enhanced time info for polling */}
          {phase === 'polling' && (
            <div className="mt-6 p-4 bg-white/5 rounded-xl border border-white/10 max-w-sm">
              <div className="flex items-center justify-center gap-2 mb-2">
                <Timer className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                <span className="text-sm font-medium text-white">
                  Tempo decorrido: {elapsedTime}
                </span>
              </div>
              <p className="text-xs text-white/50 text-center">
                Estimativa: 8-12 minutos (pode levar ate {maxPollMinutes} min)
              </p>
              <p className="text-[10px] text-white/30 mt-2 text-center">
                💡 Voce pode fechar esta janela. Voce sera notificado quando o video estiver pronto.
              </p>
            </div>
          )}
        </div>
      );
    }

    // Invalid state - doubt not related
    if (phase === 'invalid') {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <div className="w-16 h-16 rounded-full bg-yellow-500/10 flex items-center justify-center mb-6 border border-yellow-500/30">
            <AlertCircle className="w-8 h-8 text-yellow-400" />
          </div>

          <h3 className="text-lg font-semibold text-white mb-2">Duvida nao relacionada</h3>
          <p className="text-sm text-white/60 mb-6 max-w-xs">{message}</p>

          <Button
            onClick={reset}
            className="bg-white/10 hover:bg-white/20 text-white border border-white/20"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Tentar Novamente
          </Button>
        </div>
      );
    }

    // Failed state
    if (phase === 'failed') {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-6 border border-red-500/30">
            <XCircle className="w-8 h-8 text-red-400" />
          </div>

          <h3 className="text-lg font-semibold text-white mb-2">Ops! Algo deu errado</h3>
          <p className="text-sm text-white/60 mb-6 max-w-xs">{message}</p>

          <Button
            onClick={reset}
            className="bg-white/10 hover:bg-white/20 text-white border border-white/20"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Tentar Novamente
          </Button>
        </div>
      );
    }

    // Idle state - two-column layout: input form | history sidebar
    return (
      <div className="flex gap-6 h-full">
        {/* Left Column - Input Form */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Introduction */}
          <div className="mb-6 p-4 bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/10 to-[var(--faiston-blue-mid,#2226C0)]/10 rounded-xl border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/30 to-[var(--faiston-blue-mid,#2226C0)]/30 flex items-center justify-center shrink-0">
                <GraduationCap className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white mb-1">Ola, {studentName}! 👋</h4>
                <p className="text-xs text-white/60">
                  Me conte o que voce nao entendeu e eu vou criar uma aula em video personalizada so
                  para voce!
                </p>
              </div>
            </div>
          </div>

          {/* Doubt Input */}
          <div className="flex-1 flex flex-col">
            <label className="block text-sm font-medium text-white/80 mb-2">
              Qual sua duvida sobre esta aula?
            </label>
            <Textarea
              value={doubt}
              onChange={(e) => setDoubt(e.target.value)}
              placeholder="Descreva o que voce nao entendeu..."
              className="flex-1 bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none min-h-[120px]"
            />
            <div className="flex justify-between items-center mt-2">
              <span
                className={`text-xs ${
                  doubt.length < minDoubtLength ? 'text-white/40' : 'text-green-400'
                }`}
              >
                {doubt.length}/{minDoubtLength} caracteres minimos
              </span>
              {doubt.length >= minDoubtLength && <CheckCircle className="w-4 h-4 text-green-400" />}
            </div>
          </div>

          {/* Example Prompts */}
          <div className="mt-4">
            <label className="block text-xs font-medium text-white/60 mb-2">
              <Sparkles className="w-3 h-3 inline-block mr-1 text-[var(--faiston-magenta-mid,#C31B8C)]" />
              Exemplos de duvidas
            </label>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_DOUBTS.map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => setDoubt(example)}
                  className="px-3 py-1.5 rounded-full text-xs bg-white/5 text-white/60 border border-white/10 hover:bg-white/10 hover:text-white/80 transition-all"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          {/* Generate Button */}
          <div className="mt-6">
            <Button
              onClick={handleGenerate}
              disabled={
                isLoading ||
                loadingTranscription ||
                !transcription ||
                doubt.trim().length < minDoubtLength
              }
              className="w-full h-12 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] via-[var(--faiston-blue-mid,#2226C0)] to-[var(--faiston-magenta-mid,#C31B8C)] hover:opacity-90 text-white font-semibold rounded-xl border-0 transition-all"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Processando...
                </>
              ) : hasPendingVideo ? (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Continuar Verificacao
                </>
              ) : (
                <>
                  <Video className="w-4 h-4 mr-2" />
                  Gerar Aula Extra
                </>
              )}
            </Button>
            {loadingTranscription && (
              <p className="text-xs text-white/40 text-center mt-2">Carregando transcricao...</p>
            )}
          </div>
        </div>

        {/* Right Column - History Sidebar */}
        <div className="w-[280px] shrink-0 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <History className="w-4 h-4 text-white/60" />
            <h4 className="text-sm font-medium text-white/80">Ultimos Videos</h4>
            {history.length > 0 && (
              <span className="text-xs text-white/40 ml-auto">{history.length}/5</span>
            )}
          </div>

          {history.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-4 bg-white/5 rounded-xl border border-white/10">
              <Video className="w-10 h-10 text-white/20 mb-3" />
              <p className="text-sm text-white/40">Nenhum video gerado ainda</p>
              <p className="text-xs text-white/30 mt-1">Seus videos aparecerao aqui</p>
            </div>
          ) : (
            <ScrollArea className="flex-1 -mr-4 pr-4">
              <div className="space-y-3">
                {history.map((item: VideoHistoryItem) => {
                  const statusConfig = STATUS_CONFIG[item.status];
                  const isActive = item.videoId === activeVideoId;

                  return (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`group relative p-3 rounded-xl border transition-all cursor-pointer ${
                        isActive
                          ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/10 border-[var(--faiston-magenta-mid,#C31B8C)]/30'
                          : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                      }`}
                      onClick={() => selectFromHistory(item)}
                    >
                      {/* Status Badge */}
                      <div className="flex items-center gap-2 mb-2">
                        <div
                          className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full ${statusConfig.bgColor}`}
                        >
                          {statusConfig.pulse ? (
                            <motion.div
                              animate={{ scale: [1, 1.2, 1], opacity: [0.7, 1, 0.7] }}
                              transition={{ duration: 1.5, repeat: Infinity }}
                            >
                              <Circle className={`w-2 h-2 ${statusConfig.color} fill-current`} />
                            </motion.div>
                          ) : (
                            <Circle className={`w-2 h-2 ${statusConfig.color} fill-current`} />
                          )}
                          <span className={`text-[10px] font-medium ${statusConfig.color}`}>
                            {statusConfig.label}
                          </span>
                        </div>
                        <span className="text-[10px] text-white/40 ml-auto">
                          {formatRelativeTime(item.createdAt)}
                        </span>
                      </div>

                      {/* Doubt Preview */}
                      <p className="text-xs text-white/70 line-clamp-2 mb-2">{item.doubt}</p>

                      {/* Duration (if completed) */}
                      {item.status === 'completed' && item.duration && (
                        <div className="flex items-center gap-1 text-[10px] text-white/40">
                          <Clock className="w-3 h-3" />
                          {formatDuration(item.duration)}
                        </div>
                      )}

                      {/* Delete Button (on hover) */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteFromHistory(item.videoId);
                        }}
                        className="absolute top-2 right-2 p-1 rounded-md bg-red-500/0 hover:bg-red-500/20 text-white/0 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                        title="Remover do historico"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </motion.div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-black/20">
      {/* Header */}
      <div className="px-6 py-5 border-b border-white/10">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
            <GraduationCap className="w-6 h-6 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </div>
          <div>
            <h3 className="text-xl font-semibold text-white">Aulas Extras</h3>
            <p className="text-sm text-white/40">Videos personalizados pelo NEXO</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-5">{renderContent()}</div>
      </ScrollArea>
    </div>
  );
}
