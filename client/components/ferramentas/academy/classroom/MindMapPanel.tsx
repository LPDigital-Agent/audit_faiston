// =============================================================================
// Mind Map Panel - Faiston Academy
// =============================================================================
// AI-generated interactive mind map with video navigation.
// Click on leaf nodes with video icon to seek to that timestamp.
// =============================================================================

'use client';

import { useState, useEffect, useCallback, memo, startTransition } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Network,
  RefreshCw,
  RotateCcw,
  Expand,
  Minimize2,
  Video,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import { useMindMap, type MindMapNode } from '@/hooks/academy/useMindMap';

interface MindMapPanelProps {
  episodeId: string;
  episodeTitle: string;
  onSeek?: (time: number) => void;
  transcription?: string;
}

// Dynamic transcription path based on course and episode
function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

// Format timestamp to mm:ss
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Count descendants for badge display
function countDescendants(node: MindMapNode): number {
  if (!node.children || node.children.length === 0) return 0;
  return node.children.reduce((sum, child) => sum + 1 + countDescendants(child), 0);
}

// Tree Node Component (recursive)
interface TreeNodeProps {
  node: MindMapNode;
  level: number;
  isExpanded: boolean;
  expandedNodes: Set<string>;
  onToggle: (nodeId: string) => void;
  onSeek: (time: number) => void;
}

