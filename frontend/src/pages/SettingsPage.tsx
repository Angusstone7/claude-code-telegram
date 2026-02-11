// ---------------------------------------------------------------------------
// SettingsPage — application settings management
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Settings,
  User,
  Monitor,
  Shield,
  Globe,
  Zap,
  Save,
  Loader2,
  CheckCircle,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSettingsStore } from '@/stores/settingsStore'
import { useAuthStore } from '@/stores/authStore'
import type { UpdateSettingsRequest } from '@/types/api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

// ── Component ────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const { t } = useTranslation()

  const user = useAuthStore((s) => s.user)
  const { settings, isLoading, error, fetchSettings, updateSettings } =
    useSettingsStore()

  // Local form state
  const [formState, setFormState] = useState<UpdateSettingsRequest>({})
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Load settings on mount
  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  // Sync form state when settings arrive
  useEffect(() => {
    if (settings) {
      setFormState({
        yolo_mode: settings.yolo_mode,
        step_streaming: settings.step_streaming,
        backend: settings.backend,
        model: settings.model,
        permission_mode: settings.permission_mode,
        language: settings.language,
      })
    }
  }, [settings])

  // Auto-dismiss success notification
  useEffect(() => {
    if (saveStatus === 'success') {
      const timer = setTimeout(() => setSaveStatus('idle'), 3000)
      return () => clearTimeout(timer)
    }
  }, [saveStatus])

  const handleSave = useCallback(async () => {
    setSaveStatus('saving')
    try {
      await updateSettings(formState)
      setSaveStatus('success')
    } catch {
      setSaveStatus('error')
    }
  }, [formState, updateSettings])

  const updateField = useCallback(
    <K extends keyof UpdateSettingsRequest>(key: K, value: UpdateSettingsRequest[K]) => {
      setFormState((prev) => ({ ...prev, [key]: value }))
    },
    [],
  )

  // ── Loading state ────────────────────────────────────────────────────────

  if (isLoading && !settings) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <LoadingSpinner message={t('common.loading')} />
      </div>
    )
  }

  if (error && !settings) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-red-500">
        <AlertCircle className="h-8 w-8" />
        <p className="text-sm">{error}</p>
      </div>
    )
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/50">
            <Settings className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-card-foreground">
            {t('settings.title')}
          </h1>
        </div>

        <button
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
          className={cn(
            'inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium',
            'bg-blue-600 text-white hover:bg-blue-700',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'transition-colors',
          )}
        >
          {saveStatus === 'saving' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {t('common.save')}
        </button>
      </div>

      {/* Success/Error notification */}
      {saveStatus === 'success' && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-900/30 dark:text-green-200">
          <CheckCircle className="h-4 w-4" />
          {t('settings.saved')}
        </div>
      )}
      {saveStatus === 'error' && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200">
          <AlertCircle className="h-4 w-4" />
          {error ?? t('common.error')}
        </div>
      )}

      {/* ── Profile Section ────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <User className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.profile')}
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('settings.displayName')}
            </label>
            <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
              {user?.display_name ?? '-'}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('settings.telegramId')}
            </label>
            <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
              {user?.telegram_id ?? '-'}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('common.username')}
            </label>
            <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
              {user?.username ?? '-'}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('common.role')}
            </label>
            <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
              {user?.role ?? '-'}
            </div>
          </div>
        </div>
      </section>

      {/* ── Claude Backend Section ─────────────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Monitor className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.claudeBackend')}
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          {/* Backend selector */}
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('settings.claudeBackend')}
            </label>
            <div className="flex gap-2">
              {(['sdk', 'cli'] as const).map((opt) => (
                <button
                  key={opt}
                  onClick={() => updateField('backend', opt)}
                  className={cn(
                    'flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                    formState.backend === opt
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                      : 'border-border bg-background text-muted-foreground hover:bg-accent',
                  )}
                >
                  {opt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Model selector */}
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('settings.model')}
            </label>
            <select
              value={formState.model ?? ''}
              onChange={(e) => updateField('model', e.target.value)}
              className={cn(
                'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm',
                'text-card-foreground',
                'focus:outline-none focus:ring-2 focus:ring-blue-500',
              )}
            >
              {settings?.available_models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* ── Permission & YOLO Section ──────────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.permissionMode')}
          </h2>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          {/* Permission mode */}
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('settings.permissionMode')}
            </label>
            <div className="flex gap-2">
              {(['default', 'auto', 'never'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => updateField('permission_mode', mode)}
                  className={cn(
                    'flex-1 rounded-lg border px-3 py-2 text-sm font-medium capitalize transition-colors',
                    formState.permission_mode === mode
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                      : 'border-border bg-background text-muted-foreground hover:bg-accent',
                  )}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* YOLO mode toggle */}
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t('settings.yoloMode')}
            </label>
            <button
              onClick={() => updateField('yolo_mode', !formState.yolo_mode)}
              className={cn(
                'flex items-center gap-3 rounded-lg border px-4 py-2 text-sm font-medium transition-colors w-full',
                formState.yolo_mode
                  ? 'border-yellow-500 bg-yellow-50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300'
                  : 'border-border bg-background text-muted-foreground hover:bg-accent',
              )}
            >
              <Zap className={cn('h-4 w-4', formState.yolo_mode ? 'text-yellow-500' : '')} />
              <span className="flex-1 text-left">
                {formState.yolo_mode ? 'ON' : 'OFF'}
              </span>
              <div
                className={cn(
                  'h-6 w-11 rounded-full transition-colors',
                  formState.yolo_mode ? 'bg-yellow-500' : 'bg-gray-300 dark:bg-gray-600',
                )}
              >
                <div
                  className={cn(
                    'h-5 w-5 translate-y-0.5 rounded-full bg-white shadow-sm transition-transform',
                    formState.yolo_mode ? 'translate-x-5' : 'translate-x-0.5',
                  )}
                />
              </div>
            </button>
          </div>
        </div>
      </section>

      {/* ── Language Section ────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.language')}
          </h2>
        </div>
        <div className="flex gap-2">
          {([
            { code: 'ru', label: 'Русский' },
            { code: 'en', label: 'English' },
            { code: 'zh', label: '中文' },
          ] as const).map((lang) => (
            <button
              key={lang.code}
              onClick={() => updateField('language', lang.code)}
              className={cn(
                'flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors',
                formState.language === lang.code
                  ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  : 'border-border bg-background text-muted-foreground hover:bg-accent',
              )}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}
