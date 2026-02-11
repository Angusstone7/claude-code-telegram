// ---------------------------------------------------------------------------
// ChatPage — assembles all chat components into a full page with session
// management sidebar, message area, interactive cards, and input controls.
// ---------------------------------------------------------------------------

import { useState, useRef, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Send,
  Paperclip,
  StopCircle,
  Plus,
  MessageSquare,
  Wifi,
  WifiOff,
  Loader2,
  PanelLeftClose,
  PanelLeft,
  FolderOpen,
} from 'lucide-react'
import { api } from '@/services/api'
import { cn } from '@/lib/utils'
import { useChat } from '@/hooks/useChat'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { HITLCard } from '@/components/chat/HITLCard'
import { QuestionCard } from '@/components/chat/QuestionCard'
import { PlanCard } from '@/components/chat/PlanCard'
import type {
  ProjectListResponse,
  ContextResponse,
  ContextListResponse,
  CreateContextRequest,
} from '@/types/api'

// ── Query keys ────────────────────────────────────────────────────────────

const projectKeys = {
  all: ['projects'] as const,
  list: () => [...projectKeys.all, 'list'] as const,
}

const contextKeys = {
  all: ['contexts'] as const,
  byProject: (projectId: string) =>
    [...contextKeys.all, projectId] as const,
}

// ── Connection status badge ───────────────────────────────────────────────

function ConnectionBadge({
  isConnected,
  isTaskRunning,
}: {
  isConnected: boolean
  isTaskRunning: boolean
}) {
  const { t } = useTranslation()

  if (isTaskRunning) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
        <Loader2 className="h-3 w-3 animate-spin" />
        {t('chat.streaming')}
      </span>
    )
  }

  if (isConnected) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/15 px-2.5 py-1 text-xs font-medium text-green-400">
        <Wifi className="h-3 w-3" />
        {t('chat.connected')}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-1 text-xs font-medium text-red-400">
      <WifiOff className="h-3 w-3" />
      {t('chat.disconnected')}
    </span>
  )
}

// ── Session sidebar ───────────────────────────────────────────────────────

