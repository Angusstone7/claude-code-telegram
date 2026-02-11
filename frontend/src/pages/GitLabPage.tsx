// ---------------------------------------------------------------------------
// GitLabPage — GitLab projects list + CI/CD pipelines viewer
// ---------------------------------------------------------------------------

import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  GitBranch,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  CircleDot,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  GitlabIcon,
  SkipForward,
  Hand,
  AlertTriangle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDate } from '@/lib/utils'
import { api } from '@/services/api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import type {
  GitLabProjectListResponse,
  GitLabProjectResponse,
  PipelineListResponse,
  PipelineResponse,
  PipelineStageResponse,
} from '@/types/api'

// ── Status helpers ──────────────────────────────────────────────────────────

type PipelineStatus = 'success' | 'failed' | 'running' | 'pending' | 'skipped' | 'manual' | 'canceled' | string

const STATUS_CONFIG: Record<
  string,
  { color: string; bg: string; icon: React.ComponentType<{ className?: string }>; label: string }
> = {
  success: {
    color: 'text-green-400',
    bg: 'bg-green-500/15',
    icon: CheckCircle2,
    label: 'gitlab.success',
  },
  failed: {
    color: 'text-red-400',
    bg: 'bg-red-500/15',
    icon: XCircle,
    label: 'gitlab.failed',
  },
  running: {
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/15',
    icon: Loader2,
    label: 'gitlab.running',
  },
  pending: {
    color: 'text-muted-foreground',
    bg: 'bg-secondary',
    icon: Clock,
    label: 'gitlab.pending',
  },
  created: {
    color: 'text-muted-foreground',
    bg: 'bg-secondary',
    icon: Clock,
    label: 'gitlab.pending',
  },
  skipped: {
    color: 'text-slate-400',
    bg: 'bg-slate-500/15',
    icon: SkipForward,
    label: 'gitlab.skipped',
  },
  manual: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/15',
    icon: Hand,
    label: 'gitlab.manual',
  },
  canceled: {
    color: 'text-muted-foreground',
    bg: 'bg-secondary',
    icon: XCircle,
    label: 'gitlab.failed',
  },
}

function getStatusConfig(status: PipelineStatus) {
  return (
    STATUS_CONFIG[status] ?? {
      color: 'text-muted-foreground',
      bg: 'bg-secondary',
      icon: CircleDot,
      label: 'common.status',
    }
  )
}

// ── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({ status, size = 'md' }: { status: string; size?: 'sm' | 'md' }) {
  const { t } = useTranslation()
  const cfg = getStatusConfig(status)
  const Icon = cfg.icon
  const isAnimated = status === 'running'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-medium',
        cfg.bg,
        cfg.color,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
      )}
    >
      <Icon className={cn(size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5', isAnimated && 'animate-spin')} />
      {t(cfg.label)}
    </span>
  )
}

// ── Stage dot (compact indicator) ───────────────────────────────────────────

function StageDot({ stage }: { stage: PipelineStageResponse }) {
  const { t } = useTranslation()
  const cfg = getStatusConfig(stage.status)

  return (
    <div className="group relative flex flex-col items-center">
      <div className={cn('h-3 w-3 rounded-full border-2', cfg.bg, cfg.color.replace('text-', 'border-'))} />
      {/* Tooltip */}
      <div
        className={cn(
          'pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap',
          'rounded bg-popover text-popover-foreground px-2 py-1 text-xs shadow-lg',
          'opacity-0 transition-opacity group-hover:opacity-100',
        )}
      >
        {stage.name}: {t(getStatusConfig(stage.status).label)}
      </div>
    </div>
  )
}

// ── Query keys ──────────────────────────────────────────────────────────────

const gitlabKeys = {
  all: ['gitlab'] as const,
  projects: () => [...gitlabKeys.all, 'projects'] as const,
  pipelines: (projectId: number) => [...gitlabKeys.all, 'pipelines', projectId] as const,
  stages: (projectId: number, pipelineId: number) =>
    [...gitlabKeys.all, 'stages', projectId, pipelineId] as const,
}

// ── Pipeline row ────────────────────────────────────────────────────────────

