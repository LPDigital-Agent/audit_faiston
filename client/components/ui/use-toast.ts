// =============================================================================
// Toast Hook - Minimal Implementation
// =============================================================================
// Provides a minimal toast notification API.
// Based on shadcn/ui toast pattern but simplified for this project.
// =============================================================================

'use client';

import { useState } from 'react';

export interface ToastProps {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
  duration?: number;
  className?: string;
}

export interface ToastOptions {
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
  duration?: number;
  className?: string;
}

let toastCount = 0;

function genId() {
  toastCount = (toastCount + 1) % Number.MAX_VALUE;
  return toastCount.toString();
}

// Global toast state (simple implementation)
const toastListeners: Set<(toasts: ToastProps[]) => void> = new Set();
let toastState: ToastProps[] = [];

function dispatch(toasts: ToastProps[]) {
  toastState = toasts;
  toastListeners.forEach((listener) => listener(toasts));
}

export function toast(options: ToastOptions) {
  const id = genId();
  const duration = options.duration ?? 5000;

  const newToast: ToastProps = {
    id,
    ...options,
  };

  dispatch([...toastState, newToast]);

  // Auto-dismiss
  if (duration > 0) {
    setTimeout(() => {
      dismiss(id);
    }, duration);
  }

  return {
    id,
    dismiss: () => dismiss(id),
  };
}

export function dismiss(toastId?: string) {
  if (toastId) {
    dispatch(toastState.filter((t) => t.id !== toastId));
  } else {
    dispatch([]);
  }
}

export function useToast() {
  const [toasts, setToasts] = useState<ToastProps[]>(toastState);

  useState(() => {
    const listener = (newToasts: ToastProps[]) => setToasts(newToasts);
    toastListeners.add(listener);
    return () => {
      toastListeners.delete(listener);
    };
  });

  return {
    toasts,
    toast,
    dismiss,
  };
}
