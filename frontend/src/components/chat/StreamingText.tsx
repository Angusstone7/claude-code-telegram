import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────

interface StreamingTextProps {
  content: string
  isStreaming: boolean
  className?: string
}

// ── Component ────────────────────────────────────────────────────────────

export function StreamingText({
  content,
  isStreaming,
  className,
}: StreamingTextProps) {
  return (
    <div className={cn('relative', className)}>
      <div className="prose prose-sm dark:prose-invert max-w-none overflow-hidden break-words [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3">
        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
          {content}
        </ReactMarkdown>
      </div>

      {isStreaming && (
        <span
          className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-blue-500"
          aria-label="Streaming"
        />
      )}
    </div>
  )
}
