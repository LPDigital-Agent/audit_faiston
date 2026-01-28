'use client';

// =============================================================================
// Toaster Component - Global Toast Notifications
// =============================================================================
// Renders toast notifications from use-toast.ts hook.
// Uses Framer Motion for smooth animations and follows Faiston design system.
// =============================================================================

import { useEffect, useState, startTransition } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useToast, type ToastProps } from './use-toast';

/**
 * Individual toast notification component.
 */
function Toast({ toast, onDismiss }: { toast: ToastProps; onDismiss: () => void }) {
  const isDestructive = toast.variant === 'destructive';

  return (
    <motion.div
      key={toast.id}
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.95 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`
        min-w-[320px] max-w-[420px] p-4 rounded-xl shadow-2xl
        backdrop-blur-xl border
        ${toast.className ? toast.className : isDestructive
          ? 'bg-red-500/15 border-red-500/30 shadow-red-500/20'
          : 'bg-surface-elevated/90 border-white/10 shadow-cyan-500/10'}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        {isDestructive ? (
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
        ) : (
          <CheckCircle2 className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          {toast.title && (
            <p className={`font-medium ${isDestructive ? 'text-red-100' : 'text-white'}`}>
              {toast.title}
            </p>
          )}
          {toast.description && (
            <p className={`text-sm mt-1 ${isDestructive ? 'text-red-200/80' : 'text-white/70'}`}>
              {toast.description}
            </p>
          )}
        </div>

        {/* Dismiss button */}
        <button
          onClick={onDismiss}
          className={`
            p-1 rounded-lg transition-colors shrink-0
            ${isDestructive
              ? 'text-red-300/60 hover:text-red-200 hover:bg-red-500/20'
              : 'text-white/40 hover:text-white hover:bg-white/10'}
          `}
          aria-label="Fechar notificacao"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
}

/**
 * Global Toaster component.
 * Renders all active toasts in a fixed position at bottom-right.
 */
export function Toaster() {
  const { toasts, dismiss } = useToast();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => {
    startTransition(() => {
      setMounted(true);
    });
  }, []);

  if (!mounted) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[100] flex flex-col gap-3 pointer-events-none"
      aria-live="polite"
      aria-label="Notificacoes"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <Toast toast={toast} onDismiss={() => dismiss(toast.id)} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export default Toaster;
