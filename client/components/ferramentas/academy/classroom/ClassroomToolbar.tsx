// =============================================================================
// Classroom Toolbar - Faiston Academy
// =============================================================================
// Floating dock-style toolbar for toggling classroom panels.
// Inspired by macOS dock with glassmorphism styling.
// =============================================================================

'use client';

import {
  Video,
  FileText,
  Sparkles,
  RotateCcw,
  ArrowLeft,
  Type,
  Zap,
  Network,
  Headphones,
  BookOpen,
  Presentation,
  GraduationCap,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from '@/components/ui/tooltip';

interface ToolbarButtonProps {
  icon: React.ElementType;
  label: string;
  isActive?: boolean;
  onClick: () => void;
  shortcut?: string;
  variant?: 'default' | 'gradient';
  showBadge?: boolean;
  progress?: number | null;
}

function ToolbarButton({
  icon: Icon,
  label,
  isActive = true,
  onClick,
  shortcut,
  showBadge = false,
  progress = null,
}: ToolbarButtonProps) {
  const baseClasses =
    'flex items-center gap-2 px-3 py-2 rounded-xl transition-all font-medium text-sm relative overflow-visible';

  // Faiston brand gradient (magenta/blue)
  const activeClasses =
    'bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)]/30 to-[var(--faiston-blue-mid,#2226C0)]/30 text-white border border-[var(--faiston-magenta-mid,#C31B8C)]/40';
  const inactiveClasses =
    'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80';

  const isGenerating = progress !== null && progress < 100;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onClick}
          className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses}`}
        >
          <Icon className="w-4 h-4" />
          <span className="hidden sm:inline">{label}</span>

          {/* Percentage Badge (shown during generation) */}
          {isGenerating && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute -top-2 -right-2 px-1.5 py-0.5 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-full text-[10px] font-bold text-white border border-cyan-400/30"
              style={{
                boxShadow: '0 0 8px rgba(6, 182, 212, 0.6)',
              }}
            >
              {Math.round(progress)}%
            </motion.div>
          )}

          {/* Notification Badge (shown when complete) - Faiston magenta */}
          {showBadge && !isGenerating && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-[#151720] bg-[var(--faiston-magenta-mid,#C31B8C)]"
              style={{
                boxShadow: '0 0 8px rgba(195, 27, 140, 0.6)',
              }}
            >
              <motion.div
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.7, 1, 0.7],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                className="w-full h-full rounded-full bg-[var(--faiston-magenta-mid,#C31B8C)]"
              />
            </motion.div>
          )}
        </motion.button>
      </TooltipTrigger>
      <TooltipContent side="top" className="bg-black/90 text-white border-white/10">
        <p>
          {label}
          {isGenerating && <span className="ml-2 text-cyan-400">{Math.round(progress)}%</span>}
          {shortcut && !isGenerating && <span className="ml-2 text-white/50">({shortcut})</span>}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

export function ClassroomToolbar() {
  const router = useRouter();
  const {
    panels,
    togglePanelVisibility,
    resetLayout,
    courseId,
    audioReady,
    audioGenerating,
    audioProgress,
    extraclassReady,
    setExtraclassReady,
  } = useAcademyClassroom();

  const handleBack = () => {
    router.push(`/ferramentas/academy/cursos/${courseId}`);
  };

  return (
    <TooltipProvider>
      <div className="fixed bottom-6 left-0 right-0 z-[400] flex justify-center pointer-events-none">
        <motion.div
          initial={{ y: 60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300, delay: 0.3 }}
          className="glass-card rounded-full px-4 py-2 pointer-events-auto border border-white/10"
        >
          <div className="flex items-center gap-2">
            {/* Back Button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleBack}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/5 text-white/70 hover:bg-white/10 hover:text-white transition-all"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span className="hidden sm:inline text-sm">Voltar</span>
                </motion.button>
              </TooltipTrigger>
              <TooltipContent side="top" className="bg-black/90 text-white border-white/10">
                <p>Voltar ao curso</p>
              </TooltipContent>
            </Tooltip>

            {/* Separator */}
            <div className="w-px h-6 bg-white/20 mx-1" />

            {/* Panel Toggle Buttons */}
            <ToolbarButton
              icon={Video}
              label="Video"
              isActive={panels.video?.isVisible}
              onClick={() => togglePanelVisibility('video')}
              shortcut="1"
            />

            <ToolbarButton
              icon={FileText}
              label="Notas"
              isActive={panels.notes?.isVisible}
              onClick={() => togglePanelVisibility('notes')}
              shortcut="2"
            />

            <ToolbarButton
              icon={Sparkles}
              label="NEXO"
              isActive={panels.nexo?.isVisible}
              onClick={() => togglePanelVisibility('nexo')}
              shortcut="3"
              variant="gradient"
            />

            <ToolbarButton
              icon={Type}
              label="Transcricao"
              isActive={panels.transcription?.isVisible}
              onClick={() => togglePanelVisibility('transcription')}
              shortcut="4"
            />

            <ToolbarButton
              icon={Zap}
              label="Flashcards"
              isActive={panels.flashcards?.isVisible}
              onClick={() => togglePanelVisibility('flashcards')}
              shortcut="5"
            />

            <ToolbarButton
              icon={Network}
              label="Mind Map"
              isActive={panels.mindmap?.isVisible}
              onClick={() => togglePanelVisibility('mindmap')}
            />

            <ToolbarButton
              icon={Headphones}
              label="Audio Class"
              isActive={panels.audioclass?.isVisible}
              onClick={() => togglePanelVisibility('audioclass')}
              shortcut="6"
              showBadge={audioReady && !panels.audioclass?.isVisible}
              progress={audioGenerating && !panels.audioclass?.isVisible ? audioProgress : null}
            />

            <ToolbarButton
              icon={BookOpen}
              label="Biblioteca"
              isActive={panels.library?.isVisible}
              onClick={() => togglePanelVisibility('library')}
              shortcut="7"
            />

            <ToolbarButton
              icon={Presentation}
              label="Slide Deck"
              isActive={panels.slidedeck?.isVisible}
              onClick={() => togglePanelVisibility('slidedeck')}
              shortcut="8"
            />

            <ToolbarButton
              icon={GraduationCap}
              label="Aulas Extras"
              isActive={panels.extraclass?.isVisible}
              onClick={() => {
                if (!panels.extraclass?.isVisible && extraclassReady) {
                  setExtraclassReady(false);
                }
                togglePanelVisibility('extraclass');
              }}
              shortcut="9"
              variant="gradient"
              showBadge={extraclassReady && !panels.extraclass?.isVisible}
            />

            {/* Separator */}
            <div className="w-px h-6 bg-white/20 mx-1" />

            {/* Reset Layout */}
            <Tooltip>
              <TooltipTrigger asChild>
                <motion.button
                  whileHover={{ scale: 1.05, rotate: -30 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={resetLayout}
                  className="p-2 rounded-xl bg-white/5 text-white/50 hover:bg-white/10 hover:text-white transition-all"
                >
                  <RotateCcw className="w-4 h-4" />
                </motion.button>
              </TooltipTrigger>
              <TooltipContent side="top" className="bg-black/90 text-white border-white/10">
                <p>Resetar layout</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </motion.div>
      </div>
    </TooltipProvider>
  );
}
