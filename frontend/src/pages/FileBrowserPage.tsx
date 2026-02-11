// ---------------------------------------------------------------------------
// FileBrowserPage — browse server filesystem within /root/projects
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Folder,
  File,
  ChevronRight,
  ArrowUp,
  FolderPlus,
  FolderCheck,
  Loader2,
  AlertCircle,
  Home,
} from 'lucide-react'
import { cn, formatFileSize } from '@/lib/utils'
import { api } from '@/services/api'
import type { FileBrowserResponse, FileEntry } from '@/types/api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

// ── Constants ────────────────────────────────────────────────────────────────

const ROOT_PATH = '/root/projects'

// ── Query keys ───────────────────────────────────────────────────────────────

const fileKeys = {
  all: ['files'] as const,
  browse: (path: string) => [...fileKeys.all, 'browse', path] as const,
}

// ── Component ────────────────────────────────────────────────────────────────

export function FileBrowserPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [currentPath, setCurrentPath] = useState(ROOT_PATH)
  const [showMkdir, setShowMkdir] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [notification, setNotification] = useState<string | null>(null)

  // ── Browse query ─────────────────────────────────────────────────────────

  const {
    data: browseData,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: fileKeys.browse(currentPath),
    queryFn: async () => {
      const { data } = await api.get<FileBrowserResponse>('/files/browse', {
        params: { path: currentPath },
      })
      return data
    },
  })

  // ── Mkdir mutation ───────────────────────────────────────────────────────

  const mkdirMutation = useMutation({
    mutationFn: async (fullPath: string) => {
      const { data } = await api.post<FileBrowserResponse>('/files/mkdir', {
        path: fullPath,
      })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: fileKeys.browse(currentPath) })
      setNewFolderName('')
      setShowMkdir(false)
    },
  })

  // ── Set as work dir mutation ─────────────────────────────────────────────

  const setWorkDirMutation = useMutation({
    mutationFn: async (path: string) => {
      // Use runtime config to set working dir
      await api.put('/config/CLAUDE_WORKING_DIR', { value: path })
      return path
    },
    onSuccess: (path) => {
      setNotification(`Working directory set to ${path}`)
    },
    onError: () => {
      setNotification('Failed to set working directory')
    },
  })

  // Auto-dismiss notification
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [notification])

  // ── Navigation ───────────────────────────────────────────────────────────

  const navigateTo = useCallback((path: string) => {
    setCurrentPath(path)
    setShowMkdir(false)
    setNewFolderName('')
  }, [])

  const navigateUp = useCallback(() => {
    if (browseData?.parent_path) {
      navigateTo(browseData.parent_path)
    }
  }, [browseData?.parent_path, navigateTo])

  const handleEntryClick = useCallback(
    (entry: FileEntry) => {
      if (entry.is_directory) {
        navigateTo(entry.path)
      }
    },
    [navigateTo],
  )

  const handleCreateFolder = useCallback(() => {
    const trimmed = newFolderName.trim()
    if (!trimmed) return
    const fullPath = currentPath.endsWith('/')
      ? `${currentPath}${trimmed}`
      : `${currentPath}/${trimmed}`
    mkdirMutation.mutate(fullPath)
  }, [currentPath, newFolderName, mkdirMutation])

  // ── Breadcrumbs ──────────────────────────────────────────────────────────

  const breadcrumbs = (() => {
    const normalizedRoot = ROOT_PATH.replace(/\/+$/, '')
    const normalizedCurrent = currentPath.replace(/\/+$/, '')

    if (normalizedCurrent === normalizedRoot) {
      return [{ label: 'projects', path: ROOT_PATH }]
    }

    const relativePath = normalizedCurrent.slice(normalizedRoot.length + 1)
    const segments = relativePath.split('/').filter(Boolean)

    const crumbs = [{ label: 'projects', path: ROOT_PATH }]
    let accumulated = normalizedRoot
    for (const seg of segments) {
      accumulated += '/' + seg
      crumbs.push({ label: seg, path: accumulated })
    }
    return crumbs
  })()

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-card-foreground">
          {t('files.title')}
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setWorkDirMutation.mutate(currentPath)}
            disabled={setWorkDirMutation.isPending}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium',
              'bg-green-600 text-white hover:bg-green-500',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'transition-colors',
            )}
          >
            <FolderCheck className="h-4 w-4" />
            {t('files.setAsWorkDir')}
          </button>
          <button
            onClick={() => setShowMkdir((prev) => !prev)}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium',
              'bg-primary text-primary-foreground hover:bg-primary/90',
              'transition-colors',
            )}
          >
            <FolderPlus className="h-4 w-4" />
            {t('files.createFolder')}
          </button>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2 text-sm text-green-400">
          {notification}
        </div>
      )}

      {/* Breadcrumb navigation */}
      <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
        <div className="flex items-center gap-1 overflow-x-auto text-sm">
          <button
            onClick={() => navigateTo(ROOT_PATH)}
            className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          >
            <Home className="h-4 w-4" />
          </button>
          {breadcrumbs.map((crumb, idx) => (
            <div key={crumb.path} className="flex items-center gap-1">
              {idx > 0 && (
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <button
                onClick={() => navigateTo(crumb.path)}
                className={cn(
                  'shrink-0 rounded px-2 py-1 transition-colors',
                  idx === breadcrumbs.length - 1
                    ? 'font-semibold text-card-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                )}
              >
                {crumb.label}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Create folder inline */}
      {showMkdir && (
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <FolderPlus className="h-5 w-5 text-primary" />
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateFolder()
                if (e.key === 'Escape') {
                  setShowMkdir(false)
                  setNewFolderName('')
                }
              }}
              placeholder={t('files.folderName')}
              className={cn(
                'flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm',
                'placeholder:text-muted-foreground',
                'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary',
              )}
              autoFocus
            />
            <button
              onClick={handleCreateFolder}
              disabled={!newFolderName.trim() || mkdirMutation.isPending}
              className={cn(
                'rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50',
                'transition-colors',
              )}
            >
              {mkdirMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.create')
              )}
            </button>
            <button
              onClick={() => {
                setShowMkdir(false)
                setNewFolderName('')
              }}
              className="rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-accent transition-colors"
            >
              {t('common.cancel')}
            </button>
          </div>
          {mkdirMutation.isError && (
            <p className="mt-2 text-sm text-destructive">
              {(mkdirMutation.error as Error)?.message ?? 'Error creating folder'}
            </p>
          )}
        </div>
      )}

      {/* File list */}
      <div className="flex-1 rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex h-64 items-center justify-center">
            <LoadingSpinner message={t('common.loading')} />
          </div>
        ) : isError ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2 text-destructive">
            <AlertCircle className="h-8 w-8" />
            <p className="text-sm">{(error as Error)?.message ?? t('common.error')}</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {/* Up row */}
            {browseData?.parent_path && (
              <button
                onClick={navigateUp}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-accent transition-colors"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary">
                  <ArrowUp className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="text-sm font-medium text-muted-foreground">
                  {t('files.parentDir')} ..
                </span>
              </button>
            )}

            {/* Entries */}
            {browseData?.entries.map((entry) => (
              <button
                key={entry.path}
                onClick={() => handleEntryClick(entry)}
                className={cn(
                  'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors',
                  entry.is_directory
                    ? 'cursor-pointer hover:bg-accent'
                    : 'cursor-default',
                )}
              >
                <div
                  className={cn(
                    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                    entry.is_directory
                      ? 'bg-primary/20'
                      : 'bg-secondary',
                  )}
                >
                  {entry.is_directory ? (
                    <Folder className="h-4 w-4 text-primary" />
                  ) : (
                    <File className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>

                <div className="flex flex-1 items-center justify-between gap-4 min-w-0">
                  <span
                    className={cn(
                      'truncate text-sm',
                      entry.is_directory
                        ? 'font-semibold text-card-foreground'
                        : 'text-card-foreground',
                    )}
                  >
                    {entry.name}
                  </span>

                  <div className="flex shrink-0 items-center gap-4 text-xs text-muted-foreground">
                    {!entry.is_directory && entry.size != null && (
                      <span>{formatFileSize(entry.size)}</span>
                    )}
                    {entry.modified_at && (
                      <span className="hidden sm:inline">
                        {new Date(entry.modified_at).toLocaleDateString()}
                      </span>
                    )}
                    {entry.is_directory && (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </div>
              </button>
            ))}

            {/* Empty state */}
            {browseData?.entries.length === 0 && (
              <div className="flex h-48 flex-col items-center justify-center gap-2 text-muted-foreground">
                <Folder className="h-10 w-10 opacity-30" />
                <p className="text-sm">{t('common.noData')}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
