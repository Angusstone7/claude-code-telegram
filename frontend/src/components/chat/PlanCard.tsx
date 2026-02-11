import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { Check, X, ChevronDown, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────

interface PlanCardProps {
  requestId: string
  content: string
  onApprove: (requestId: string) => void
  onReject: (requestId: string, feedback?: string) => void
}

// ── Constants ────────────────────────────────────────────────────────────

/** Collapse plan content if it exceeds this character count */
const COLLAPSE_THRESHOLD = 600

// ── Component ────────────────────────────────────────────────────────────

export function PlanCard({
  requestId,
  content,
  onApprove,
  onReject,
}: PlanCardProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(content.length <= COLLAPSE_THRESHOLD)
  const [showRejectForm, setShowRejectForm] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [responded, setResponded] = useState<'approved' | 'rejected' | null>(
    null,
  )

  const handleApprove = () => {
    setResponded('approved')
    onApprove(requestId)
  }

  const handleReject = () => {
    if (!showRejectForm) {
      setShowRejectForm(true)
      return
    }
    setResponded('rejected')
    onReject(requestId, feedback.trim() || undefined)
  }

  const isLong = content.length > COLLAPSE_THRESHOLD

  return (
    <div className="rounded-lg border border-purple-500/40 bg-card p-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="rounded-md bg-purple-500/20 p-1.5">
          <FileText className="h-4 w-4 text-purple-600 dark:text-purple-400" />
        </div>
        <h3 className="text-sm font-semibold text-card-foreground">
          {t('chat.plan.title')}
        </h3>
      </div>

      {/* Plan content (collapsible if long) */}
      <div className="mt-3">
        <div
          className={cn(
            'prose prose-sm dark:prose-invert max-w-none overflow-hidden break-words [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3',
            !expanded && isLong && 'max-h-48 overflow-hidden',
          )}
        >
          <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
            {content}
          </ReactMarkdown>
        </div>

        {/* Gradient fade + expand toggle for long content */}
        {isLong && (
          <div className="relative">
            {!expanded && (
              <div className="pointer-events-none absolute -top-12 left-0 right-0 h-12 bg-gradient-to-t from-card to-transparent" />
            )}
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="mt-1 flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-card-foreground transition-colors"
            >
              <ChevronDown
                className={cn(
                  'h-3.5 w-3.5 transition-transform',
                  expanded && 'rotate-180',
                )}
              />
              {expanded ? t('common.close') : 'Show full plan'}
            </button>
          </div>
        )}
      </div>

      {/* Action buttons / responded state */}
      {responded === null ? (
        <div className="mt-4 space-y-3">
          {/* Reject feedback form */}
          {showRejectForm && (
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={t('chat.plan.feedback')}
              rows={3}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
            />
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleApprove}
              className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
            >
              <Check className="h-4 w-4" />
              {t('chat.plan.approve')}
            </button>
            <button
              type="button"
              onClick={handleReject}
              className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
            >
              <X className="h-4 w-4" />
              {t('chat.plan.reject')}
            </button>
            {showRejectForm && (
              <button
                type="button"
                onClick={() => setShowRejectForm(false)}
                className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:text-card-foreground transition-colors"
              >
                {t('common.cancel')}
              </button>
            )}
          </div>
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
              ? t('chat.plan.approve')
              : t('chat.plan.reject')}
          </span>
        </div>
      )}
    </div>
  )
}
