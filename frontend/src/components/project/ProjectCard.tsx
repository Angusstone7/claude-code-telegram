// ---------------------------------------------------------------------------
// ProjectCard — displays a single project with name, path, and active badge
// ---------------------------------------------------------------------------

import { useTranslation } from 'react-i18next'
import { FolderOpen, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDate } from '@/lib/utils'
import type { ProjectResponse } from '@/types/api'

interface ProjectCardProps {
  project: ProjectResponse
  isActive: boolean
  onClick: (project: ProjectResponse) => void
  className?: string
}

export function ProjectCard({
  project,
  isActive,
  onClick,
  className,
}: ProjectCardProps) {
  const { t } = useTranslation()

  return (
    <button
      type="button"
      onClick={() => onClick(project)}
      className={cn(
        'w-full rounded-lg border p-4 text-left backdrop-blur-[14px] transition-colors duration-150',
        isActive
          ? 'border-primary/50 bg-accent'
          : 'border-border bg-card hover:border-primary/50',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className={cn(
              'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md',
              isActive
                ? 'bg-primary/20'
                : 'bg-muted',
            )}
          >
            <FolderOpen
              className={cn(
                'h-5 w-5',
                isActive
                  ? 'text-primary'
                  : 'text-muted-foreground',
              )}
            />
          </div>

          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-card-foreground">
              {project.name}
            </h3>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {project.path}
            </p>
            {project.created_at && (
              <p className="mt-1 text-xs text-muted-foreground">
                {formatDate(project.created_at)}
              </p>
            )}
          </div>
        </div>

        {isActive && (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
            <Check className="h-3 w-3" />
            {t('projects.activeProject')}
          </span>
        )}
      </div>

      {project.description && (
        <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
          {project.description}
        </p>
      )}
    </button>
  )
}
