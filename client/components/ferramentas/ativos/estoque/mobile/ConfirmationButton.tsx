'use client';

// =============================================================================
// Confirmation Button - SGA Inventory PWA Component
// =============================================================================
// Hold-to-confirm button for critical actions to prevent accidental taps.
// Provides visual feedback and requires deliberate user action.
// =============================================================================

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Loader2 } from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface ConfirmationButtonProps {
  onConfirm: () => void | Promise<void>;
  holdDuration?: number; // Duration in ms to hold for confirmation
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
  variant?: 'default' | 'destructive' | 'success';
  size?: 'sm' | 'md' | 'lg';
}

// =============================================================================
// Component
// =============================================================================

export function ConfirmationButton({
  onConfirm,
  holdDuration = 1500,
  children,
  className = '',
  disabled = false,
  variant = 'default',
  size = 'md',
}: ConfirmationButtonProps) {
  const [isHolding, setIsHolding] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const holdStartRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const confirmedRef = useRef(false);

  // Get variant colors
  const getVariantColors = () => {
    switch (variant) {
      case 'destructive':
        return {
          bg: 'bg-red-500/20',
          border: 'border-red-500/30',
          progressBg: 'bg-red-500',
          text: 'text-red-400',
          ring: 'ring-red-500/30',
        };
      case 'success':
        return {
          bg: 'bg-green-500/20',
          border: 'border-green-500/30',
          progressBg: 'bg-green-500',
          text: 'text-green-400',
          ring: 'ring-green-500/30',
        };
      default:
        return {
          bg: 'bg-magenta-mid/20',
          border: 'border-magenta-mid/30',
          progressBg: 'bg-gradient-to-r from-magenta-mid to-blue-mid',
          text: 'text-magenta-mid',
          ring: 'ring-magenta-mid/30',
        };
    }
  };

  // Get size classes
  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'h-10 px-4 text-sm';
      case 'lg':
        return 'h-14 px-8 text-lg';
      default:
        return 'h-12 px-6 text-base';
    }
  };

  const colors = getVariantColors();
  const sizeClasses = getSizeClasses();

  // Update progress
  const updateProgress = useCallback(() => {
    if (!holdStartRef.current) return;

    const elapsed = Date.now() - holdStartRef.current;
    const newProgress = Math.min((elapsed / holdDuration) * 100, 100);

    setProgress(newProgress);

    if (newProgress >= 100 && !confirmedRef.current) {
      confirmedRef.current = true;
      setIsConfirmed(true);
      setIsHolding(false);

      // Trigger confirmation
      (async () => {
        setIsLoading(true);
        try {
          await onConfirm();
        } finally {
          setIsLoading(false);
          setTimeout(() => {
            setIsConfirmed(false);
            setProgress(0);
            confirmedRef.current = false;
          }, 1000);
        }
      })();
    } else if (newProgress < 100) {
      animationFrameRef.current = requestAnimationFrame(updateProgress);
    }
  }, [holdDuration, onConfirm]);

  // Start holding
  const handleStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      if (disabled || isLoading || isConfirmed) return;

      e.preventDefault();
      holdStartRef.current = Date.now();
      confirmedRef.current = false;
      setIsHolding(true);
      setProgress(0);
      animationFrameRef.current = requestAnimationFrame(updateProgress);
    },
    [disabled, isLoading, isConfirmed, updateProgress]
  );

  // Stop holding
  const handleEnd = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    holdStartRef.current = null;
    setIsHolding(false);

    // Reset if not confirmed
    if (!confirmedRef.current) {
      setProgress(0);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  return (
    <motion.button
      className={`
        relative overflow-hidden rounded-xl font-medium
        border transition-all select-none
        ${sizeClasses}
        ${colors.bg} ${colors.border} ${colors.text}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${isHolding ? `ring-4 ${colors.ring}` : ''}
        ${className}
      `}
      onMouseDown={handleStart}
      onMouseUp={handleEnd}
      onMouseLeave={handleEnd}
      onTouchStart={handleStart}
      onTouchEnd={handleEnd}
      disabled={disabled || isLoading || isConfirmed}
      whileTap={{ scale: disabled ? 1 : 0.98 }}
    >
      {/* Progress Background */}
      <motion.div
        className={`absolute inset-0 ${colors.progressBg} opacity-30`}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: progress / 100 }}
        style={{ transformOrigin: 'left' }}
        transition={{ duration: 0.05 }}
      />

      {/* Content */}
      <div className="relative z-10 flex items-center justify-center gap-2">
        {isLoading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Processando...</span>
          </>
        ) : isConfirmed ? (
          <>
            <CheckCircle2 className="w-5 h-5" />
            <span>Confirmado!</span>
          </>
        ) : isHolding ? (
          <>
            <motion.div
              className="w-5 h-5 rounded-full border-2 border-current"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            <span>Segure...</span>
          </>
        ) : (
          children
        )}
      </div>

      {/* Hold instruction */}
      {!isHolding && !isConfirmed && !isLoading && (
        <div className="absolute bottom-1 left-0 right-0 text-center">
          <span className="text-[10px] opacity-60">
            Segure para confirmar
          </span>
        </div>
      )}
    </motion.button>
  );
}
