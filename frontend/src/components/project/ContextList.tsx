// ---------------------------------------------------------------------------
// ContextList — displays contexts for a project with CRUD operations
// ---------------------------------------------------------------------------

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Plus,
  MessageSquare,
  Trash2,
  Eraser,
  Play,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDate } from '@/lib/utils'
import {
  useContexts,
  useCreateContext,
  useActivateContext,
  useDeleteContext,
  useClearContextMessages,
} from '@/hooks/useProjects'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'

interface ContextListProps {
  projectId: string
  className?: string
}

export function ContextList({ projectId, className }: ContextListProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useContexts(projectId)
  const createContext = useCreateContext()
  const activateContext = useActivateContext()
  const deleteContext = useDeleteContext()
  const clearMessages = useClearContextMessages()

  const [showForm, setShowForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const contexts = data?.items ?? []

  const handleCreate = () => {
    if (!newName.trim()) return
    createContext.mutate(
      { projectId, name: newName.trim() },
      {
        onSuccess: () => {
          setNewName('')
          setShowForm(false)
        },
      },
    )
  }

  const handleActivate = (contextId: string) => {
    activateContext.mutate({ projectId, contextId })
  }

  const handleDelete = (contextId: string) => {
    deleteContext.mutate(
      { projectId, contextId },
      { onSuccess: () => setConfirmDeleteId(null) },
    )
  }

  const handleClearMessages = (contextId: string) => {
    clearMessages.mutate({ projectId, contextId })
  }

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center py-8', className)}>
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-card-foreground">
          {t('projects.contexts')}
        </h3>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          {t('projects.createContext')}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-border bg-background p-3">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={t('common.name')}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={createContext.isPending || !newName.trim()}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {t('common.create')}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false)
                setNewName('')
              }}
              className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-card-foreground hover:bg-accent transition-colors"
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      {/* Context list */}
      {contexts.length === 0 ? (
        <EmptyState
          title={t('projects.noContexts')}
          icon={MessageSquare}
          className="py-6"
        />
      ) : (
        <div className="space-y-2">
          {contexts.map((ctx) => (
            <div
              key={ctx.id}
              className={cn(
                'rounded-lg border p-3 transition-colors',
                ctx.updated_at === ctx.created_at
                  ? 'border-border bg-card'
                  : 'border-border bg-card',
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate text-sm font-medium text-card-foreground">
                      {ctx.name}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>
                      {ctx.messages_count} {t('projects.messages')}
                    </span>
                    <span>{formatDate(ctx.created_at)}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleActivate(ctx.id)}
                    title={t('projects.activateContext')}
                    className={cn(
                      'rounded-md p-1.5 transition-colors',
                      'text-muted-foreground hover:bg-accent hover:text-card-foreground',
                    )}
                  >
                    <Play className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleClearMessages(ctx.id)}
                    title={t('projects.clearMessages')}
                    disabled={clearMessages.isPending}
                    className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-card-foreground transition-colors disabled:opacity-50"
                  >
                    <Eraser className="h-3.5 w-3.5" />
                  </button>
                  {confirmDeleteId === ctx.id ? (
                    <button
                      type="button"
                      onClick={() => handleDelete(ctx.id)}
                      disabled={deleteContext.isPending}
                      className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                    >
                      {t('common.confirm')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteId(ctx.id)}
                      title={t('common.delete')}
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
