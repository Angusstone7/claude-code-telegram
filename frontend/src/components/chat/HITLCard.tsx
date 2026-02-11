import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, X, ChevronDown, Shield } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────

interface HITLCardProps {
  requestId: string
  toolName: string
  toolInput: Record<string, unknown>
  description: string
  onApprove: (requestId: string) => void
  onReject: (requestId: string) => void
}

// ── Component ────────────────────────────────────────────────────────────

export function HITLCard({
  requestId,
  toolName,
  toolInput,
  description,
  onApprove,
  onReject,
}: HITLCardProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const [responded, setResponded] = useState<'approved' | 'rejected' | null>(
    null,
  )

  const handleApprove = () => {
    setResponded('approved')
    onApprove(requestId)
  }

  const handleReject = () => {
    setResponded('rejected')
    onReject(requestId)
  }

  return (
    <div className="rounded-lg border border-yellow-500/40 bg-card p-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="rounded-md bg-yellow-500/20 p-1.5">
          <Shield className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
        </div>
        <h3 className="text-sm font-semibold text-card-foreground">
          {t('chat.hitl.title')}
        </h3>
      </div>

      {/* Tool name badge */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs text-muted-foreground">
          {t('chat.hitl.tool')}:
        </span>
        <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-card-foreground">
          {toolName}
        </span>
      </div>

      {/* Description */}
      {description && (
        <p className="mt-2 text-sm text-card-foreground">{description}</p>
      )}

      {/* Collapsible JSON view */}
      <div className="mt-3">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-card-foreground transition-colors"
        >
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 transition-transform',
              expanded && 'rotate-180',
            )}
          />
          {t('chat.hitl.input')}
        </button>
        {expanded && (
          <pre className="mt-2 max-h-60 overflow-auto rounded-md bg-muted p-3 text-xs text-card-foreground">
            {JSON.stringify(toolInput, null, 2)}
          </pre>
        )}
      </div>

      {/* Action buttons */}
      {responded === null ? (
        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            onClick={handleApprove}
            className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
          >
            <Check className="h-4 w-4" />
            {t('chat.hitl.approve')}
          </button>
          <button
            type="button"
            onClick={handleReject}
            className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
          >
            <X className="h-4 w-4" />
            {t('chat.hitl.reject')}
          </button>
        </div>
      ) : (
        <div className="mt-4">
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
              responded === 'approved'
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
            )}
          >
            {responded === 'approved' ? (
              <Check className="h-3 w-3" />
            ) : (
              <X className="h-3 w-3" />
            )}
            {responded === 'approved'
              ? t('chat.hitl.approve')
              : t('chat.hitl.reject')}
          </span>
        </div>
      )}
    </div>
  )
}
