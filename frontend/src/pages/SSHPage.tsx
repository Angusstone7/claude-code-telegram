import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import {
  Terminal,
  Send,
  Clock,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  XCircle,
  History,
  Loader2,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────

interface SSHCommandResponse {
  command: string
  output: string
  exit_code: number
  executed_at: string
  duration_ms: number
}

interface SSHHistoryResponse {
  commands: SSHCommandResponse[]
  total: number
}

// ── Hooks ────────────────────────────────────────────────────────────────

function useSSHHistory() {
  return useQuery<SSHHistoryResponse>({
    queryKey: ['ssh', 'history'],
    queryFn: async () =>
      (await api.get<SSHHistoryResponse>('/ssh/history?limit=50')).data,
    staleTime: 5_000,
  })
}

function useSSHExecute() {
  const queryClient = useQueryClient()
  return useMutation<SSHCommandResponse, Error, { command: string; timeout?: number }>({
    mutationFn: async ({ command, timeout = 30 }) => {
      const res = await api.post<SSHCommandResponse>('/ssh/execute', {
        command,
        timeout,
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ssh', 'history'] })
    },
  })
}

// ── OutputBlock ──────────────────────────────────────────────────────────

function OutputBlock({ entry }: { entry: SSHCommandResponse }) {
  const date = new Date(entry.executed_at)
  const timeStr = date.toLocaleTimeString()

  return (
    <div className="group">
      {/* Command line */}
      <div className="flex items-center gap-2 text-sm">
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-green-400" />
        <span className="font-mono font-semibold text-green-400">{entry.command}</span>
        <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-gray-500 opacity-0 transition-opacity group-hover:opacity-100">
          <Clock className="h-3 w-3" />
          {timeStr}
          <span className="tabular-nums">{entry.duration_ms}ms</span>
          {entry.exit_code === 0 ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <XCircle className="h-3.5 w-3.5 text-red-400" />
          )}
        </span>
      </div>

      {/* Output */}
      {entry.output && (
        <pre className="mt-1 whitespace-pre-wrap break-all pl-5 text-sm leading-relaxed text-gray-300">
          {entry.output}
        </pre>
      )}

      {/* Exit code indicator for non-zero */}
      {entry.exit_code !== 0 && (
        <div className="mt-1 flex items-center gap-1 pl-5 text-xs text-red-400">
          <AlertCircle className="h-3 w-3" />
          exit code: {entry.exit_code}
        </div>
      )}
    </div>
  )
}

// ── HistoryPanel ─────────────────────────────────────────────────────────

function HistoryPanel({
  commands,
  onSelect,
}: {
  commands: SSHCommandResponse[]
  onSelect: (cmd: string) => void
}) {
  const { t } = useTranslation()

  // Extract unique commands (most recent first, deduplicated)
  const uniqueCommands: string[] = []
  const seen = new Set<string>()
  for (const entry of commands) {
    if (!seen.has(entry.command)) {
      seen.add(entry.command)
      uniqueCommands.push(entry.command)
    }
  }

  if (uniqueCommands.length === 0) return null

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-gray-400">
        <History className="h-3.5 w-3.5" />
        {t('ssh.history')}
      </p>
      <div className="max-h-48 space-y-1 overflow-y-auto">
        {uniqueCommands.slice(0, 20).map((cmd, idx) => (
          <button
            key={idx}
            className="w-full truncate rounded px-2 py-1 text-left font-mono text-xs text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
            onClick={() => onSelect(cmd)}
            title={cmd}
          >
            $ {cmd}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────

export function SSHPage() {
  const { t } = useTranslation()
  const [command, setCommand] = useState('')
  const [localResults, setLocalResults] = useState<SSHCommandResponse[]>([])
  const [showHistory, setShowHistory] = useState(false)

  const outputRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: history } = useSSHHistory()
  const executeMut = useSSHExecute()

  // Auto-scroll to bottom on new output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [localResults])

  const handleExecute = useCallback(() => {
    const trimmed = command.trim()
    if (!trimmed || executeMut.isPending) return

    executeMut.mutate(
      { command: trimmed, timeout: 30 },
      {
        onSuccess: (result) => {
          setLocalResults((prev) => [...prev, result])
          setCommand('')
          inputRef.current?.focus()
        },
        onError: (err) => {
          // Create a pseudo-result for the error
          const errorResult: SSHCommandResponse = {
            command: trimmed,
            output: `Error: ${err.message}`,
            exit_code: -1,
            executed_at: new Date().toISOString(),
            duration_ms: 0,
          }
          setLocalResults((prev) => [...prev, errorResult])
          setCommand('')
          inputRef.current?.focus()
        },
      },
    )
  }, [command, executeMut])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleExecute()
    }
  }

  const handleHistorySelect = (cmd: string) => {
    setCommand(cmd)
    setShowHistory(false)
    inputRef.current?.focus()
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t('ssh.title')}</h1>
        <button
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
            showHistory
              ? 'bg-gray-700 text-white'
              : 'text-muted-foreground hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
          onClick={() => setShowHistory(!showHistory)}
        >
          <History className="h-4 w-4" />
          {t('ssh.history')}
        </button>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        {/* Terminal area */}
        <div className="flex min-w-0 flex-1 flex-col rounded-lg border border-gray-700 bg-gray-900 shadow-lg">
          {/* Terminal header */}
          <div className="flex items-center gap-2 border-b border-gray-700 px-4 py-2">
            <div className="flex gap-1.5">
              <span className="h-3 w-3 rounded-full bg-red-500" />
              <span className="h-3 w-3 rounded-full bg-yellow-500" />
              <span className="h-3 w-3 rounded-full bg-green-500" />
            </div>
            <span className="ml-2 text-xs text-gray-400">SSH Terminal</span>
          </div>

          {/* Output area */}
          <div
            ref={outputRef}
            className="flex-1 overflow-y-auto px-4 py-3 font-mono text-sm"
          >
            {localResults.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <div className="text-center text-gray-500">
                  <Terminal className="mx-auto mb-2 h-8 w-8" />
                  <p className="text-sm">{t('ssh.placeholder')}</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {localResults.map((entry, idx) => (
                  <OutputBlock key={idx} entry={entry} />
                ))}

                {/* Loading indicator */}
                {executeMut.isPending && (
                  <div className="flex items-center gap-2 pl-5 text-sm text-gray-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Executing...
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Command input */}
          <div className="border-t border-gray-700 p-3">
            <div className="flex items-center gap-2">
              <span className="shrink-0 font-mono text-sm text-green-400">$</span>
              <input
                ref={inputRef}
                type="text"
                className="min-w-0 flex-1 bg-transparent font-mono text-sm text-gray-100 placeholder-gray-500 outline-none"
                placeholder={t('ssh.placeholder')}
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={executeMut.isPending}
                autoFocus
              />
              <button
                className="flex shrink-0 items-center gap-1.5 rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-50 disabled:hover:bg-green-600"
                onClick={handleExecute}
                disabled={!command.trim() || executeMut.isPending}
              >
                {executeMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                {t('ssh.execute')}
              </button>
            </div>
          </div>
        </div>

        {/* History sidebar */}
        {showHistory && history && (
          <div className="w-72 shrink-0">
            <HistoryPanel
              commands={history.commands}
              onSelect={handleHistorySelect}
            />
          </div>
        )}
      </div>
    </div>
  )
}
