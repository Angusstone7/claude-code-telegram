// ---------------------------------------------------------------------------
// VariableManager — CRUD interface for project/global variables
// ---------------------------------------------------------------------------

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Plus,
  Pencil,
  Trash2,
  Save,
  X,
  Variable,
  Filter,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDate } from '@/lib/utils'
import {
  useVariables,
  useCreateVariable,
  useUpdateVariable,
  useDeleteVariable,
} from '@/hooks/useProjects'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import type { VariableResponse } from '@/types/api'

// ── Types ────────────────────────────────────────────────────────────────

type ScopeFilter = 'all' | 'global' | 'project'

interface VariableManagerProps {
  projectId: string
  className?: string
}

// ── Component ────────────────────────────────────────────────────────────

export function VariableManager({ projectId, className }: VariableManagerProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useVariables(projectId)
  const createVariable = useCreateVariable()
  const updateVariable = useUpdateVariable()
  const deleteVariable = useDeleteVariable()

  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  // Create form state
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')
  const [newScope, setNewScope] = useState<'global' | 'project'>('project')

  // Edit form state
  const [editKey, setEditKey] = useState('')
  const [editValue, setEditValue] = useState('')

  const variables = data?.items ?? []

  const filteredVariables =
    scopeFilter === 'all'
      ? variables
      : variables.filter((v) => v.scope === scopeFilter)

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleCreate = () => {
    if (!newKey.trim() || !newValue.trim()) return

    createVariable.mutate(
      {
        projectId,
        payload: {
          key: newKey.trim(),
          value: newValue.trim(),
          scope: newScope,
          project_id: newScope === 'project' ? projectId : null,
        },
      },
      {
        onSuccess: () => {
          setNewKey('')
          setNewValue('')
          setNewScope('project')
          setShowForm(false)
        },
      },
    )
  }

  const startEdit = (variable: VariableResponse) => {
    setEditingId(variable.id)
    setEditKey(variable.key)
    setEditValue(variable.value)
  }

  const handleUpdate = () => {
    if (!editingId || !editKey.trim() || !editValue.trim()) return

    updateVariable.mutate(
      {
        projectId,
        variableId: editingId,
        payload: { key: editKey.trim(), value: editValue.trim() },
      },
      {
        onSuccess: () => {
          setEditingId(null)
          setEditKey('')
          setEditValue('')
        },
      },
    )
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditKey('')
    setEditValue('')
  }

  const handleDelete = (variableId: string) => {
    deleteVariable.mutate(
      { projectId, variableId },
      { onSuccess: () => setConfirmDeleteId(null) },
    )
  }

  // ── Render ────────────────────────────────────────────────────────────

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
          {t('projects.variables')}
        </h3>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          {t('projects.addVariable')}
        </button>
      </div>

      {/* Scope filter */}
      <div className="flex items-center gap-1">
        <Filter className="h-3.5 w-3.5 text-muted-foreground" />
        {(['all', 'project', 'global'] as ScopeFilter[]).map((scope) => (
          <button
            key={scope}
            type="button"
            onClick={() => setScopeFilter(scope)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              scopeFilter === scope
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                : 'text-muted-foreground hover:bg-accent hover:text-card-foreground',
            )}
          >
            {t(`projects.scope_${scope}`)}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-border bg-background p-3">
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder={t('projects.variableKey')}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <input
                type="text"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder={t('projects.variableValue')}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={newScope}
                onChange={(e) =>
                  setNewScope(e.target.value as 'global' | 'project')
                }
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-card-foreground focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="project">{t('projects.scope_project')}</option>
                <option value="global">{t('projects.scope_global')}</option>
              </select>
              <div className="flex-1" />
              <button
                type="button"
                onClick={handleCreate}
                disabled={
                  createVariable.isPending || !newKey.trim() || !newValue.trim()
                }
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {t('common.create')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  setNewKey('')
                  setNewValue('')
                }}
                className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-card-foreground hover:bg-accent transition-colors"
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Variable list */}
      {filteredVariables.length === 0 ? (
        <EmptyState
          title={t('projects.noVariables')}
          icon={Variable}
          className="py-6"
        />
      ) : (
        <div className="space-y-2">
          {filteredVariables.map((variable) => (
            <div
              key={variable.id}
              className="rounded-lg border border-border bg-card p-3"
            >
              {editingId === variable.id ? (
                /* Inline edit form */
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={editKey}
                      onChange={(e) => setEditKey(e.target.value)}
                      className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-card-foreground focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-card-foreground focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={handleUpdate}
                      disabled={updateVariable.isPending}
                      className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      <Save className="h-3 w-3" />
                      {t('common.save')}
                    </button>
                    <button
                      type="button"
                      onClick={cancelEdit}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-card-foreground hover:bg-accent transition-colors"
                    >
                      <X className="h-3 w-3" />
                      {t('common.cancel')}
                    </button>
                  </div>
                </div>
              ) : (
                /* Read view */
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-card-foreground">
                        {variable.key}
                      </span>
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium',
                          variable.scope === 'global'
                            ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                            : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
                        )}
                      >
                        {t(`projects.scope_${variable.scope}`)}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {variable.value.length > 80
                        ? `${variable.value.slice(0, 80)}...`
                        : variable.value}
                    </p>
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {formatDate(variable.updated_at)}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={() => startEdit(variable)}
                      title={t('common.edit')}
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-card-foreground transition-colors"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    {confirmDeleteId === variable.id ? (
                      <button
                        type="button"
                        onClick={() => handleDelete(variable.id)}
                        disabled={deleteVariable.isPending}
                        className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                      >
                        {t('common.confirm')}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(variable.id)}
                        title={t('common.delete')}
                        className="rounded-md p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
