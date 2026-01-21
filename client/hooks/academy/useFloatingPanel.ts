// =============================================================================
// useFloatingPanel Hook - Faiston Academy
// =============================================================================
// Hook for managing floating panel behavior in the classroom UI.
// Handles dragging, resizing, and z-index management for floating panels.
//
// Uses Framer Motion for smooth drag animations and motion values.
// Supports 8-direction resize (corners and edges).
// =============================================================================

'use client';

import { useCallback, useRef, useState, useEffect } from 'react';
import { useDragControls, useMotionValue } from 'framer-motion';
import {
  useAcademyClassroom,
  PANEL_MIN_SIZES,
} from '@/contexts/AcademyClassroomContext';
import type { ClassroomPanelId } from '@/lib/academy/constants';

interface UseFloatingPanelProps {
  panelId: ClassroomPanelId;
}

type ResizeDirection = 'se' | 'sw' | 'ne' | 'nw' | 'n' | 's' | 'e' | 'w';

// Define the workspace bounds (the area where students can drag panels)
const WORKSPACE_BOUNDS = {
  top: 0,
  left: 0,
  right: 0, // Will be calculated dynamically
  bottom: 80, // Space for bottom toolbar
};

export function useFloatingPanel({ panelId }: UseFloatingPanelProps) {
  const {
    panels,
    updatePanelPosition,
    updatePanelSize,
    bringToFront,
  } = useAcademyClassroom();

  const panel = panels[panelId];
  const dragControls = useDragControls();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // Motion values for coordinated drag - these sync Framer's internal state with our position
  const motionX = useMotionValue(0);
  const motionY = useMotionValue(0);

  // Store initial resize state
  const resizeStartRef = useRef<{
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
    startPosX: number;
    startPosY: number;
    direction: ResizeDirection;
  } | null>(null);

  // Handle drag start from title bar
  const startDrag = useCallback(
    (event: React.PointerEvent) => {
      if (panel.isMaximized) return; // Don't allow drag when maximized
      bringToFront(panelId);
      setIsDragging(true);
      dragControls.start(event);
    },
    [dragControls, bringToFront, panelId, panel.isMaximized]
  );

  // Handle drag end - constrain to viewport and RESET motion values
  const onDragEnd = useCallback(
    (
      _event: unknown,
      info: { point: { x: number; y: number }; offset: { x: number; y: number } }
    ) => {
      setIsDragging(false);

      // info.offset contains how much the element moved from its starting position
      let newX = panel.position.x + info.offset.x;
      let newY = panel.position.y + info.offset.y;

      // Get viewport dimensions
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Panel dimensions
      const panelWidth = panel.size.width;
      const panelHeight = panel.isMinimized ? 44 : panel.size.height;
      const toolbarHeight = WORKSPACE_BOUNDS.bottom;

      // Constrain to viewport bounds - keep panel FULLY inside the workspace
      // Left bound: panel can't go past left edge
      newX = Math.max(WORKSPACE_BOUNDS.left, newX);
      // Right bound: panel right edge can't exceed viewport
      newX = Math.min(viewportWidth - panelWidth, newX);
      // Top bound: keep panel below top edge
      newY = Math.max(WORKSPACE_BOUNDS.top, newY);
      // Bottom bound: panel bottom must stay above toolbar
      newY = Math.min(viewportHeight - toolbarHeight - panelHeight, newY);

      // CRITICAL: Reset motion values to 0 BEFORE updating position
      // This prevents the "jump" by clearing Framer Motion's internal transform offset
      motionX.set(0);
      motionY.set(0);

      updatePanelPosition(panelId, { x: newX, y: newY });
    },
    [
      panelId,
      panel.position,
      panel.size,
      panel.isMinimized,
      updatePanelPosition,
      motionX,
      motionY,
    ]
  );

  // Handle resize start
  const startResize = useCallback(
    (
      event: React.PointerEvent | React.MouseEvent,
      direction: ResizeDirection
    ) => {
      if (panel.isMaximized) return; // Don't allow resize when maximized
      event.preventDefault();
      event.stopPropagation();
      bringToFront(panelId);
      setIsResizing(true);

      resizeStartRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        startWidth: panel.size.width,
        startHeight: panel.size.height,
        startPosX: panel.position.x,
        startPosY: panel.position.y,
        direction,
      };

      // Add global event listeners
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
      document.addEventListener('touchmove', handleResizeTouchMove);
      document.addEventListener('touchend', handleResizeEnd);
    },
    [panelId, panel, bringToFront]
  );

  const handleResizeMove = useCallback(
    (event: MouseEvent) => {
      if (!resizeStartRef.current) return;

      const {
        startX,
        startY,
        startWidth,
        startHeight,
        startPosX,
        startPosY,
        direction,
      } = resizeStartRef.current;
      const minSize = PANEL_MIN_SIZES[panelId] || { width: 200, height: 150 };

      const deltaX = event.clientX - startX;
      const deltaY = event.clientY - startY;

      let newWidth = startWidth;
      let newHeight = startHeight;
      let newPosX = startPosX;
      let newPosY = startPosY;

      // Handle each direction
      if (direction.includes('e')) {
        newWidth = Math.max(minSize.width, startWidth + deltaX);
      }
      if (direction.includes('w')) {
        const widthDelta = Math.min(deltaX, startWidth - minSize.width);
        newWidth = startWidth - widthDelta;
        newPosX = startPosX + widthDelta;
      }
      if (direction.includes('s')) {
        newHeight = Math.max(minSize.height, startHeight + deltaY);
      }
      if (direction.includes('n')) {
        const heightDelta = Math.min(deltaY, startHeight - minSize.height);
        newHeight = startHeight - heightDelta;
        newPosY = startPosY + heightDelta;
      }

      updatePanelSize(panelId, { width: newWidth, height: newHeight });
      updatePanelPosition(panelId, { x: newPosX, y: newPosY });
    },
    [panelId, updatePanelSize, updatePanelPosition]
  );

  const handleResizeTouchMove = useCallback(
    (event: TouchEvent) => {
      if (!resizeStartRef.current || !event.touches[0]) return;
      const touch = event.touches[0];
      handleResizeMove({
        clientX: touch.clientX,
        clientY: touch.clientY,
      } as MouseEvent);
    },
    [handleResizeMove]
  );

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
    resizeStartRef.current = null;
    document.removeEventListener('mousemove', handleResizeMove);
    document.removeEventListener('mouseup', handleResizeEnd);
    document.removeEventListener('touchmove', handleResizeTouchMove);
    document.removeEventListener('touchend', handleResizeEnd);
  }, [handleResizeMove, handleResizeTouchMove]);

  // Clean up event listeners on unmount
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
      document.removeEventListener('touchmove', handleResizeTouchMove);
      document.removeEventListener('touchend', handleResizeEnd);
    };
  }, [handleResizeMove, handleResizeEnd, handleResizeTouchMove]);

  // Click handler to bring to front
  const handlePanelClick = useCallback(() => {
    bringToFront(panelId);
  }, [bringToFront, panelId]);

  // Calculate drag constraints dynamically (keeps panel inside viewport during drag)
  const getDragConstraints = useCallback(() => {
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const panelWidth = panel.size.width;
    const panelHeight = panel.isMinimized ? 44 : panel.size.height;

    return {
      top: -panel.position.y + WORKSPACE_BOUNDS.top,
      left: -panel.position.x + WORKSPACE_BOUNDS.left,
      right: viewportWidth - panel.position.x - panelWidth,
      bottom:
        viewportHeight -
        WORKSPACE_BOUNDS.bottom -
        panel.position.y -
        panelHeight,
    };
  }, [panel.position, panel.size, panel.isMinimized]);

  return {
    panel,
    dragControls,
    containerRef,
    isResizing,
    isDragging,
    startDrag,
    onDragEnd,
    startResize,
    handlePanelClick,
    // Motion values for coordinated drag
    motionX,
    motionY,
    getDragConstraints,
  };
}

// Re-export ResizeDirection type for components
export type { ResizeDirection };
