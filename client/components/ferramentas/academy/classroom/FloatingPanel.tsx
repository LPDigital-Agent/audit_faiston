// =============================================================================
// Floating Panel - Faiston Academy
// =============================================================================
// Draggable, resizable floating panel component for the classroom interface.
// Uses Framer Motion for smooth animations and drag interactions.
// =============================================================================

'use client';

import { ReactNode, useRef } from 'react';
import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';
import { useFloatingPanel } from '@/hooks/academy/useFloatingPanel';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import { PanelTitleBar } from './PanelTitleBar';
import type { ClassroomPanelId } from '@/lib/academy/constants';
import type { ResizeDirection } from '@/hooks/academy/useFloatingPanel';

// =============================================================================
// Resize Handle Component (extracted for React 19 compiler compliance)
// =============================================================================
interface ResizeHandleProps {
  position: string;
  cursor: string;
  direction: ResizeDirection;
  onResize: (
    event: React.PointerEvent | React.MouseEvent,
    direction: ResizeDirection
  ) => void;
}

function ResizeHandle({ position, cursor, direction, onResize }: ResizeHandleProps) {
  return (
    <div
      className={`absolute ${position} opacity-0 hover:opacity-100 transition-opacity z-10`}
      style={{ cursor }}
      onMouseDown={(e) => onResize(e, direction)}
      onTouchStart={(e) => {
        const touch = e.touches[0];
        onResize(
          {
            clientX: touch.clientX,
            clientY: touch.clientY,
            preventDefault: () => {},
            stopPropagation: () => {},
          } as React.MouseEvent,
          direction
        );
      }}
    >
      <div
        className={`${
          ['n', 's'].includes(direction)
            ? 'w-8 h-2'
            : ['e', 'w'].includes(direction)
              ? 'w-2 h-8'
              : 'w-3 h-3'
        } bg-white/20 rounded-full`}
      />
    </div>
  );
}

// =============================================================================
// Floating Panel Component
// =============================================================================
interface FloatingPanelProps {
  id: ClassroomPanelId;
  title: string;
  icon: LucideIcon;
  children: ReactNode;
  canClose?: boolean;
  canResize?: boolean;
}

export function FloatingPanel({
  id,
  title,
  icon,
  children,
  canClose = true,
  canResize = true,
}: FloatingPanelProps) {
  const { togglePanelVisibility, minimizePanel, maximizePanel } = useAcademyClassroom();
  const {
    panel,
    dragControls,
    isDragging,
    startDrag,
    onDragEnd,
    startResize,
    handlePanelClick,
    motionX,
    motionY,
    getDragConstraints,
  } = useFloatingPanel({ panelId: id });

  const containerRef = useRef<HTMLDivElement>(null);

  if (!panel.isVisible) return null;

  const handleClose = canClose ? () => togglePanelVisibility(id) : undefined;
  const handleMinimize = () => minimizePanel(id);
  const handleMaximize = () => maximizePanel(id);

  return (
    <motion.div
      ref={containerRef}
      key={`floating-panel-${id}`}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{
        opacity: 1,
        scale: 1,
        width: panel.size.width,
        height: panel.isMinimized ? 44 : panel.size.height,
      }}
      transition={{
        type: 'spring',
        damping: 25,
        stiffness: 300,
      }}
      drag
      dragListener={false}
      dragControls={dragControls}
      dragMomentum={false}
      dragElastic={0}
      dragConstraints={getDragConstraints()}
      onDragEnd={onDragEnd}
      style={{
        x: motionX,
        y: motionY,
        left: panel.position.x,
        top: panel.position.y,
        width: panel.size.width,
        height: panel.isMinimized ? 44 : panel.size.height,
        zIndex: panel.zIndex,
        boxShadow: isDragging
          ? '0 20px 60px rgba(0,0,0,0.4)'
          : '0 8px 32px rgba(0,0,0,0.25)',
      }}
      whileDrag={{
        scale: 1.02,
        boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}
      onClick={handlePanelClick}
      className="fixed glass-card rounded-2xl overflow-hidden flex flex-col border border-white/10"
    >
      {/* Title Bar */}
      <PanelTitleBar
        title={title}
        icon={icon}
        onStartDrag={startDrag}
        onClose={handleClose}
        onMinimize={handleMinimize}
        onMaximize={handleMaximize}
        canClose={canClose}
        isMinimized={panel.isMinimized}
        isMaximized={panel.isMaximized}
        isDragging={isDragging}
      />

      {/* Content - hidden when minimized */}
      {!panel.isMinimized && <div className="flex-1 overflow-hidden">{children}</div>}

      {/* Resize Handles - hidden when minimized, maximized, or canResize is false */}
      {!panel.isMinimized && !panel.isMaximized && canResize && (
        <>
          {/* Corner handles */}
          <ResizeHandle position="bottom-0 right-0 p-1" cursor="se-resize" direction="se" onResize={startResize} />
          <ResizeHandle position="bottom-0 left-0 p-1" cursor="sw-resize" direction="sw" onResize={startResize} />
          <ResizeHandle position="top-11 right-0 p-1" cursor="ne-resize" direction="ne" onResize={startResize} />
          <ResizeHandle position="top-11 left-0 p-1" cursor="nw-resize" direction="nw" onResize={startResize} />

          {/* Edge handles */}
          <ResizeHandle
            position="bottom-0 left-1/2 -translate-x-1/2 pb-0.5"
            cursor="s-resize"
            direction="s"
            onResize={startResize}
          />
          <ResizeHandle
            position="top-14 left-1/2 -translate-x-1/2 pt-0.5"
            cursor="n-resize"
            direction="n"
            onResize={startResize}
          />
          <ResizeHandle
            position="right-0 top-1/2 -translate-y-1/2 pr-0.5"
            cursor="e-resize"
            direction="e"
            onResize={startResize}
          />
          <ResizeHandle
            position="left-0 top-1/2 -translate-y-1/2 pl-0.5"
            cursor="w-resize"
            direction="w"
            onResize={startResize}
          />
        </>
      )}
    </motion.div>
  );
}
