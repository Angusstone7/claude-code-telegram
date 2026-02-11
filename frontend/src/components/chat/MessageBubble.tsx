import { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { Copy, Check, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isToolUse?: boolean
  toolName?: string
}

// ── Code Block with Copy ─────────────────────────────────────────────────

function CodeBlock({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<'code'> & { children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false)

  // Detect if this is an inline code span or a fenced code block.
  // react-markdown wraps fenced blocks in <pre><code>, so when we
  // receive a `className` starting with "language-" it is a block.
  const isBlock = typeof className === 'string' && /language-/.test(className)

  const handleCopy = useCallback(() => {
    const text = String(children).replace(/\n$/, '')
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [children])

  if (!isBlock) {
    return (
      <code
        className="rounded bg-muted px-1.5 py-0.5 text-sm font-mono text-card-foreground"
        {...props}
      >
        {children}
      </code>
    )
  }

  return (
    <div className="group relative">
      <button
        type="button"
        onClick={handleCopy}
        className="absolute right-2 top-2 rounded-md border border-border bg-card p-1.5 text-muted-foreground opacity-0 transition-opacity hover:text-card-foreground group-hover:opacity-100"
        aria-label="Copy code"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-green-500" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
      <code className={className} {...props}>
        {children}
      </code>
    </div>
  )
}

// ── Timestamp Formatter ──────────────────────────────────────────────────

function formatTime(date: Date): string {
  return new Intl.DateTimeFormat('default', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

// ── Component ────────────────────────────────────────────────────────────

export function MessageBubble({
  role,
  content,
  timestamp,
  isToolUse,
  toolName,
}: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div
      className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}
    >
      <div
        className={cn(
          'relative max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-blue-600 text-white'
            : 'border border-border bg-card text-card-foreground',
        )}
      >
        {/* Tool use badge */}
        {isToolUse && toolName && (
          <div className="mb-2 flex items-center gap-1.5">
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                isUser
                  ? 'bg-blue-500/60 text-blue-100'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              <Wrench className="h-3 w-3" />
              {toolName}
            </span>
          </div>
        )}

        {/* Message content */}
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none overflow-hidden break-words [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3">
            <ReactMarkdown
              rehypePlugins={[rehypeHighlight]}
              components={{ code: CodeBlock }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}

        {/* Timestamp */}
        <p
          className={cn(
            'mt-1.5 text-[10px]',
            isUser ? 'text-blue-200' : 'text-muted-foreground',
          )}
        >
          {formatTime(timestamp instanceof Date ? timestamp : new Date(timestamp))}
        </p>
      </div>
    </div>
  )
}
