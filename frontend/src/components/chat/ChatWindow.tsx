import { useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageCircle } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { StreamingText } from './StreamingText'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

interface ChatWindowProps {
  messages: ChatMessage[]
  className?: string
}

// ── Helpers ──────────────────────────────────────────────────────────────

function isSameDay(a: Date, b: Date): boolean {
  const da = a instanceof Date ? a : new Date(a)
  const db = b instanceof Date ? b : new Date(b)
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  )
}

function formatDateSeparator(date: Date): string {
  const d = date instanceof Date ? date : new Date(date)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)

  if (isSameDay(d, today)) return 'Today'
  if (isSameDay(d, yesterday)) return 'Yesterday'

  return new Intl.DateTimeFormat('default', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(d)
}

// ── Date Separator ───────────────────────────────────────────────────────

function DateSeparator({ date }: { date: Date }) {
  return (
    <div className="flex items-center gap-3 py-3">
      <div className="h-px flex-1 bg-border" />
      <span className="text-xs font-medium text-muted-foreground">
        {formatDateSeparator(date)}
      </span>
      <div className="h-px flex-1 bg-border" />
    </div>
  )
}

// ── Empty State ──────────────────────────────────────────────────────────

function EmptyState() {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-full bg-muted p-4">
        <MessageCircle className="h-8 w-8 text-muted-foreground" />
      </div>
      <div>
        <p className="text-lg font-medium text-card-foreground">
          {t('chat.title')}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {t('chat.placeholder')}
        </p>
      </div>
    </div>
  )
}

// ── Component ────────────────────────────────────────────────────────────

export function ChatWindow({ messages, className }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive or content streams
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, messages.length > 0 ? messages[messages.length - 1].content : ''])

  if (messages.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-1 flex-col rounded-lg border border-border bg-card',
          className,
        )}
      >
        <EmptyState />
      </div>
    )
  }

  return (
    <div
      className={cn(
        'flex flex-1 flex-col rounded-lg border border-border bg-card overflow-y-auto',
        className,
      )}
    >
      <div className="flex flex-1 flex-col gap-3 p-4">
        {messages.map((msg, idx) => {
          const prevMsg = idx > 0 ? messages[idx - 1] : null
          const showDateSep =
            !prevMsg ||
            !isSameDay(
              prevMsg.timestamp instanceof Date
                ? prevMsg.timestamp
                : new Date(prevMsg.timestamp),
              msg.timestamp instanceof Date
                ? msg.timestamp
                : new Date(msg.timestamp),
            )

          return (
            <div key={msg.id}>
              {showDateSep && (
                <DateSeparator
                  date={
                    msg.timestamp instanceof Date
                      ? msg.timestamp
                      : new Date(msg.timestamp)
                  }
                />
              )}

              {msg.isStreaming ? (
                <div className="flex w-full justify-start">
                  <div className="relative max-w-[85%] rounded-lg border border-border bg-card px-4 py-3 text-sm leading-relaxed text-card-foreground">
                    <StreamingText
                      content={msg.content}
                      isStreaming={true}
                    />
                  </div>
                </div>
              ) : (
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  timestamp={
                    msg.timestamp instanceof Date
                      ? msg.timestamp
                      : new Date(msg.timestamp)
                  }
                />
              )}
            </div>
          )
        })}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
