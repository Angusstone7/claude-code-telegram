import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageCircleQuestion, Send } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────

interface QuestionCardProps {
  requestId: string
  question: string
  options: string[] | null
  onAnswer: (requestId: string, answer: string) => void
}

// ── Component ────────────────────────────────────────────────────────────

export function QuestionCard({
  requestId,
  question,
  options,
  onAnswer,
}: QuestionCardProps) {
  const { t } = useTranslation()
  const [textInput, setTextInput] = useState('')
  const [answered, setAnswered] = useState<string | null>(null)

  const handleOptionClick = (option: string) => {
    setAnswered(option)
    onAnswer(requestId, option)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = textInput.trim()
    if (!trimmed) return
    setAnswered(trimmed)
    onAnswer(requestId, trimmed)
  }

  return (
    <div className="rounded-lg border border-blue-500/40 bg-card p-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="rounded-md bg-blue-500/20 p-1.5">
          <MessageCircleQuestion className="h-4 w-4 text-blue-600 dark:text-blue-400" />
        </div>
        <h3 className="text-sm font-semibold text-card-foreground">
          {t('chat.question.title')}
        </h3>
      </div>

      {/* Question text */}
      <p className="mt-3 text-sm text-card-foreground whitespace-pre-wrap">
        {question}
      </p>

      {/* Answer area */}
      {answered === null ? (
        <div className="mt-4">
          {options && options.length > 0 ? (
            /* Option buttons */
            <div className="flex flex-wrap gap-2">
              {options.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => handleOptionClick(option)}
                  className="rounded-md border border-border bg-muted px-3 py-2 text-sm font-medium text-card-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  {option}
                </button>
              ))}
            </div>
          ) : (
            /* Free text input */
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder={t('chat.question.answer')}
                className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
              <button
                type="submit"
                disabled={!textInput.trim()}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium text-white transition-colors',
                  textInput.trim()
                    ? 'bg-blue-600 hover:bg-blue-700'
                    : 'bg-blue-600/50 cursor-not-allowed',
                )}
              >
                <Send className="h-4 w-4" />
                {t('chat.question.answer')}
              </button>
            </form>
          )}
        </div>
      ) : (
        /* Answered state */
        <div className="mt-4">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
            {t('chat.question.answer')}: {answered}
          </span>
        </div>
      )}
    </div>
  )
}
