'use client';

import { useEffect } from 'react';

interface ToastProps {
  message: string;
  type: 'success' | 'error';
  onDismiss: () => void;
}

// Auto-dismiss timer starts once on mount; does not reset if onDismiss reference changes.
export default function Toast({ message, type, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3000);
    return () => clearTimeout(timer);
    // Intentionally omit onDismiss from deps — timer should fire once after 3s, not restart on re-render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={`fixed bottom-4 right-4 z-50 flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg transition-all ${
        type === 'success' ? 'bg-green-600' : 'bg-red-600'
      }`}
    >
      <span>
        {type === 'success' ? '✓' : '✕'}
      </span>
      <span>{message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="ml-2 rounded p-0.5 text-white/80 hover:text-white focus:outline-none focus:ring-2 focus:ring-white/50"
      >
        ✕
      </button>
    </div>
  );
}
