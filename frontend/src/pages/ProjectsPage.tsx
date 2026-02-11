// ---------------------------------------------------------------------------
// ProjectsPage — full project management page with contexts and variables
// ---------------------------------------------------------------------------

import { useTranslation } from 'react-i18next'
import { FolderOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProjectStore } from '@/stores/projectStore'
import { ProjectList } from '@/components/project/ProjectList'
import { ContextList } from '@/components/project/ContextList'
import { VariableManager } from '@/components/project/VariableManager'

export function ProjectsPage() {
  const { t } = useTranslation()
  const activeProject = useProjectStore((s) => s.activeProject)

  return (
    <div className="flex h-full flex-col gap-6 p-6 lg:flex-row">
      {/* Left panel — project list */}
      <div className="w-full shrink-0 lg:w-80 xl:w-96">
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <ProjectList />
        </div>
      </div>

      {/* Right panel — contexts + variables for selected project */}
      <div className="flex-1 min-w-0">
        {activeProject ? (
          <div className="space-y-6">
            {/* Project header */}
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/50">
                  <FolderOpen className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold text-card-foreground">
                    {activeProject.name}
                  </h2>
                  <p className="truncate text-sm text-muted-foreground">
                    {activeProject.path}
                  </p>
                </div>
              </div>
              {activeProject.description && (
                <p className="mt-3 text-sm text-muted-foreground">
                  {activeProject.description}
                </p>
              )}
            </div>

            {/* Contexts */}
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <ContextList projectId={activeProject.id} />
            </div>

            {/* Variables */}
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <VariableManager projectId={activeProject.id} />
            </div>
          </div>
        ) : (
          <div
            className={cn(
              'flex h-full min-h-[400px] flex-col items-center justify-center',
              'rounded-xl border border-dashed border-border bg-card/50 p-12 text-center',
            )}
          >
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800">
              <FolderOpen className="h-8 w-8 text-gray-400" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-card-foreground">
              {t('projects.selectProjectTitle')}
            </h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              {t('projects.selectProjectDescription')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
