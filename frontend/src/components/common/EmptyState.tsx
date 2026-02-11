import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'

interface EmptyStateProps {
  /** Title text */
  title: string
  /** Description text shown below the title */
  description?: string
  /** Lucide icon component (default: Inbox) */
  icon?: LucideIcon
  /** Additional CSS classes for the wrapper */
  className?: string
  /** Optional action slot (e.g. a button) rendered below the description */
  children?: React.ReactNode
}

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  className,
  children,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-12 text-center',
        className,
      )}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gray-100">
        <Icon className="h-7 w-7 text-gray-400" />
      </div>

      <div className="space-y-1">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        {description && (
          <p className="max-w-sm text-sm text-gray-500">{description}</p>
        )}
      </div>

      {children && <div className="mt-2">{children}</div>}
    </div>
  )
}
