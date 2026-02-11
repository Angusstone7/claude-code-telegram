import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  MonitorCheck,
  FolderOpen,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────

interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  memory_used_gb: number
  disk_percent: number
  load_avg_1m: number
  active_tasks: number
}

interface SystemInfo {
  bot_username: string | null
  python_version: string
  working_dir: string
  sdk_available: boolean
  cli_available: boolean
}

interface ProjectResponse {
  id: string
  name: string
  path: string
  description: string | null
  created_at: string
}

// ── Hooks ────────────────────────────────────────────────────────────────

function useMetrics() {
  return useQuery<SystemMetrics>({
    queryKey: ['system', 'metrics'],
    queryFn: async () => (await api.get<SystemMetrics>('/system/metrics')).data,
    refetchInterval: 10_000,
  })
}

function useSystemInfo() {
  return useQuery<SystemInfo>({
    queryKey: ['system', 'info'],
    queryFn: async () => (await api.get<SystemInfo>('/system/info')).data,
    staleTime: 60_000,
  })
}

function useProjects() {
  return useQuery<{ projects: ProjectResponse[]; total: number }>({
    queryKey: ['projects'],
    queryFn: async () =>
      (await api.get<{ projects: ProjectResponse[]; total: number }>('/projects'))
        .data,
  })
}

// ── Color mapping for metric cards ───────────────────────────────────────

const colorMap: Record<string, { bg: string; text: string; bar: string }> = {
  blue: { bg: 'bg-blue-500/20', text: 'text-blue-400', bar: 'bg-blue-500' },
  purple: { bg: 'bg-purple-500/20', text: 'text-purple-400', bar: 'bg-purple-500' },
  orange: { bg: 'bg-orange-500/20', text: 'text-orange-400', bar: 'bg-orange-500' },
  emerald: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', bar: 'bg-emerald-500' },
}

// ── Metric Card ──────────────────────────────────────────────────────────

function MetricCard({
  icon: Icon,
  label,
  value,
  percent,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  percent?: number
  color: string
}) {
  const c = colorMap[color] ?? colorMap.blue
  return (
    <div className="rounded-lg border border-border bg-card p-4 backdrop-blur-[14px] hover:border-primary/50 transition-colors duration-150">
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2.5 ${c.bg}`}>
          <Icon className={`h-5 w-5 ${c.text}`} />
        </div>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold text-card-foreground">{value}</p>
        </div>
      </div>
      {percent !== undefined && (
        <div className="mt-3">
          <div className="h-2.5 w-full rounded-full bg-muted">
            <div
              className={`h-2.5 rounded-full transition-all ${
                percent > 90
                  ? 'bg-red-500'
                  : percent > 70
                    ? 'bg-yellow-500'
                    : c.bar
              }`}
              style={{ width: `${Math.min(percent, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Status Badge ─────────────────────────────────────────────────────────

function StatusBadge({
  available,
  label,
}: {
  available: boolean
  label: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        available
          ? 'bg-green-500/15 text-green-400'
          : 'bg-red-500/15 text-red-400'
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${available ? 'bg-green-500' : 'bg-red-500'}`}
      />
      {label}
    </span>
  )
}

// ── Dashboard Page ───────────────────────────────────────────────────────

export function DashboardPage() {
  const { t } = useTranslation()
  const { data: metrics, isLoading: metricsLoading } = useMetrics()
  const { data: sysInfo } = useSystemInfo()
  const { data: projects } = useProjects()

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t('dashboard.title')}</h1>

      {/* System Metrics */}
      <section>
        <h2 className="mb-3 text-xl font-bold text-foreground">
          {t('dashboard.systemMetrics')}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            icon={Cpu}
            label={t('dashboard.cpu')}
            value={
              metricsLoading
                ? '...'
                : `${(metrics?.cpu_percent ?? 0).toFixed(1)}%`
            }
            percent={metrics?.cpu_percent}
            color="blue"
          />
          <MetricCard
            icon={MemoryStick}
            label={t('dashboard.ram')}
            value={
              metricsLoading
                ? '...'
                : `${(metrics?.memory_used_gb ?? 0).toFixed(1)} GB`
            }
            percent={metrics?.memory_percent}
            color="purple"
          />
          <MetricCard
            icon={HardDrive}
            label={t('dashboard.disk')}
            value={
              metricsLoading
                ? '...'
                : `${(metrics?.disk_percent ?? 0).toFixed(1)}%`
            }
            percent={metrics?.disk_percent}
            color="orange"
          />
          <MetricCard
            icon={Activity}
            label={t('dashboard.usageStats')}
            value={
              metricsLoading
                ? '...'
                : `${metrics?.active_tasks ?? 0} active`
            }
            color="emerald"
          />
        </div>
      </section>

      {/* Claude Status */}
      <section>
        <h2 className="mb-3 text-xl font-bold text-foreground">
          {t('dashboard.claudeStatus')}
        </h2>
        <div className="rounded-lg border border-border bg-card p-4 backdrop-blur-[14px]">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <MonitorCheck className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">SDK:</span>
              <StatusBadge
                available={sysInfo?.sdk_available ?? false}
                label={sysInfo?.sdk_available ? 'Online' : 'Offline'}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">CLI:</span>
              <StatusBadge
                available={sysInfo?.cli_available ?? false}
                label={sysInfo?.cli_available ? 'Online' : 'Offline'}
              />
            </div>
            {sysInfo?.python_version && (
              <span className="text-xs text-muted-foreground">
                Python {sysInfo.python_version}
              </span>
            )}
          </div>
        </div>
      </section>

      {/* Projects */}
      <section>
        <h2 className="mb-3 text-xl font-bold text-foreground">
          {t('dashboard.currentProject')}
        </h2>
        {projects && projects.projects.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.projects.slice(0, 6).map((p) => (
              <div
                key={p.id}
                className="flex items-start gap-3 rounded-lg border border-border bg-card p-4 backdrop-blur-[14px] hover:border-primary/50 transition-all duration-150 hover:-translate-y-0.5"
              >
                <FolderOpen className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div className="min-w-0">
                  <p className="font-medium text-card-foreground truncate">
                    {p.name}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {p.path}
                  </p>
                  {p.description && (
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                      {p.description}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border bg-card/50 p-6 text-center text-sm text-muted-foreground">
            {t('projects.noProjects')}
          </div>
        )}
      </section>
    </div>
  )
}
