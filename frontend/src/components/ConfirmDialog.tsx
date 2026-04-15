import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'danger' | 'warning' | 'info';
}

export default function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'danger'
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  const variantStyles = {
    danger: 'bg-error text-white hover:bg-error/90',
    warning: 'bg-amber-500 text-white hover:bg-amber-600',
    info: 'bg-primary text-white hover:bg-primary-dim'
  };

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onCancel}
        className="absolute inset-0 bg-on-background/40 backdrop-blur-sm"
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative bg-background w-full max-w-md rounded-sm shadow-2xl overflow-hidden"
      >
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={`p-2 rounded-full ${variant === 'danger' ? 'bg-error/10 text-error' : 'bg-primary/10 text-primary'}`}>
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-headline font-bold text-on-background mb-2">{title}</h3>
              <p className="text-sm text-secondary leading-relaxed">{message}</p>
            </div>
            <button 
              onClick={onCancel}
              className="text-outline-variant hover:text-on-background transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        <div className="px-6 py-4 bg-surface-container-low flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-sm font-label text-xs font-bold uppercase tracking-widest text-secondary hover:text-on-background transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-6 py-2 rounded-sm font-label text-xs font-bold uppercase tracking-widest transition-all shadow-md ${variantStyles[variant]}`}
          >
            {confirmLabel}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
