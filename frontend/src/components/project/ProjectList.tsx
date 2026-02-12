// ---------------------------------------------------------------------------
// ProjectList — renders a list of projects with create project functionality
// ---------------------------------------------------------------------------

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, FolderOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProjects, useCreateProject, useActivateProject } from '@/hooks/useProjects'
import { useProjectStore } from '@/stores/projectStore'
import { ProjectCard } from './ProjectCard'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import type { ProjectResponse } from '@/types/api'

interface ProjectListProps {
  className?: string
}

export function ProjectList({ className }: ProjectListProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useProjects()
  const createProject = useCreateProject()
  const activateProject = useActivateProject()
  const activeProject = useProjectStore((s) => s.activeProject)
  const setActiveProject = useProjectStore((s) => s.setActiveProject)

  const [showForm, setShowForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPath, setNewPath] = useState('')
  const [newDescription, setNewDescription] = useState('')

  const projects = data?.projects ?? []

  const handleActivate = (project: ProjectResponse) => {
    setActiveProject(project)
    activateProject.mutate(project.id)
  }

  const handleCreate = () => {
    if (!newName.trim() || !newPath.trim()) return

    createProject.mutate(
      {
        name: newName.trim(),
        path: newPath.trim(),
        description: newDescription.trim() || undefined,
      },
      {
        onSuccess: (created) => {
          setActiveProject(created)
          setNewName('')
          setNewPath('')
          setNewDescription('')
          setShowForm(false)
        },
      },
    )
  }

  const handleCancelCreate = () => {
    setNewName('')
    setNewPath('')
    setNewDescription('')
    setShowForm(false)
  }

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center py-12', className)}>
        <LoadingSpinner message={t('common.loading')} />
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-card-foreground">
          {t('projects.title')}
        </h2>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t('projects.createProject')}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold text-card-foreground">
            {t('projects.createProject')}
          </h3>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="project-name"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t('common.name')}
              </label>
              <input
                id="project-name"
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="my-project"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
            </div>
            <div>
              <label
                htmlFor="project-path"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t('projects.workingDir')}
              </label>
              <input
                id="project-path"
                type="text"
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                placeholder="/root/projects/my-project"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
            </div>
            <div>
              <label
                htmlFor="project-desc"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t('common.description')}
              </label>
              <input
                id="project-desc"
                type="text"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder={t('common.description')}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCreate}
                disabled={createProject.isPending || !newName.trim() || !newPath.trim()}
                className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {t('common.create')}
              </button>
              <button
                type="button"
                onClick={handleCancelCreate}
                className="inline-flex items-center rounded-xl border border-border px-3 py-2 text-sm font-medium text-card-foreground hover:bg-accent transition-colors"
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Project list */}
      {projects.length === 0 ? (
        <EmptyState
          title={t('projects.noProjects')}
          description={t('projects.noProjectsDescription')}
          icon={FolderOpen}
        />
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              isActive={activeProject?.id === project.id}
              onClick={handleActivate}
            />
          ))}
        </div>
      )}
    </div>
  )
}
