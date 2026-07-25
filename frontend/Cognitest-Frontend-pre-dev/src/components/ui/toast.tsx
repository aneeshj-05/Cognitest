import React, { createContext, useContext, useState, useCallback } from 'react';
import { X, AlertCircle } from 'lucide-react';

interface ToastOptions {
  title: string;
  description: string;
  /** "error" | "success" | "info" | "warning" */
  type?: 'error' | 'success' | 'info' | 'warning';
  /** duration in ms, default 6000 */
  duration?: number;
}

interface Toast extends ToastOptions {
  id: number;
}

interface ToastContextValue {
  show: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextIdRef = React.useRef(0);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((options: ToastOptions) => {
    const id = nextIdRef.current++;
    const toast: Toast = {
      id,
      title: options.title,
      description: options.description,
      type: options.type ?? 'error',
      duration: options.duration ?? 6000,
    };
    setToasts((prev) => [...prev, toast]);
    setTimeout(() => removeToast(id), toast.duration);
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`relative rounded-xl border p-5 shadow-2xl shadow-[0_4px_6px_rgba(0,0,0,0.4)] animate-in fade-in-0 zoom-in-95 transition-all
              ${t.type === 'error' ? 'bg-destructive border-destructive/30 text-destructive-foreground border-l-4 border-destructive' : ''}
              ${t.type === 'success' ? 'bg-primary/10 border-primary/30 text-primary-foreground' : ''}
              ${t.type === 'info' ? 'bg-primary/10 border-primary/30 text-primary-foreground' : ''}
              ${t.type === 'warning' ? 'bg-secondary/10 border-secondary/30 text-secondary-foreground' : ''}
            `}
          >
            <div className="flex items-start gap-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/25">
                <AlertCircle className="h-4 w-4 text-white" />
              </div>
              <div className="flex-1">
                <p className="font-semibold">{t.title}</p>
                <p className="text-sm opacity-90 leading-5 mt-0.5 whitespace-pre-wrap break-words">{t.description}</p>
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="inline-flex h-5 w-5 items-center justify-center rounded-full opacity-70 hover:opacity-100 hover:bg-white/15 transition-colors"
                aria-label="Close"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): { show: (options: ToastOptions) => void } => {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
};
