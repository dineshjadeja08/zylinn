import { useState, useCallback } from 'react';

interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

let listeners: Array<(toasts: Toast[]) => void> = [];
let toasts: Toast[] = [];

function addToast(toast: Omit<Toast, 'id'>) {
  const id = Math.random().toString(36).slice(2);
  toasts = [...toasts, { ...toast, id }];
  listeners.forEach(l => l(toasts));
  setTimeout(() => { toasts = toasts.filter(t => t.id !== id); listeners.forEach(l => l(toasts)); }, 4000);
}

export function toast(toast: Omit<Toast, 'id'>) { addToast(toast); }

export function useToast() {
  const [state, setState] = useState<Toast[]>(toasts);
  listeners.push(setState);
  return { toasts: state, toast };
}
