import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import {
  Puzzle,
  ChevronDown,
  ChevronRight,
  Terminal,
  Globe,
  HardDrive,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────

interface PluginCommand {
  name: string
  description: string | null
}

interface Plugin {
  name: string
  enabled: boolean
  description: string | null
  source: string | null
  commands: PluginCommand[]
}

interface PluginListResponse {
  plugins: Plugin[]
  total: number
}

// ── Hook ─────────────────────────────────────────────────────────────────

function usePlugins() {
  return useQuery<PluginListResponse>({
    queryKey: ['plugins'],
    queryFn: async () => (await api.get<PluginListResponse>('/plugins')).data,
    staleTime: 30_000,
  })
}

// ── Plugin Card ──────────────────────────────────────────────────────────

function PluginCard({ plugin }: { plugin: Plugin }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const hasCommands = plugin.commands.length > 0

  return (
    <div className="rounded-lg border border-border bg-card transition-shadow hover:shadow-sm hover:border-primary/50 transition-colors duration-150">
      {/* Header */}
      <div
        className={`flex items-start gap-3 p-4 ${hasCommands ? 'cursor-pointer' : ''}`}
        onClick={() => hasCommands && setExpanded(!expanded)}
      >
        {/* Icon */}
        <div
          className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
            plugin.enabled
              ? 'bg-primary/20'
              : 'bg-secondary'
          }`}
        >
          <Puzzle
            className={`h-5 w-5 ${
              plugin.enabled
                ? 'text-primary'
                : 'text-muted-foreground'
            }`}
          />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-card-foreground">{plugin.name}</h3>

            {/* Enabled / Disabled badge */}
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                plugin.enabled
                  ? 'bg-green-500/15 text-green-400'
                  : 'bg-secondary text-muted-foreground'
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  plugin.enabled ? 'bg-green-500' : 'bg-muted-foreground'
                }`}
              />
              {plugin.enabled ? t('plugins.enabled') : t('plugins.disabled')}
            </span>

            {/* Source badge */}
            {plugin.source && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                {plugin.source === 'official' ? (
                  <Globe className="h-3 w-3" />
                ) : (
                  <HardDrive className="h-3 w-3" />
                )}
                {plugin.source}
              </span>
            )}
          </div>

          {plugin.description && (
            <p className="mt-1 text-sm text-muted-foreground">{plugin.description}</p>
          )}
        </div>

        {/* Expand arrow */}
        {hasCommands && (
          <div className="mt-1 shrink-0 text-muted-foreground">
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </div>
        )}
      </div>

      {/* Commands (collapsible) */}
      {expanded && hasCommands && (
        <div className="border-t border-border bg-muted/30 px-4 py-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {t('plugins.commands')}
          </p>
          <div className="space-y-1.5">
            {plugin.commands.map((cmd, idx) => (
              <div key={idx} className="flex items-start gap-2 text-sm">
                <Terminal className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <span className="font-mono text-card-foreground">/{cmd.name}</span>
                  {cmd.description && (
                    <span className="ml-2 text-muted-foreground">
                      &mdash; {cmd.description}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────

export function PluginsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = usePlugins()

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner message={t('common.loading')} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">{t('plugins.title')}</h1>
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {t('common.error')}: {(error as Error).message}
        </div>
      </div>
    )
  }

  const plugins = data?.plugins ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t('plugins.title')}</h1>
        <span className="text-sm text-muted-foreground">
          {plugins.filter((p) => p.enabled).length} / {plugins.length} {t('plugins.enabled').toLowerCase()}
        </span>
      </div>

      {plugins.length === 0 ? (
        <EmptyState
          title={t('plugins.noPlugins')}
          description="No Claude Code plugins found in the plugins directory."
          icon={Puzzle}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {plugins.map((plugin) => (
            <PluginCard key={plugin.name} plugin={plugin} />
          ))}
        </div>
      )}
    </div>
  )
}
