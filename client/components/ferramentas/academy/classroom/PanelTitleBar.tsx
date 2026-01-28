// =============================================================================
// Panel Title Bar - Faiston Academy
// =============================================================================
// macOS-style title bar for floating panels with traffic light controls.
// =============================================================================

'use client';

import { LucideIcon, GripHorizontal } from 'lucide-react';
import { motion } from 'framer-motion';

interface PanelTitleBarProps {
  title: string;
  icon: LucideIcon;
  onStartDrag: (event: React.PointerEvent) => void;
  onClose?: () => void;
  onMinimize: () => void;
  onMaximize: () => void;
  canClose?: boolean;
  isMinimized?: boolean;
  isMaximized?: boolean;
  isDragging?: boolean;
}

export function PanelTitleBar({
  title,
  icon: Icon,
  onStartDrag,
  onClose,
  onMinimize,
  onMaximize,
  canClose = true,
  isMinimized = false,
  isMaximized = false,
  isDragging = false,
}: PanelTitleBarProps) {
  return (
    <div
      className="h-11 flex items-center justify-between px-3 bg-white/5 border-b border-white/10 select-none"
      style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      onPointerDown={onStartDrag}
    >
      {/* Left side: Window controls (macOS style) */}
      <div
        className="flex items-center gap-2"
        onPointerDown={(e) => e.stopPropagation()}
      >
        {/* Close button - Red */}
        {canClose ? (
          <motion.button
            whileHover={{ scale: 1.15 }}
            whileTap={{ scale: 0.9 }}
            onClick={onClose}
            className="w-3 h-3 rounded-full bg-[#FF5F57] hover:bg-[#FF3B30] transition-colors group relative"
            title="Fechar"
          >
            <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 text-[8px] text-black/70 font-bold">
              ×
            </span>
          </motion.button>
        ) : (
          <div className="w-3 h-3 rounded-full bg-white/20" />
        )}

        {/* Minimize button - Yellow */}
        <motion.button
          whileHover={{ scale: 1.15 }}
          whileTap={{ scale: 0.9 }}
          onClick={onMinimize}
          className="w-3 h-3 rounded-full bg-[#FFBD2E] hover:bg-[#FFCC00] transition-colors group relative"
          title={isMinimized ? 'Restaurar' : 'Minimizar'}
        >
          <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 text-[8px] text-black/70 font-bold">
            −
          </span>
        </motion.button>

        {/* Maximize button - Green */}
        <motion.button
          whileHover={{ scale: 1.15 }}
          whileTap={{ scale: 0.9 }}
          onClick={onMaximize}
          className="w-3 h-3 rounded-full bg-[#28CA41] hover:bg-[#34C759] transition-colors group relative"
          title={isMaximized ? 'Restaurar' : 'Maximizar'}
        >
          <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 text-[8px] text-black/70 font-bold">
            +
          </span>
        </motion.button>
      </div>

      {/* Center: Title with icon - Faiston magenta theme */}
      <div className="flex items-center gap-2 flex-1 justify-center pointer-events-none">
        <Icon className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
        <span className="text-sm font-medium text-white/90 truncate">{title}</span>
      </div>

      {/* Right side: Drag indicator */}
      <div className="flex items-center">
        <GripHorizontal className="w-4 h-4 text-white/30" />
      </div>
    </div>
  );
}
