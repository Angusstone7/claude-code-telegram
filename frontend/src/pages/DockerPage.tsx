import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { cn } from '@/lib/utils'
import {
  Box,
  Cpu,
  HardDrive,
  MemoryStick,
  Play,
  Square,
  RotateCw,
  ScrollText,
  X,
  Container,
} from 'lucide-react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import type {
  ContainerListResponse,
  ContainerResponse,
  ContainerActionResponse,
  ContainerLogsResponse,
  SystemMetrics,
} from '@/types/api'

// ── Query keys ──────────────────────────────────────────────────────────

const dockerKeys = {
  all: ['docker'] as const,
  containers: () => [...dockerKeys.all, 'containers'] as const,
  logs: (name: string) => [...dockerKeys.all, 'logs', name] as const,
}

const metricsKey = ['system', 'metrics'] as const

// ── Hooks ───────────────────────────────────────────────────────────────

function useContainers() {
  return useQuery<ContainerListResponse>({
    queryKey: dockerKeys.containers(),
    queryFn: async () =>
      (await api.get<ContainerListResponse>('/docker/containers')).data,
    refetchInterval: 30_000,
  })
}

function useContainerLogs(name: string | null) {
  return useQuery<ContainerLogsResponse>({
    queryKey: dockerKeys.logs(name ?? ''),
    queryFn: async () =>
      (
        await api.get<ContainerLogsResponse>(
          `/docker/containers/${name}/logs`,
          { params: { tail: 200 } },
        )
      ).data,
    enabled: name !== null,
    refetchInterval: 10_000,
  })
}

function useContainerAction() {
  const queryClient = useQueryClient()

  return useMutation<
    ContainerActionResponse,
    Error,
    { name: string; action: 'start' | 'stop' | 'restart' }
  >({
    mutationFn: async ({ name, action }) => {
      const { data } = await api.post<ContainerActionResponse>(
        `/docker/containers/${name}/${action}`,
      )
      return data
    },
    onSuccess: () => {
      // Refresh container list after action
      queryClient.invalidateQueries({ queryKey: dockerKeys.containers() })
    },
  })
}

function useSystemMetrics() {
  return useQuery<SystemMetrics>({
    queryKey: metricsKey,
    queryFn: async () =>
      (await api.get<SystemMetrics>('/system/metrics')).data,
    refetchInterval: 30_000,
  })
}