function SessionSidebar({
  contexts,
  activeContextId,
  onSelectContext,
  onCreateContext,
  isCreating,
  collapsed,
  onToggle,
}: {
  contexts: ContextResponse[]
  activeContextId: string | null
  onSelectContext: (ctx: ContextResponse) => void
  onCreateContext: () => void
  isCreating: boolean
  collapsed: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation()

  if (collapsed) {
    return (
      <div className="flex w-12 flex-col items-center border-r border-border bg-card py-3">
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          title={t('chat.sessions')}
        >
          <PanelLeft className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="flex w-64 flex-col border-r border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-3 py-3">
        <h3 className="text-sm font-semibold text-card-foreground">
          {t('chat.sessions')}
        </h3>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {/* New session button */}
      <div className="p-2">
        <button
          type="button"
          onClick={onCreateContext}
          disabled={isCreating}
          className={cn(
            'flex w-full items-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-sm font-medium transition-colors',
            isCreating
              ? 'cursor-not-allowed text-muted-foreground'
              : 'text-card-foreground hover:bg-accent hover:text-accent-foreground',
          )}
        >
          {isCreating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {t('chat.newSession')}
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {contexts.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-muted-foreground">
            {t('chat.noSessions')}
          </p>
        ) : (
          <div className="space-y-1">
            {contexts.map((ctx) => (
              <button
                key={ctx.id}
                type="button"
                onClick={() => onSelectContext(ctx)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
                  activeContextId === ctx.id
                    ? 'bg-accent text-accent-foreground'
                    : 'text-card-foreground hover:bg-accent/50',
                )}
              >
                <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{ctx.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {ctx.messages_count} msg
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── No project selected state ─────────────────────────────────────────────

function NoProjectState() {
  const { t } = useTranslation()

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-full bg-muted p-4">
        <FolderOpen className="h-8 w-8 text-muted-foreground" />
      </div>
      <div>
        <p className="text-lg font-medium text-card-foreground">
          {t('chat.noProject')}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {t('chat.selectProject')}
        </p>
      </div>
    </div>
  )
}

// ── Chat input bar ────────────────────────────────────────────────────────

function ChatInputBar({
  onSend,
  onCancel,
  isTaskRunning,
  isConnected,
  disabled,
}: {
  onSend: (text: string) => void
  onCancel: () => void
  isTaskRunning: boolean
  isConnected: boolean
  disabled: boolean
}) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault()
      const trimmed = input.trim()
      if (!trimmed || isTaskRunning || !isConnected || disabled) return
      onSend(trimmed)
      setInput('')
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    },
    [input, isTaskRunning, isConnected, disabled, onSend],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Send on Enter without Shift
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  // Auto-resize textarea
  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value)
      const el = e.target
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    },
    [],
  )

  return (
    <div className="border-t border-border bg-card px-4 py-3">
      {isTaskRunning ? (
        /* Cancel task bar */
        <div className="flex items-center justify-center">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-2 rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors"
          >
            <StopCircle className="h-4 w-4" />
            {t('chat.cancelTask')}
          </button>
        </div>
      ) : (
        /* Input form */
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          {/* Attach file button (placeholder for FileUpload integration) */}
          <button
            type="button"
            className="shrink-0 rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            title={t('chat.attachFile')}
            disabled={disabled || !isConnected}
          >
            <Paperclip className="h-5 w-5" />
          </button>

          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.placeholder')}
            rows={1}
            disabled={disabled || !isConnected}
            className={cn(
              'flex-1 resize-none rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground',
              'placeholder:text-muted-foreground',
              'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'max-h-[200px]',
            )}
          />

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || !isConnected || disabled}
            className={cn(
              'shrink-0 inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium text-white transition-colors',
              input.trim() && isConnected && !disabled
                ? 'bg-primary hover:bg-primary/90'
                : 'bg-primary/50 cursor-not-allowed',
            )}
            title={t('chat.sendMessage')}
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      )}
    </div>
  )
}

// ── Main ChatPage ─────────────────────────────────────────────────────────

export function ChatPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  // ── Local state ───────────────────────────────────────────────────────
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [activeContext, setActiveContext] = useState<ContextResponse | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // ── Fetch projects ────────────────────────────────────────────────────
  const { data: projectsData } = useQuery<ProjectListResponse>({
    queryKey: projectKeys.list(),
    queryFn: async () =>
      (await api.get<ProjectListResponse>('/projects')).data,
  })

  const projects = projectsData?.items ?? []

  // Auto-select first project if none active
  useEffect(() => {
    if (!activeProjectId && projects.length > 0) {
      setActiveProjectId(projects[0].id)
    }
  }, [activeProjectId, projects])

  // ── Fetch contexts for active project ─────────────────────────────────
  const { data: contextsData } = useQuery<ContextListResponse>({
    queryKey: contextKeys.byProject(activeProjectId ?? ''),
    queryFn: async () =>
      (
        await api.get<ContextListResponse>(
          `/projects/${activeProjectId}/contexts`,
        )
      ).data,
    enabled: activeProjectId !== null,
  })

  const contexts = contextsData?.items ?? []

  // Auto-select first context when contexts load
  useEffect(() => {
    if (contexts.length > 0 && !activeContext) {
      setActiveContext(contexts[0])
    }
    // If the active context was for a different project, reset
    if (
      activeContext &&
      activeProjectId &&
      activeContext.project_id !== activeProjectId
    ) {
      setActiveContext(contexts.length > 0 ? contexts[0] : null)
    }
  }, [contexts, activeContext, activeProjectId])

  // ── Create context mutation ───────────────────────────────────────────
  const createContextMutation = useMutation({
    mutationFn: async (req: CreateContextRequest) => {
      const { data } = await api.post<ContextResponse>(
        `/projects/${req.project_id}/contexts`,
        req,
      )
      return data
    },
    onSuccess: (newContext) => {
      queryClient.invalidateQueries({
        queryKey: contextKeys.byProject(activeProjectId ?? ''),
      })
      setActiveContext(newContext)
    },
  })

  const handleCreateContext = useCallback(() => {
    if (!activeProjectId || createContextMutation.isPending) return
    const name = `Session ${new Date().toLocaleString('default', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
    createContextMutation.mutate({
      name,
      project_id: activeProjectId,
    })
  }, [activeProjectId, createContextMutation])

  // ── Derive context id (numeric) from context.id ───────────────────────
  // The useChat hook expects a numeric contextId. Context IDs from the API
  // are strings — we parse them to numbers. If parsing fails we use the
  // hash-based fallback.
  const numericContextId =
    activeContext
      ? Number.isFinite(Number(activeContext.id))
        ? Number(activeContext.id)
        : 0
      : null

  // ── Chat hook ─────────────────────────────────────────────────────────
  const {
    messages,
    isConnected,
    isTaskRunning,
    hitlRequests,
    questionRequests,
    planRequests,
    sendMessage,
    approveHITL,
    rejectHITL,
    answerQuestion,
    approvePlan,
    rejectPlan,
    cancelTask,
  } = useChat(activeProjectId, numericContextId)

  // ── Find active project for display ───────────────────────────────────
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="-m-6 flex h-[calc(100vh-theme(spacing.16))] flex-col">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <h1 className="text-lg font-semibold text-card-foreground truncate">
            {activeContext?.name ?? t('chat.title')}
          </h1>
          {activeProject && (
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              <FolderOpen className="h-3 w-3" />
              {activeProject.name}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Project selector */}
          {projects.length > 1 && (
            <select
              value={activeProjectId ?? ''}
              onChange={(e) => {
                setActiveProjectId(e.target.value || null)
                setActiveContext(null)
              }}
              className="rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}

          <ConnectionBadge
            isConnected={isConnected}
            isTaskRunning={isTaskRunning}
          />
        </div>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Session sidebar */}
        {activeProjectId && (
          <SessionSidebar
            contexts={contexts}
            activeContextId={activeContext?.id ?? null}
            onSelectContext={setActiveContext}
            onCreateContext={handleCreateContext}
            isCreating={createContextMutation.isPending}
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed((prev) => !prev)}
          />
        )}

        {/* Chat area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {!activeProjectId ? (
            <NoProjectState />
          ) : (
            <>
              {/* Messages + interactive cards */}
              <div className="flex flex-1 flex-col overflow-y-auto">
                {/* ChatWindow takes up available space */}
                <ChatWindow
                  messages={messages}
                  className="flex-1 rounded-none border-0"
                />

                {/* Interactive cards overlay area */}
                {(hitlRequests.length > 0 ||
                  questionRequests.length > 0 ||
                  planRequests.length > 0) && (
                  <div className="space-y-3 border-t border-border bg-background/50 p-4">
                    {/* HITL permission requests */}
                    {hitlRequests.map((req) => (
                      <HITLCard
                        key={req.requestId}
                        requestId={req.requestId}
                        toolName={req.toolName}
                        toolInput={req.toolInput}
                        description={req.description}
                        onApprove={approveHITL}
                        onReject={rejectHITL}
                      />
                    ))}

                    {/* Question requests */}
                    {questionRequests.map((req) => (
                      <QuestionCard
                        key={req.requestId}
                        requestId={req.requestId}
                        question={req.question}
                        options={req.options}
                        onAnswer={answerQuestion}
                      />
                    ))}

                    {/* Plan approval requests */}
                    {planRequests.map((req) => (
                      <PlanCard
                        key={req.requestId}
                        requestId={req.requestId}
                        content={req.content}
                        onApprove={approvePlan}
                        onReject={rejectPlan}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Input bar */}
              <ChatInputBar
                onSend={sendMessage}
                onCancel={cancelTask}
                isTaskRunning={isTaskRunning}
                isConnected={isConnected}
                disabled={!activeContext}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
