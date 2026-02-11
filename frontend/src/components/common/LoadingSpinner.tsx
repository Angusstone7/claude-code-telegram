import { cn } from '@/lib/utils'

interface LoadingSpinnerProps {
  /** Optional message shown below the spinner */
  message?: string
  /** Additional CSS classes for the wrapper */
  className?: string
  /** Spinner size: sm (16px), md (32px), lg (48px) */
  size?: 'sm' | 'md' | 'lg'
}

const sizeMap = {
  sm: 'h-4 w-4 border-2',
  md: 'h-8 w-8 border-3',
  lg: 'h-12 w-12 border-4',
} as const

export function LoadingSpinner({
  message,
  className,
  size = 'md',
}: LoadingSpinnerProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3', className)}>
      <div
        className={cn(
          'animate-spin rounded-full border-solid border-gray-300 border-t-blue-600',
          sizeMap[size],
        )}
        role="status"
        aria-label="Loading"
      />
      {message && (
        <p className="text-sm text-gray-500">{message}</p>
      )}
    </div>
  )
}
