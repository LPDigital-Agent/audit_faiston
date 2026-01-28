// =============================================================================
// Library Panel - Faiston Academy
// =============================================================================
// Materials library with PDF viewing and AI-powered YouTube recommendations.
// Displays course materials and NEXO-curated video suggestions.
// =============================================================================

'use client';

import { useEffect } from 'react';
import {
  FileText,
  ExternalLink,
  Download,
  Eye,
  ArrowLeft,
  FolderOpen,
  Loader2,
  BookOpen,
  Sparkles,
  Youtube,
  Play,
  RefreshCw,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useLibrary, LibraryFile } from '@/hooks/academy/useLibrary';
import { useYouTubeRecommendations, YouTubeRecommendation } from '@/hooks/academy/useYouTubeRecommendations';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';

interface LibraryPanelProps {
  episodeId: string;
}

// Format file size
function formatSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// File icon component
function FileIcon({ type }: { type: 'pdf' | 'link' }) {
  return (
    <div
      className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
        type === 'pdf' ? 'bg-red-500/10' : 'bg-[var(--faiston-magenta-mid,#C31B8C)]/10'
      }`}
    >
      {type === 'pdf' ? (
        <FileText className="w-5 h-5 text-red-400" />
      ) : (
        <ExternalLink className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
      )}
    </div>
  );
}

// File item component
function FileItem({
  file,
  onPreview,
  onDownload,
}: {
  file: LibraryFile;
  onPreview: () => void;
  onDownload: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/15
                 rounded-xl p-3 transition-all duration-200"
    >
      <div className="flex items-start gap-3">
        <FileIcon type={file.type} />

        <div className="flex-1 min-w-0">
          <h4 className="text-white/90 font-medium truncate">{file.name}</h4>
          {file.description && (
            <p className="text-white/50 text-sm mt-0.5 line-clamp-2">{file.description}</p>
          )}
          <p className="text-white/30 text-xs mt-1">
            {file.type === 'pdf' ? `${formatSize(file.size)} • PDF` : file.domain}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-3">
        <button
          onClick={onPreview}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5
                     rounded-lg bg-white/10 hover:bg-white/20 text-white/70
                     hover:text-white text-sm transition-all"
        >
          <Eye className="w-3.5 h-3.5" />
          {file.type === 'link' ? 'Abrir' : 'Preview'}
        </button>
        {file.type === 'pdf' && (
          <button
            onClick={onDownload}
            className="flex items-center justify-center gap-1.5 px-3 py-1.5
                       rounded-lg bg-white/10 hover:bg-white/20 text-white/70
                       hover:text-white text-sm transition-all"
            title="Download"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </motion.div>
  );
}

// YouTube video thumbnail component
function VideoThumbnail({
  video,
  onClick,
  index,
}: {
  video: YouTubeRecommendation;
  onClick: () => void;
  index: number;
}) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={onClick}
      className="w-full flex items-start gap-3 p-2 rounded-xl
                 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-[var(--faiston-magenta-mid,#C31B8C)]/30
                 transition-all duration-200 text-left group"
    >
      {/* Real YouTube thumbnail */}
      <div className="relative w-[120px] h-[68px] rounded-lg bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-red-500/20 flex-shrink-0 overflow-hidden">
        {video.thumbnailUrl ? (
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <Youtube className="w-8 h-8 text-red-500/50" />
          </div>
        )}
        {/* Play overlay on hover */}
        <div className="absolute inset-0 bg-[var(--faiston-magenta-mid,#C31B8C)]/80 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
          <Play className="w-6 h-6 text-white fill-white" />
        </div>
      </div>

      {/* Video info */}
      <div className="flex-1 min-w-0 py-0.5">
        <p className="text-white/90 text-sm font-medium line-clamp-2 group-hover:text-white">
          {video.title}
        </p>
        <p className="text-white/40 text-xs mt-1 flex items-center gap-1">
          <Youtube className="w-3 h-3 text-red-500" />
          {video.channelTitle || 'YouTube'}
        </p>
      </div>
    </motion.button>
  );
}

// Empty state for materials
function EmptyMaterials() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <FolderOpen className="w-10 h-10 text-white/20 mb-2" />
      <p className="text-white/40 text-sm">Nenhum material disponivel</p>
    </div>
  );
}

// Empty state for recommendations
function EmptyRecommendations({
  onRetry,
  hasTranscription,
}: {
  onRetry: () => void;
  hasTranscription: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-6 text-center">
      <Sparkles className="w-8 h-8 text-[var(--faiston-magenta-mid,#C31B8C)]/30 mb-2" />
      <p className="text-white/40 text-sm">
        {hasTranscription ? 'Nenhuma recomendacao encontrada' : 'Transcricao nao disponivel'}
      </p>
      {hasTranscription && (
        <button
          onClick={onRetry}
          className="mt-2 text-[var(--faiston-magenta-mid,#C31B8C)] text-xs hover:text-[var(--faiston-magenta-mid,#C31B8C)]/80 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" />
          Tentar novamente
        </button>
      )}
    </div>
  );
}

// Loading state component
function LoadingState() {
  return (
    <div className="flex items-center justify-center py-8">
      <Loader2 className="w-6 h-6 text-white/50 animate-spin" />
    </div>
  );
}

// Loading state for recommendations
function RecommendationsLoading() {
  return (
    <div className="flex items-center gap-2 py-4 justify-center text-white/50">
      <Loader2 className="w-4 h-4 animate-spin text-[var(--faiston-magenta-mid,#C31B8C)]" />
      <span className="text-sm">NEXO esta buscando videos...</span>
    </div>
  );
}

// YouTube Video Modal component
function YouTubeVideoModal({
  video,
  isOpen,
  onClose,
  onOpenExternal,
}: {
  video: YouTubeRecommendation | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenExternal: (video: YouTubeRecommendation) => void;
}) {
  if (!video) return null;

  const embedUrl = `https://www.youtube.com/embed/${video.videoId}?autoplay=1&rel=0&hl=pt-BR`;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[800px] p-0 bg-[#0D0E12] border-white/10 overflow-hidden">
        <DialogHeader className="px-4 py-3 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <Youtube className="w-5 h-5 text-red-500 flex-shrink-0" />
              <DialogTitle className="text-white/90 text-sm font-medium truncate">
                {video.title}
              </DialogTitle>
            </div>
            <button
              onClick={() => onOpenExternal(video)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20
                         text-white/70 hover:text-white text-xs transition-all ml-2 flex-shrink-0"
              title="Abrir no YouTube"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">YouTube</span>
            </button>
          </div>
          <p className="text-white/40 text-xs mt-1">{video.channelTitle}</p>
        </DialogHeader>

        {/* Video embed container - 16:9 aspect ratio */}
        <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
          <iframe
            src={embedUrl}
            title={video.title}
            className="absolute inset-0 w-full h-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Preview view component
function PreviewView({
  file,
  onClose,
  onDownload,
}: {
  file: LibraryFile;
  onClose: () => void;
  onDownload: () => void;
}) {
  const handleLinkPreview = () => {
    window.open(file.url, '_blank', 'noopener,noreferrer');
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="h-full flex flex-col"
    >
      {/* Preview Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-3">
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="w-4 h-4 text-white/70" />
        </button>
        <span className="flex-1 text-white/90 font-medium truncate">{file.name}</span>
        {file.type === 'pdf' && (
          <button
            onClick={onDownload}
            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
            title="Download"
          >
            <Download className="w-4 h-4 text-white/70" />
          </button>
        )}
      </div>

      {/* Preview Content */}
      <div className="flex-1 p-2 min-h-0">
        {file.type === 'link' ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4">
            <ExternalLink className="w-12 h-12 text-[var(--faiston-magenta-mid,#C31B8C)] mb-4" />
            <p className="text-white/70 mb-2">Este link sera aberto em uma nova aba</p>
            <p className="text-white/40 text-sm mb-4">{file.domain}</p>
            <button
              onClick={handleLinkPreview}
              className="px-4 py-2 rounded-lg bg-[var(--faiston-magenta-mid,#C31B8C)]/20 hover:bg-[var(--faiston-magenta-mid,#C31B8C)]/30
                         text-[var(--faiston-magenta-mid,#C31B8C)] text-sm font-medium transition-colors"
            >
              Abrir Link
            </button>
          </div>
        ) : (
          <iframe
            src={`${file.url}#toolbar=0&navpanes=0`}
            className="w-full h-full rounded-lg bg-white"
            title={file.name}
          />
        )}
      </div>
    </motion.div>
  );
}

export function LibraryPanel({ episodeId }: LibraryPanelProps) {
  const { courseId, episodeTitle, courseCategory } = useAcademyClassroom();

  const {
    files,
    isLoading,
    selectedFile,
    isPreviewOpen,
    openPreview,
    closePreview,
    downloadFile,
    fileCount,
    transcription,
    isLoadingTranscription,
  } = useLibrary(episodeId, courseId);

  const {
    recommendations,
    isLoading: isLoadingRecommendations,
    error: recommendationsError,
    hasRecommendations,
    hasCachedData,
    fetchRecommendations,
    refreshRecommendations,
    openVideo,
    closeVideo,
    openInYouTube,
    selectedVideo,
    isModalOpen,
  } = useYouTubeRecommendations({
    courseId,
    episodeId,
    episodeTitle: episodeTitle || undefined,
    courseCategory: courseCategory || undefined,
  });

  // Auto-fetch recommendations when transcription is available and no cache
  useEffect(() => {
    if (transcription && !hasCachedData && !isLoadingRecommendations && !recommendationsError) {
      fetchRecommendations(transcription);
    }
  }, [transcription, hasCachedData, isLoadingRecommendations, recommendationsError, fetchRecommendations]);

  return (
    <div className="h-full flex flex-col bg-black/20">
      <AnimatePresence mode="wait">
        {isPreviewOpen && selectedFile ? (
          <PreviewView
            key="preview"
            file={selectedFile}
            onClose={closePreview}
            onDownload={() => downloadFile(selectedFile)}
          />
        ) : (
          <motion.div
            key="list"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="h-full flex flex-col"
          >
            {/* Header */}
            <div className="px-6 py-5 border-b border-white/10">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
                  <BookOpen className="w-6 h-6 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white">Biblioteca</h3>
                  <p className="text-sm text-white/40">Materiais e recomendacoes</p>
                </div>
              </div>
            </div>

            {/* Content with two sections */}
            <ScrollArea className="flex-1">
              {/* Materials Section */}
              <div className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <FileText className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                  <span className="text-sm font-medium text-white/60">Materiais da Aula</span>
                  <span className="text-xs text-white/30 ml-auto">{fileCount}</span>
                </div>

                {isLoading ? (
                  <LoadingState />
                ) : files.length === 0 ? (
                  <EmptyMaterials />
                ) : (
                  <div className="space-y-3">
                    {files.map((file, index) => (
                      <motion.div
                        key={file.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <FileItem
                          file={file}
                          onPreview={() => openPreview(file)}
                          onDownload={() => downloadFile(file)}
                        />
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>

              {/* Divider */}
              <div className="px-4">
                <div className="h-px bg-gradient-to-r from-transparent via-[var(--faiston-magenta-mid,#C31B8C)]/30 to-transparent" />
              </div>

              {/* NEXO Recommendations Section */}
              <div className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                  <span className="text-sm font-medium text-white/60">Recomendacoes do NEXO</span>
                  <Youtube className="w-4 h-4 text-red-500" />
                  {hasRecommendations && transcription && (
                    <button
                      onClick={() => refreshRecommendations(transcription)}
                      className="ml-auto p-1 hover:bg-white/10 rounded transition-colors"
                      title="Atualizar recomendacoes"
                    >
                      <RefreshCw className="w-3 h-3 text-white/40 hover:text-white/70" />
                    </button>
                  )}
                </div>

                {isLoadingTranscription || isLoadingRecommendations ? (
                  <RecommendationsLoading />
                ) : hasRecommendations ? (
                  <div className="space-y-2">
                    {recommendations.map((video, index) => (
                      <VideoThumbnail
                        key={video.id}
                        video={video}
                        onClick={() => openVideo(video)}
                        index={index}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyRecommendations
                    onRetry={() => transcription && fetchRecommendations(transcription)}
                    hasTranscription={!!transcription}
                  />
                )}

                {recommendationsError && (
                  <p className="text-red-400/70 text-xs text-center mt-2">{recommendationsError}</p>
                )}
              </div>
            </ScrollArea>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-white/5 flex justify-between">
              <span className="text-white/40 text-sm">
                {fileCount} {fileCount === 1 ? 'material' : 'materiais'}
              </span>
              <span className="text-white/40 text-sm">
                {recommendations.length} {recommendations.length === 1 ? 'video' : 'videos'}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* YouTube Video Modal */}
      <YouTubeVideoModal
        video={selectedVideo}
        isOpen={isModalOpen}
        onClose={closeVideo}
        onOpenExternal={openInYouTube}
      />
    </div>
  );
}