const TreeNode = memo(function TreeNode({
  node,
  level,
  isExpanded,
  expandedNodes,
  onToggle,
  onSeek,
}: TreeNodeProps) {
  const hasChildren = node.children && node.children.length > 0;
  const hasTimestamp = node.timestamp !== undefined;
  const isLeafNode = !hasChildren;
  const descendantCount = hasChildren ? countDescendants(node) : 0;

  // Faiston-themed styling based on node type and level
  const getNodeStyles = () => {
    // Leaf node with timestamp - interactive magenta theme
    if (isLeafNode && hasTimestamp) {
      return `
        bg-[var(--faiston-magenta-mid,#C31B8C)]/10 backdrop-blur-md
        border border-[var(--faiston-magenta-mid,#C31B8C)]/60
        text-pink-100
        shadow-[0_0_16px_rgba(195,27,140,0.25)]
        hover:bg-[var(--faiston-magenta-mid,#C31B8C)]/20 hover:border-[var(--faiston-magenta-mid,#C31B8C)]/80
        hover:shadow-[0_0_24px_rgba(195,27,140,0.4)]
        hover:translate-x-1
        cursor-pointer transition-all duration-200
        group
      `;
    }

    // Section nodes with children - level-based styling
    if (hasChildren) {
      if (level === 1) {
        return `
          bg-[var(--faiston-blue-mid,#2226C0)]/10 backdrop-blur-md
          border-l-[3px] border-l-[var(--faiston-blue-mid,#2226C0)] border border-[var(--faiston-blue-mid,#2226C0)]/50
          text-white
          shadow-[0_0_20px_rgba(34,38,192,0.2)]
          hover:bg-[var(--faiston-blue-mid,#2226C0)]/20 hover:border-[var(--faiston-blue-mid,#2226C0)]/70
          hover:shadow-[0_0_28px_rgba(34,38,192,0.35)]
          hover:translate-x-0.5
          cursor-pointer transition-all duration-200
        `;
      } else {
        return `
          bg-violet-950/70 backdrop-blur-md
          border-l-[3px] border-l-violet-400 border border-violet-400/50
          text-white
          shadow-[0_0_18px_rgba(139,92,246,0.2)]
          hover:bg-violet-900/80 hover:border-violet-300/70
          hover:shadow-[0_0_26px_rgba(139,92,246,0.35)]
          hover:translate-x-0.5
          cursor-pointer transition-all duration-200
        `;
      }
    }

    // Regular leaf node without timestamp
    return `
      bg-white/10 backdrop-blur-md
      border border-white/20
      text-white/80
      hover:bg-white/15 hover:border-white/30 hover:text-white
      transition-colors duration-150
    `;
  };

  const getChevronColor = () => {
    if (level === 1) return 'text-blue-300';
    return 'text-violet-300';
  };

  const handleClick = () => {
    if (isLeafNode && hasTimestamp) {
      onSeek(node.timestamp!);
    } else if (hasChildren) {
      onToggle(node.id);
    }
  };

  return (
    <div className="relative">
      {/* Neural pathway connection lines */}
      {level > 0 && (
        <>
          <div
            className="absolute w-0.5 bg-gradient-to-b from-[var(--faiston-blue-mid,#2226C0)]/30 to-violet-500/20"
            style={{
              left: `${(level - 1) * 24 + 12}px`,
              top: 0,
              height: '36px',
            }}
          />
          <div
            className={`absolute w-2 h-2 rounded-full ${
              level === 1
                ? 'bg-[var(--faiston-blue-mid,#2226C0)]/70'
                : 'bg-violet-500/60'
            } shadow-[0_0_8px_rgba(99,102,241,0.5)]`}
            style={{
              left: `${(level - 1) * 24 + 8}px`,
              top: '32px',
            }}
          />
        </>
      )}

      {/* Node row */}
      <motion.div
        initial={{ opacity: 0, x: -15, scale: 0.98 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        exit={{ opacity: 0, x: -15, scale: 0.98 }}
        transition={{
          duration: 0.2,
          ease: [0.4, 0, 0.2, 1],
          delay: level * 0.02,
        }}
        className="flex items-stretch"
        style={{ paddingLeft: `${level * 24}px` }}
      >
        {level > 0 && (
          <div className="w-6 flex items-center">
            <div className="w-full h-0.5 bg-gradient-to-r from-slate-400/30 to-slate-400/10" />
          </div>
        )}

        <div
          onClick={handleClick}
          className={`flex items-center gap-2.5 my-1 ${getNodeStyles()}`}
          style={{
            padding: hasChildren ? '10px 14px' : '8px 12px',
            borderRadius: hasChildren ? '8px' : '6px',
            maxWidth: 'fit-content',
          }}
        >
          {hasChildren && (
            <motion.div
              animate={{ rotate: isExpanded ? 90 : 0 }}
              transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              className="shrink-0"
            >
              <ChevronRight className={`w-4 h-4 ${getChevronColor()}`} />
            </motion.div>
          )}

          {isLeafNode && hasTimestamp && (
            <motion.div
              animate={{
                opacity: [0.7, 1, 0.7],
                scale: [1, 1.05, 1],
              }}
              transition={{
                duration: 2.5,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
              className="shrink-0"
            >
              <Video className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)] drop-shadow-[0_0_8px_rgba(195,27,140,0.5)] group-hover:scale-110 transition-transform" />
            </motion.div>
          )}

          {isLeafNode && !hasTimestamp && <div className="w-4" />}

          <span
            className={`flex-1 leading-snug ${
              hasChildren ? (level === 1 ? 'text-[13px] font-medium' : 'text-xs') : 'text-xs'
            }`}
          >
            {node.label}
          </span>

          {isLeafNode && hasTimestamp && (
            <motion.span
              whileHover={{ scale: 1.05, backgroundColor: 'rgba(195, 27, 140, 0.25)' }}
              transition={{ duration: 0.15 }}
              className="text-[10px] font-semibold text-pink-200 bg-[var(--faiston-magenta-mid,#C31B8C)]/30 px-2 py-0.5 rounded-full shrink-0"
            >
              {formatTime(node.timestamp!)}
            </motion.span>
          )}

          {hasChildren && !isExpanded && descendantCount > 0 && (
            <span
              className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0 ${
                level === 1
                  ? 'text-blue-200 bg-[var(--faiston-blue-mid,#2226C0)]/30'
                  : 'text-violet-200 bg-violet-500/30'
              }`}
            >
              {descendantCount}
            </span>
          )}
        </div>
      </motion.div>

      {/* Children with stagger animation */}
      <AnimatePresence initial={false}>
        {hasChildren && isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: 0.25,
              ease: [0.4, 0, 0.2, 1],
              opacity: { duration: 0.2 },
            }}
            className="overflow-hidden"
          >
            {node.children!.map((child) => (
              <TreeNode
                key={child.id}
                node={child}
                level={level + 1}
                isExpanded={expandedNodes.has(child.id)}
                expandedNodes={expandedNodes}
                onToggle={onToggle}
                onSeek={onSeek}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

// Root node wrapper with Faiston gradient
const RootNodeWrapper = memo(function RootNodeWrapper({
  title,
  nodes,
  expandedNodes,
  onToggle,
  onSeek,
}: {
  title: string;
  nodes: MindMapNode[];
  expandedNodes: Set<string>;
  onToggle: (nodeId: string) => void;
  onSeek: (time: number) => void;
}) {
  const isRootExpanded = expandedNodes.has('root');
  const totalNodes = nodes.reduce((sum, n) => sum + 1 + countDescendants(n), 0);

  return (
    <div className="p-4">
      {/* Root node with Faiston gradient */}
      <motion.div
        onClick={() => onToggle('root')}
        whileHover={{ scale: 1.005 }}
        whileTap={{ scale: 0.995 }}
        className="inline-flex items-center gap-3 px-4 py-3 rounded-[10px] cursor-pointer transition-all duration-200"
        style={{
          background:
            'linear-gradient(135deg, var(--faiston-magenta-mid,#C31B8C) 0%, var(--faiston-blue-mid,#2226C0) 100%)',
          boxShadow: '0 6px 24px rgba(195, 27, 140, 0.3), 0 0 40px rgba(34, 38, 192, 0.12)',
        }}
      >
        <motion.div
          animate={{ rotate: isRootExpanded ? 90 : 0 }}
          transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
        >
          <ChevronRight className="w-4 h-4 text-white/90" />
        </motion.div>
        <span className="flex-1 text-[14px] font-semibold text-white tracking-tight">{title}</span>
        {!isRootExpanded && (
          <span className="text-[11px] font-medium bg-white/20 text-white/90 px-2.5 py-0.5 rounded-full">
            {totalNodes} itens
          </span>
        )}
      </motion.div>

      {/* Top-level children */}
      <AnimatePresence initial={false}>
        {isRootExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden mt-3"
          >
            {nodes.map((node) => (
              <TreeNode
                key={node.id}
                node={node}
                level={1}
                isExpanded={expandedNodes.has(node.id)}
                expandedNodes={expandedNodes}
                onToggle={onToggle}
                onSeek={onSeek}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

// Main Mind Map Panel Component
export function MindMapPanel({ episodeId, episodeTitle, onSeek }: MindMapPanelProps) {
  const { courseId, panels, togglePanelVisibility } = useAcademyClassroom();
  const [transcription, setTranscription] = useState<string>('');
  const [loadingTranscription, setLoadingTranscription] = useState(false);

  // Handle seek AND auto-open video panel
  const handleSeekAndOpenVideo = useCallback(
    (time: number) => {
      const needsToOpenPanel = !panels.video?.isVisible;

      onSeek?.(time);

      if (needsToOpenPanel) {
        togglePanelVisibility('video');
      }
    },
    [panels.video?.isVisible, togglePanelVisibility, onSeek]
  );

  const {
    mindMapData,
    expandedNodes,
    generate,
    toggleNode,
    isGenerating,
    generateError,
    hasMindMap,
    expandAll,
    collapseAll,
    resetMindMap,
  } = useMindMap({
    courseId,
    episodeId,
    episodeTitle,
    onSeek: handleSeekAndOpenVideo,
  });

  // Load transcription when course/episode changes
  useEffect(() => {
    const url = getTranscriptionPath(courseId, episodeId);

    startTransition(() => {
      setLoadingTranscription(true);
    });
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load');
        return r.text();
      })
      .then((content) => {
        if (content.trim().startsWith('<!') || content.trim().startsWith('<html')) {
          console.warn('Transcription fetch returned HTML instead of text file');
          startTransition(() => {
            setTranscription('');
            setLoadingTranscription(false);
          });
          return;
        }
        startTransition(() => {
          setTranscription(content);
          setLoadingTranscription(false);
        });
      })
      .catch(() => {
        startTransition(() => {
          setLoadingTranscription(false);
        });
      });
  }, [courseId, episodeId]);

  const handleGenerate = () => {
    if (transcription) {
      generate(transcription);
    }
  };

  const handleReset = () => {
    resetMindMap();
  };

  // Settings view (no mind map yet)
  if (!hasMindMap) {
    return (
      <div className="h-full flex flex-col bg-black/20">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Network className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Mapa Mental</h3>
              <p className="text-xs text-white/40">Visualize os conceitos da aula</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
          <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-5">
            <Network className="w-10 h-10 text-white/30" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">Gerar Mapa Mental</h3>
          <p className="text-sm text-slate-400 mb-6 max-w-xs leading-relaxed">
            Crie um mapa mental interativo baseado no episodio estudado. Clique nos nos com icone de
            video para navegar.
          </p>

          {generateError && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm mb-4 max-w-xs">
              Erro ao gerar mapa mental. Tente novamente.
            </div>
          )}

          <Button
            onClick={handleGenerate}
            disabled={isGenerating || loadingTranscription || !transcription}
            className="bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white border-0 shadow-lg shadow-[var(--faiston-magenta-mid,#C31B8C)]/20 transition-all font-semibold rounded-xl"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                Gerando...
              </>
            ) : (
              <>
                <Network className="w-4 h-4 mr-2" />
                Gerar Mapa Mental
              </>
            )}
          </Button>

          {loadingTranscription && (
            <p className="text-xs text-white/40 text-center mt-3">Carregando transcricao...</p>
          )}
        </div>
      </div>
    );
  }

  // Mind map tree view
  return (
    <div className="h-full flex flex-col bg-black/20">
      {/* Header with controls */}
      <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
            <Network className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </div>
          <span className="text-base font-medium text-white">Mapa Mental</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={expandAll}
            className="p-2 rounded-md bg-white/5 hover:bg-white/10 transition-colors"
            title="Expandir tudo"
          >
            <Expand className="w-4 h-4 text-white/40 hover:text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </button>
          <button
            onClick={collapseAll}
            className="p-2 rounded-md bg-white/5 hover:bg-white/10 transition-colors"
            title="Recolher tudo"
          >
            <Minimize2 className="w-4 h-4 text-white/40 hover:text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </button>
          <button
            onClick={handleReset}
            className="p-2 rounded-md bg-white/5 hover:bg-white/10 transition-colors"
            title="Gerar novo"
          >
            <RotateCcw className="w-4 h-4 text-white/40 hover:text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </button>
        </div>
      </div>

      {/* Scrollable tree view */}
      <div className="flex-1 overflow-auto">
        {mindMapData && (
          <RootNodeWrapper
            title={mindMapData.title}
            nodes={mindMapData.nodes}
            expandedNodes={expandedNodes}
            onToggle={toggleNode}
            onSeek={handleSeekAndOpenVideo}
          />
        )}
      </div>

      {/* Footer hint */}
      <div className="px-6 py-3 border-t border-white/5">
        <div className="flex items-center justify-center gap-2 text-xs text-white/40">
          <span>Clique nos nos com</span>
          <Video className="w-3.5 h-3.5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          <span>para navegar no video</span>
        </div>
      </div>
    </div>
  );
}