// ── Status badge ────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()

  const normalized = status.toLowerCase()

  const config: Record<string, { label: string; classes: string; dot: string }> =
    {
      running: {
        label: t('docker.running'),
        classes:
          'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
        dot: 'bg-green-500',
      },
      exited: {
        label: t('docker.exited'),
        classes:
          'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
        dot: 'bg-red-500',
      },
      restarting: {
        label: t('docker.restarting'),
        classes:
          'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
        dot: 'bg-yellow-500',
      },
    }

  const cfg = config[normalized] ?? {
    label: status,
    classes:
      'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
    dot: 'bg-gray-500',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        cfg.classes,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

// ── Metric bar ──────────────────────────────────────────────────────────

function MetricBar({
  icon: Icon,
  label,
  value,
  percent,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  percent: number
  color: string
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-3">
        <div className={cn('rounded-md p-2', color)}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-xl font-semibold text-card-foreground">{value}</p>
        </div>
      </div>
      <div className="mt-3">
        <div className="h-2 w-full rounded-full bg-muted">
          <div
            className={cn(
              'h-2 rounded-full transition-all',
              percent > 90
                ? 'bg-red-500'
                : percent > 70
                  ? 'bg-yellow-500'
                  : 'bg-green-500',
            )}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}

// ── Logs modal ──────────────────────────────────────────────────────────

function LogsPanel({
  containerName,
  onClose,
}: {
  containerName: string
  onClose: () => void
}) {
  const { t } = useTranslation()
  const { data, isLoading } = useContainerLogs(containerName)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[80vh] w-full max-w-4xl flex-col rounded-lg border border-border bg-card shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <ScrollText className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-base font-semibold text-card-foreground">
              {t('docker.logs')} &mdash; {containerName}
            </h3>
            {data && (
              <span className="text-xs text-muted-foreground">
                ({data.lines} lines)
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            title={t('docker.closeLogs')}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-4">
          {isLoading ? (
            <LoadingSpinner message={t('common.loading')} className="py-12" />
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-card-foreground">
              {data?.logs || t('common.noData')}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Container row ───────────────────────────────────────────────────────

function ContainerRow({
  container,
  onViewLogs,
}: {
  container: ContainerResponse
  onViewLogs: (name: string) => void
}) {
  const { t } = useTranslation()
  const action = useContainerAction()
  const isRunning = container.status.toLowerCase() === 'running'

  return (
    <tr className="border-b border-border last:border-b-0 hover:bg-muted/50 transition-colors">
      {/* Name */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <Box className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="font-medium text-card-foreground truncate max-w-[200px]">
            {container.name}
          </span>
        </div>
      </td>

      {/* Image */}
      <td className="px-4 py-3">
        <span className="text-sm text-muted-foreground truncate block max-w-[250px]">
          {container.image}
        </span>
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <StatusBadge status={container.status} />
      </td>

      {/* Ports */}
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {container.ports.length > 0 ? (
            container.ports.map((p, i) => (
              <span
                key={i}
                className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-muted-foreground"
              >
                {p}
              </span>
            ))
          ) : (
            <span className="text-xs text-muted-foreground">&mdash;</span>
          )}
        </div>
      </td>

      {/* Uptime */}
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {container.uptime ?? '\u2014'}
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          {!isRunning && (
            <button
              onClick={() =>
                action.mutate({ name: container.name, action: 'start' })
              }
              disabled={action.isPending}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-100 dark:text-green-400 dark:hover:bg-green-900/30 disabled:opacity-50"
              title={t('docker.start')}
            >
              <Play className="h-3.5 w-3.5" />
              {t('docker.start')}
            </button>
          )}
          {isRunning && (
            <button
              onClick={() =>
                action.mutate({ name: container.name, action: 'stop' })
              }
              disabled={action.isPending}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-900/30 disabled:opacity-50"
              title={t('docker.stop')}
            >
              <Square className="h-3.5 w-3.5" />
              {t('docker.stop')}
            </button>
          )}
          <button
            onClick={() =>
              action.mutate({ name: container.name, action: 'restart' })
            }
            disabled={action.isPending}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-orange-700 hover:bg-orange-100 dark:text-orange-400 dark:hover:bg-orange-900/30 disabled:opacity-50"
            title={t('docker.restart')}
          >
            <RotateCw className="h-3.5 w-3.5" />
            {t('docker.restart')}
          </button>
          <button
            onClick={() => onViewLogs(container.name)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900/30"
            title={t('docker.logs')}
          >
            <ScrollText className="h-3.5 w-3.5" />
            {t('docker.logs')}
          </button>
        </div>
      </td>
    </tr>
  )
}

// ── Docker Page ─────────────────────────────────────────────────────────

export function DockerPage() {
  const { t } = useTranslation()
  const [logsContainer, setLogsContainer] = useState<string | null>(null)

  const { data: containerData, isLoading: containersLoading } = useContainers()
  const { data: metrics, isLoading: metricsLoading } = useSystemMetrics()

  const containers = containerData?.containers ?? []

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t('docker.title')}</h1>

      {/* System Metrics */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-foreground">
          {t('docker.systemMetrics')}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricBar
            icon={Cpu}
            label={t('docker.cpu')}
            value={
              metricsLoading
                ? '...'
                : `${(metrics?.cpu_percent ?? 0).toFixed(1)}%`
            }
            percent={metrics?.cpu_percent ?? 0}
            color="bg-blue-600"
          />
          <MetricBar
            icon={MemoryStick}
            label={t('docker.ram')}
            value={
              metricsLoading
                ? '...'
                : `${(metrics?.memory_used_gb ?? 0).toFixed(1)} GB (${(metrics?.memory_percent ?? 0).toFixed(0)}%)`
            }
            percent={metrics?.memory_percent ?? 0}
            color="bg-purple-600"
          />
          <MetricBar
            icon={HardDrive}
            label={t('docker.disk')}
            value={
              metricsLoading
                ? '...'
                : `${(metrics?.disk_percent ?? 0).toFixed(1)}%`
            }
            percent={metrics?.disk_percent ?? 0}
            color="bg-orange-600"
          />
        </div>
      </section>

      {/* Container Table */}
      <section>
        <h2 className="mb-3 text-lg font-semibold text-foreground">
          {t('docker.containers')}
          {containerData && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              ({containerData.total})
            </span>
          )}
        </h2>

        {containersLoading ? (
          <LoadingSpinner message={t('common.loading')} className="py-12" />
        ) : containers.length === 0 ? (
          <EmptyState
            icon={Container}
            title={t('docker.noContainers')}
            description={t('docker.noContainersDescription')}
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border bg-card">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-4 py-3 font-medium text-muted-foreground">
                    {t('common.name')}
                  </th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">
                    {t('docker.image')}
                  </th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">
                    {t('docker.status')}
                  </th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">
                    {t('docker.ports')}
                  </th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">
                    {t('docker.uptime')}
                  </th>
                  <th className="px-4 py-3 font-medium text-muted-foreground">
                    {t('common.actions')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {containers.map((c) => (
                  <ContainerRow
                    key={c.name}
                    container={c}
                    onViewLogs={setLogsContainer}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Logs Modal */}
      {logsContainer && (
        <LogsPanel
          containerName={logsContainer}
          onClose={() => setLogsContainer(null)}
        />
      )}
    </div>
  )
}
