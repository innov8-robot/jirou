import { toast as sonnerToast } from 'sonner';

/**
 * Thin, app-wide toast helper on top of `sonner`. Import this instead of
 * calling `sonner` directly so notification styling/behavior stays in one
 * place. The <Toaster /> host is mounted at the app root (see App.tsx).
 *
 * Usage:
 *   import { toast } from '@/lib/toast';
 *   toast.success('Projet créé');
 *   toast.error('Impossible de charger les tickets');
 */
export const toast = {
  success: (message: string, description?: string) =>
    sonnerToast.success(message, { description }),

  error: (message: string, description?: string) =>
    sonnerToast.error(message, { description }),

  info: (message: string, description?: string) =>
    sonnerToast.info(message, { description }),

  /** Toast tied to a promise's lifecycle (loading → success / error). */
  promise: sonnerToast.promise,

  /** Escape hatch for advanced/custom toasts. */
  raw: sonnerToast,
};

/**
 * Extracts a human-readable message from an unknown error (Axios error,
 * Error instance, or anything). Handy for generic API error toasts:
 *   catch (e) { toast.error('Échec', getErrorMessage(e)); }
 */
export function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const anyErr = error as {
      response?: { data?: { detail?: unknown } };
      message?: string;
    };
    const detail = anyErr.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (typeof anyErr.message === 'string') return anyErr.message;
  }
  return 'Une erreur inattendue est survenue.';
}
