import { Component, type ReactNode, type ErrorInfo } from 'react'
import { cn } from '@/lib/utils'

interface ErrorBoundaryProps {
  children: ReactNode
  /** Custom fallback UI. If not provided, a default error card is shown. */
  fallback?: ReactNode
  /** Additional CSS classes for the default fallback wrapper */
  className?: string
  /** Called when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo)
    this.props.onError?.(error, errorInfo)
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children
    }

    if (this.props.fallback) {
      return this.props.fallback
    }

    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-4 rounded-lg border border-red-200 bg-red-50 p-8',
          this.props.className,
        )}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
          <svg
            className="h-6 w-6 text-red-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>

        <div className="text-center">
          <h3 className="text-lg font-semibold text-red-800">
            Something went wrong
          </h3>
          <p className="mt-1 text-sm text-red-600">
            {this.state.error?.message ?? 'An unexpected error occurred.'}
          </p>
        </div>

        <button
          type="button"
          onClick={this.handleRetry}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
        >
          Try again
        </button>
      </div>
    )
  }
}