function PipelineRow({ pipeline, projectId }: { pipeline: PipelineResponse; projectId: number }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  const stagesQuery = useQuery({
    queryKey: gitlabKeys.stages(projectId, pipeline.id),
    queryFn: async () => {
      const { data } = await api.get<PipelineStageResponse[]>(
        `/gitlab/projects/${projectId}/pipelines/${pipeline.id}/stages`,
      )
      return data
    },
    enabled: expanded,
  })

  return (
    <div className="border-b border-border last:border-b-0">
      {/* Pipeline summary */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={cn(
          'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors',
          'hover:bg-muted/50',
          expanded && 'bg-muted/30',
        )}
      >
        {/* Expand icon */}
        <span className="shrink-0 text-muted-foreground">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>

        {/* Pipeline ID */}
        <span className="shrink-0 text-sm font-mono font-medium text-muted-foreground">#{pipeline.id}</span>

        {/* Status badge */}
        <StatusBadge status={pipeline.status} />

        {/* Branch */}
        <span className="flex shrink-0 items-center gap-1 text-sm text-card-foreground">
          <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="max-w-[140px] truncate">{pipeline.ref}</span>
        </span>

        {/* SHA (truncated) */}
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{pipeline.sha.slice(0, 8)}</span>

        {/* Spacer */}
        <span className="flex-1" />

        {/* Date */}
        <span className="shrink-0 text-xs text-muted-foreground">{formatDate(pipeline.created_at)}</span>

        {/* External link */}
        {pipeline.web_url && (
          <a
            href={pipeline.web_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 text-muted-foreground hover:text-card-foreground transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </button>

      {/* Expanded stages */}
      {expanded && (
        <div className="border-t border-border/50 bg-muted/20 px-4 py-3">
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {t('gitlab.stages')}
          </h4>

          {stagesQuery.isLoading && (
            <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('common.loading')}
            </div>
          )}

          {stagesQuery.isError && (
            <div className="flex items-center gap-2 py-2 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {t('gitlab.loadError')}
            </div>
          )}

          {stagesQuery.data && stagesQuery.data.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {stagesQuery.data.map((stage) => (
                <div
                  key={stage.name}
                  className={cn(
                    'flex items-center gap-1.5 rounded-md px-2.5 py-1.5',
                    'border border-border bg-card text-xs font-medium',
                  )}
                >
                  <StageDot stage={stage} />
                  <span className="text-card-foreground">{stage.name}</span>
                  <StatusBadge status={stage.status} size="sm" />
                </div>
              ))}
            </div>
          )}

          {stagesQuery.data && stagesQuery.data.length === 0 && (
            <p className="py-2 text-sm text-muted-foreground">{t('common.noData')}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Project list item ───────────────────────────────────────────────────────

function ProjectItem({
  project,
  isSelected,
  onClick,
}: {
  project: GitLabProjectResponse
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex w-full flex-col gap-1 rounded-lg px-3 py-2.5 text-left transition-colors',
        isSelected
          ? 'bg-primary/10 ring-1 ring-primary/30'
          : 'hover:bg-muted/50',
      )}
    >
      <span className="text-sm font-medium text-card-foreground truncate">{project.name}</span>
      <span className="text-xs text-muted-foreground truncate">{project.path_with_namespace}</span>
      {project.default_branch && (
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <GitBranch className="h-3 w-3" />
          {project.default_branch}
        </span>
      )}
    </button>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────

export function GitLabPage() {
  const { t } = useTranslation()
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)

  // Fetch projects
  const projectsQuery = useQuery({
    queryKey: gitlabKeys.projects(),
    queryFn: async () => {
      const { data } = await api.get<GitLabProjectListResponse>('/gitlab/projects')
      return data
    },
  })

  // Fetch pipelines for selected project
  const pipelinesQuery = useQuery({
    queryKey: gitlabKeys.pipelines(selectedProjectId ?? 0),
    queryFn: async () => {
      const { data } = await api.get<PipelineListResponse>(
        `/gitlab/projects/${selectedProjectId}/pipelines`,
        { params: { limit: 20 } },
      )
      return data
    },
    enabled: selectedProjectId !== null,
    // Auto-refresh when there are running pipelines
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.pipelines?.some((p) => p.status === 'running' || p.status === 'pending')) {
        return 15000
      }
      return false
    },
  })

  const selectedProject = useMemo(
    () => projectsQuery.data?.projects.find((p) => p.id === selectedProjectId) ?? null,
    [projectsQuery.data, selectedProjectId],
  )

  return (
    <div className="flex h-full flex-col gap-6 p-6 lg:flex-row">
      {/* Left panel — GitLab projects */}
      <div className="w-full shrink-0 lg:w-80 xl:w-96">
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-card-foreground">
            <GitlabIcon className="h-5 w-5 text-orange-500" />
            {t('gitlab.projects')}
          </h2>

          {projectsQuery.isLoading && (
            <LoadingSpinner message={t('common.loading')} className="py-8" />
          )}

          {projectsQuery.isError && (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <AlertTriangle className="h-8 w-8 text-red-500" />
              <p className="text-sm text-destructive">{t('gitlab.loadError')}</p>
              <p className="text-xs text-muted-foreground">
                {(projectsQuery.error as Error)?.message ?? ''}
              </p>
            </div>
          )}

          {projectsQuery.data && projectsQuery.data.projects.length === 0 && (
            <EmptyState
              title={t('gitlab.noProjects')}
              description={t('gitlab.noProjectsDescription')}
              icon={GitlabIcon}
              className="py-8"
            />
          )}

          {projectsQuery.data && projectsQuery.data.projects.length > 0 && (
            <div className="flex flex-col gap-1 max-h-[calc(100vh-220px)] overflow-y-auto">
              {projectsQuery.data.projects.map((project) => (
                <ProjectItem
                  key={project.id}
                  project={project}
                  isSelected={selectedProjectId === project.id}
                  onClick={() => setSelectedProjectId(project.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right panel — pipelines for selected project */}
      <div className="flex-1 min-w-0">
        {selectedProject ? (
          <div className="space-y-4">
            {/* Project header */}
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-orange-500/20">
                    <GitlabIcon className="h-5 w-5 text-orange-400" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold text-card-foreground">
                      {selectedProject.name}
                    </h2>
                    <p className="truncate text-sm text-muted-foreground">
                      {selectedProject.path_with_namespace}
                    </p>
                  </div>
                </div>
                <a
                  href={selectedProject.web_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm',
                    'border border-border bg-background text-card-foreground',
                    'hover:bg-muted transition-colors',
                  )}
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  GitLab
                </a>
              </div>
            </div>

            {/* Pipelines */}
            <div className="rounded-xl border border-border bg-card shadow-sm">
              <div className="border-b border-border px-4 py-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-card-foreground">
                  <CircleDot className="h-4 w-4 text-muted-foreground" />
                  {t('gitlab.pipelines')}
                  {pipelinesQuery.data && (
                    <span className="text-xs font-normal text-muted-foreground">
                      ({pipelinesQuery.data.total})
                    </span>
                  )}
                  {/* Running indicator */}
                  {pipelinesQuery.data?.pipelines?.some(
                    (p) => p.status === 'running' || p.status === 'pending',
                  ) && (
                    <span className="ml-auto flex items-center gap-1 text-xs text-yellow-400">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Auto-refresh
                    </span>
                  )}
                </h3>
              </div>

              {pipelinesQuery.isLoading && (
                <LoadingSpinner message={t('common.loading')} className="py-12" />
              )}

              {pipelinesQuery.isError && (
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                  <AlertTriangle className="h-8 w-8 text-red-500" />
                  <p className="text-sm text-destructive">{t('gitlab.loadError')}</p>
                </div>
              )}

              {pipelinesQuery.data && pipelinesQuery.data.pipelines.length === 0 && (
                <EmptyState
                  title={t('gitlab.noPipelines')}
                  description={t('gitlab.noPipelinesDescription')}
                  icon={CircleDot}
                  className="py-12"
                />
              )}

              {pipelinesQuery.data && pipelinesQuery.data.pipelines.length > 0 && (
                <div className="max-h-[calc(100vh-320px)] overflow-y-auto">
                  {pipelinesQuery.data.pipelines.map((pipeline) => (
                    <PipelineRow
                      key={pipeline.id}
                      pipeline={pipeline}
                      projectId={selectedProjectId!}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div
            className={cn(
              'flex h-full min-h-[400px] flex-col items-center justify-center',
              'rounded-xl border border-dashed border-border bg-card/50 p-12 text-center',
            )}
          >
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-secondary">
              <GitlabIcon className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-card-foreground">
              {t('gitlab.selectProject')}
            </h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              {t('gitlab.selectProjectDescription')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
