import { Component, type ErrorInfo, type ReactNode } from 'react';

import { ErrorState } from '@/components/ErrorState';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Custom fallback; receives a reset callback to attempt recovery. */
  fallback?: (reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Top-level React error boundary. Catches render errors anywhere in the
 * tree and shows a recoverable {@link ErrorState} instead of a blank page.
 * (React error boundaries must be class components.)
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Real error reporting (Sentry…) can be wired here later.
    console.error('ErrorBoundary caught an error:', error, info);
  }

  reset = (): void => {
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback(this.reset);
      return (
        <div className="flex min-h-[60vh] items-center justify-center p-6">
          <ErrorState
            title="Oups, quelque chose s'est mal passé"
            description="L'application a rencontré une erreur inattendue."
            onRetry={this.reset}
            className="w-full max-w-md"
          />
        </div>
      );
    }
    return this.props.children;
  }
}
