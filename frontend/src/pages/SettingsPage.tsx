// ---------------------------------------------------------------------------
// SettingsPage — application settings management
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
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
  Server,
  X,
  Plus,
  Eye,
  EyeOff,
  Key,
  Network,
  Wifi,
  Sliders,
  Timer,
  KeyRound,
  Lock,
  Wrench,
  ChevronDown,
  ChevronRight,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSettingsStore } from '@/stores/settingsStore'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/services/api'
import type {
  UpdateSettingsRequest,
  PluginResponse,
  ProxyConfigUpdate,
  RuntimeConfigUpdate,
  InfraConfigUpdate,
} from '@/types/api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

// ── Toast notification component ─────────────────────────────────────────

interface ToastData {
  id: number
  message: string
  type: 'success' | 'error'
}

let toastIdCounter = 0

function ToastContainer({ toasts, onDismiss }: { toasts: ToastData[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null
  return createPortal(
    <div className="fixed right-4 top-4 z-[9999] flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium shadow-lg backdrop-blur-md',
            'animate-in slide-in-from-right-5 fade-in duration-300',
            toast.type === 'success'
              ? 'border-[#4DFF88]/30 bg-[#4DFF88]/10 text-[#4DFF88]'
              : 'border-[#FF4D6A]/30 bg-[#FF4D6A]/10 text-[#FF4D6A]',
          )}
          style={{ minWidth: 260 }}
        >
          {toast.type === 'success' ? (
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
          ) : (
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
          )}
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => onDismiss(toast.id)}
            className="ml-2 flex-shrink-0 rounded-md p-0.5 opacity-60 hover:opacity-100 transition-opacity"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>,
    document.body,
  )
}

// ── Inline validation error component ────────────────────────────────────

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null
  return (
    <p className="mt-1 text-xs" style={{ color: '#FF4D6A' }}>
      {message}
    </p>
  )
}

// ── Validation helpers ───────────────────────────────────────────────────

function validateRange(value: number, min: number, max: number): boolean {
  return Number.isFinite(value) && value >= min && value <= max
}

// ── Component ────────────────────────────────────────────────────────────

export function SettingsPage() {
  const { t } = useTranslation()

  const user = useAuthStore((s) => s.user)
  const { settings, isLoading, error, fetchSettings, updateSettings, validateProvider, addCustomModel, removeCustomModel, testProxy, uploadCredentials } =
    useSettingsStore()

  // Local form state
  const [formState, setFormState] = useState<UpdateSettingsRequest>({})
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Toast state
  const [toasts, setToasts] = useState<ToastData[]>([])

  const addToast = useCallback((message: string, type: 'success' | 'error') => {
    const id = ++toastIdCounter
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3000)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Provider auth state
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [baseUrlInput, setBaseUrlInput] = useState('')
  const [localModelName, setLocalModelName] = useState('')
  const [localModelUrl, setLocalModelUrl] = useState('')
  const [validationStatus, setValidationStatus] = useState<'idle' | 'validating' | 'success' | 'error'>('idle')
  const [validationMessage, setValidationMessage] = useState('')

  // Custom model editor state
  const [showAddModel, setShowAddModel] = useState(false)
  const [newModelId, setNewModelId] = useState('')
  const [addingModel, setAddingModel] = useState(false)
  const [removingModelId, setRemovingModelId] = useState<string | null>(null)

  // T016 — Proxy Configuration state
  const [proxyEnabled, setProxyEnabled] = useState(false)
  const [proxyType, setProxyType] = useState<string>('http')
  const [proxyHost, setProxyHost] = useState('')
  const [proxyPort, setProxyPort] = useState<number>(8080)
  const [proxyUsername, setProxyUsername] = useState('')
  const [proxyPassword, setProxyPassword] = useState('')
  const [proxyNoProxy, setProxyNoProxy] = useState('')
  const [showProxyPassword, setShowProxyPassword] = useState(false)
  const [proxyTestStatus, setProxyTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')
  const [proxyTestMessage, setProxyTestMessage] = useState('')
  const [proxyTestLatency, setProxyTestLatency] = useState<number | null>(null)

  // T019 — Runtime Settings state
  const [runtimeMaxTurns, setRuntimeMaxTurns] = useState<number>(50)
  const [runtimeTimeout, setRuntimeTimeout] = useState<number>(600)
  const [runtimeStepStreaming, setRuntimeStepStreaming] = useState(false)

  // T019b — Plugins state
  const [plugins, setPlugins] = useState<PluginResponse[]>([])
  const [pluginsLoading, setPluginsLoading] = useState(false)

  // T022 — Claude Account state
  const [credentialsJson, setCredentialsJson] = useState('')
  const [credUploadStatus, setCredUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [credUploadMessage, setCredUploadMessage] = useState('')

  // T025 — Infrastructure state
  const [infraExpanded, setInfraExpanded] = useState(false)
  const [sshHost, setSshHost] = useState('')
  const [sshPort, setSshPort] = useState<number>(22)
  const [sshUser, setSshUser] = useState('root')
  const [gitlabUrl, setGitlabUrl] = useState('')
  const [gitlabToken, setGitlabToken] = useState('')
  const [showGitlabToken, setShowGitlabToken] = useState(false)
  const [alertCpu, setAlertCpu] = useState<number>(80)
  const [alertMemory, setAlertMemory] = useState<number>(80)
  const [alertDisk, setAlertDisk] = useState<number>(90)
  const [debugMode, setDebugMode] = useState(false)
  const [logLevel, setLogLevel] = useState<string>('INFO')

  // ── Validation errors (computed) ───────────────────────────────────────

  const validationErrors = useMemo(() => {
    const errors: Record<string, string> = {}

    // Runtime fields
    if (!validateRange(runtimeMaxTurns, 1, 999)) {
      errors.maxTurns = t('settings.validationErrorRange', { min: 1, max: 999 })
    }
    if (!validateRange(runtimeTimeout, 1, 99999)) {
      errors.timeout = t('settings.validationErrorRange', { min: 1, max: 99999 })
    }

    // Port fields
    if (!validateRange(proxyPort, 1, 65535)) {
      errors.proxyPort = t('settings.validationErrorPort')
    }
    if (!validateRange(sshPort, 1, 65535)) {
      errors.sshPort = t('settings.validationErrorPort')
    }

    // Alert thresholds
    if (!validateRange(alertCpu, 0, 100)) {
      errors.alertCpu = t('settings.validationErrorThreshold')
    }
    if (!validateRange(alertMemory, 0, 100)) {
      errors.alertMemory = t('settings.validationErrorThreshold')
    }
    if (!validateRange(alertDisk, 0, 100)) {
      errors.alertDisk = t('settings.validationErrorThreshold')
    }

    return errors
  }, [runtimeMaxTurns, runtimeTimeout, proxyPort, sshPort, alertCpu, alertMemory, alertDisk, t])

  const hasValidationErrors = Object.keys(validationErrors).length > 0

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
        provider: settings.provider,
        permission_mode: settings.permission_mode,
        language: settings.language,
      })
      // Sync provider auth fields
      if (settings.provider_config?.base_url) {
        setBaseUrlInput(settings.provider_config.base_url)
      }
      // Sync proxy fields
      if (settings.proxy) {
        setProxyEnabled(settings.proxy.enabled)
        setProxyType(settings.proxy.type)
        setProxyHost(settings.proxy.host)
        setProxyPort(settings.proxy.port)
        setProxyUsername(settings.proxy.username)
        setProxyNoProxy(settings.proxy.no_proxy)
      }
      // Sync runtime fields
      if (settings.runtime) {
        setRuntimeMaxTurns(settings.runtime.max_turns)
        setRuntimeTimeout(settings.runtime.timeout)
        setRuntimeStepStreaming(settings.runtime.step_streaming)
      }
      // Sync infra fields
      if (settings.infra) {
        setSshHost(settings.infra.ssh_host)
        setSshPort(settings.infra.ssh_port)
        setSshUser(settings.infra.ssh_user)
        setGitlabUrl(settings.infra.gitlab_url)
        setAlertCpu(settings.infra.alert_cpu)
        setAlertMemory(settings.infra.alert_memory)
        setAlertDisk(settings.infra.alert_disk)
        setDebugMode(settings.infra.debug)
        setLogLevel(settings.infra.log_level)
      }
    }
  }, [settings])

  // Fetch plugins on mount (T019b)
  useEffect(() => {
    const loadPlugins = async () => {
      setPluginsLoading(true)
      try {
        const { data } = await api.get<{ plugins: PluginResponse[] }>('/settings/plugins')
        setPlugins(data.plugins ?? [])
      } catch {
        // Plugins are optional
      } finally {
        setPluginsLoading(false)
      }
    }
    loadPlugins()
  }, [])

  // Auto-dismiss validation status
  useEffect(() => {
    if (validationStatus === 'success' || validationStatus === 'error') {
      const timer = setTimeout(() => {
        setValidationStatus('idle')
        setValidationMessage('')
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [validationStatus])

  const handleSave = useCallback(async () => {
    if (hasValidationErrors) {
      addToast(t('settings.hasValidationErrors'), 'error')
      return
    }
    setSaveStatus('saving')
    try {
      await updateSettings(formState)
      setSaveStatus('success')
      addToast(t('settings.saved'), 'success')
    } catch {
      setSaveStatus('error')
      addToast(t('settings.saveFailed'), 'error')
    }
  }, [formState, updateSettings, hasValidationErrors, addToast, t])

  const updateField = useCallback(
    <K extends keyof UpdateSettingsRequest>(key: K, value: UpdateSettingsRequest[K]) => {
      setFormState((prev) => ({ ...prev, [key]: value }))
    },
    [],
  )

  // Validate provider API key
  const handleValidate = useCallback(async () => {
    const provider = formState.provider ?? settings?.provider ?? 'anthropic'
    const key = apiKeyInput
    if (!key) return

    setValidationStatus('validating')
    setValidationMessage('')
    try {
      const result = await validateProvider({
        provider,
        api_key: key,
        base_url: provider === 'anthropic' ? undefined : (baseUrlInput || undefined),
      })
      if (result.valid) {
        setValidationStatus('success')
        setValidationMessage(result.message)
      } else {
        setValidationStatus('error')
        setValidationMessage(result.message)
      }
    } catch {
      setValidationStatus('error')
      setValidationMessage(t('settings.validationFailed'))
    }
  }, [formState.provider, settings?.provider, apiKeyInput, baseUrlInput, validateProvider, t])

  // Add a custom model
  const handleAddCustomModel = useCallback(async () => {
    const provider = formState.provider ?? settings?.provider ?? 'anthropic'
    const modelId = newModelId.trim()
    if (!modelId) return

    setAddingModel(true)
    try {
      await addCustomModel(provider, modelId)
      setNewModelId('')
      setShowAddModel(false)
    } catch {
      // Error handled by store
    } finally {
      setAddingModel(false)
    }
  }, [formState.provider, settings?.provider, newModelId, addCustomModel])

  // Remove a custom model
  const handleRemoveCustomModel = useCallback(async (modelId: string) => {
    const provider = formState.provider ?? settings?.provider ?? 'anthropic'
    setRemovingModelId(modelId)
    try {
      await removeCustomModel(provider, modelId)
    } catch {
      // Error handled by store
    } finally {
      setRemovingModelId(null)
    }
  }, [formState.provider, settings?.provider, removeCustomModel])

  // T016 — Save proxy settings
  const handleSaveProxy = useCallback(async () => {
    if (validationErrors.proxyPort) {
      addToast(validationErrors.proxyPort, 'error')
      return
    }
    const proxyUpdate: ProxyConfigUpdate = {
      enabled: proxyEnabled,
      type: proxyType,
      host: proxyHost,
      port: proxyPort,
      username: proxyUsername || undefined,
      password: proxyPassword || undefined,
      no_proxy: proxyNoProxy,
    }
    setSaveStatus('saving')
    try {
      await updateSettings({ proxy: proxyUpdate })
      setSaveStatus('success')
      addToast(t('settings.saved'), 'success')
    } catch {
      setSaveStatus('error')
      addToast(t('settings.saveFailed'), 'error')
    }
  }, [proxyEnabled, proxyType, proxyHost, proxyPort, proxyUsername, proxyPassword, proxyNoProxy, updateSettings, validationErrors, addToast, t])

  // T016 — Test proxy connection
  const handleTestProxy = useCallback(async () => {
    if (!proxyHost || !proxyPort) return
    setProxyTestStatus('testing')
    setProxyTestMessage('')
    setProxyTestLatency(null)
    try {
      const result = await testProxy({
        type: proxyType,
        host: proxyHost,
        port: proxyPort,
        username: proxyUsername || undefined,
        password: proxyPassword || undefined,
      })
      if (result.success) {
        setProxyTestStatus('success')
        setProxyTestMessage(result.message)
        setProxyTestLatency(result.latency_ms)
      } else {
        setProxyTestStatus('error')
        setProxyTestMessage(result.message)
      }
    } catch {
      setProxyTestStatus('error')
      setProxyTestMessage(t('settings.proxyTestFailed'))
    }
  }, [proxyType, proxyHost, proxyPort, proxyUsername, proxyPassword, testProxy, t])

  // Auto-dismiss proxy test status
  useEffect(() => {
    if (proxyTestStatus === 'success' || proxyTestStatus === 'error') {
      const timer = setTimeout(() => {
        setProxyTestStatus('idle')
        setProxyTestMessage('')
        setProxyTestLatency(null)
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [proxyTestStatus])

  // T019 — Save runtime settings
  const handleSaveRuntime = useCallback(async () => {
    if (validationErrors.maxTurns || validationErrors.timeout) {
      addToast(t('settings.hasValidationErrors'), 'error')
      return
    }
    const runtimeUpdate: RuntimeConfigUpdate = {
      max_turns: runtimeMaxTurns,
      timeout: runtimeTimeout,
      step_streaming: runtimeStepStreaming,
    }
    setSaveStatus('saving')
    try {
      await updateSettings({ runtime: runtimeUpdate })
      setSaveStatus('success')
      addToast(t('settings.saved'), 'success')
    } catch {
      setSaveStatus('error')
      addToast(t('settings.saveFailed'), 'error')
    }
  }, [runtimeMaxTurns, runtimeTimeout, runtimeStepStreaming, updateSettings, validationErrors, addToast, t])

  // T022 — Upload credentials
  const handleUploadCredentials = useCallback(async () => {
    if (!credentialsJson.trim()) return
    setCredUploadStatus('uploading')
    setCredUploadMessage('')
    try {
      const result = await uploadCredentials(credentialsJson)
      if (result.success) {
        setCredUploadStatus('success')
        setCredUploadMessage(result.message)
        setCredentialsJson('')
      } else {
        setCredUploadStatus('error')
        setCredUploadMessage(result.message)
      }
    } catch {
      setCredUploadStatus('error')
      setCredUploadMessage(t('common.error'))
    }
  }, [credentialsJson, uploadCredentials, t])

  // T022 — Delete credentials
  const handleDeleteCredentials = useCallback(async () => {
    setSaveStatus('saving')
    try {
      await updateSettings({ proxy: undefined } as UpdateSettingsRequest)
      // Use a dedicated endpoint approach: post empty credentials
      await uploadCredentials('')
      await fetchSettings()
      setSaveStatus('success')
      addToast(t('settings.saved'), 'success')
    } catch {
      setSaveStatus('error')
      addToast(t('settings.saveFailed'), 'error')
    }
  }, [updateSettings, uploadCredentials, fetchSettings, addToast, t])

  // Auto-dismiss credential upload status
  useEffect(() => {
    if (credUploadStatus === 'success' || credUploadStatus === 'error') {
      const timer = setTimeout(() => {
        setCredUploadStatus('idle')
        setCredUploadMessage('')
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [credUploadStatus])

  // T025 — Save infrastructure settings
  const handleSaveInfra = useCallback(async () => {
    if (validationErrors.sshPort || validationErrors.alertCpu || validationErrors.alertMemory || validationErrors.alertDisk) {
      addToast(t('settings.hasValidationErrors'), 'error')
      return
    }
    const infraUpdate: InfraConfigUpdate = {
      ssh_host: sshHost,
      ssh_port: sshPort,
      ssh_user: sshUser,
      gitlab_url: gitlabUrl,
      gitlab_token: gitlabToken || undefined,
      alert_cpu: alertCpu,
      alert_memory: alertMemory,
      alert_disk: alertDisk,
      debug: debugMode,
      log_level: logLevel,
    }
    setSaveStatus('saving')
    try {
      await updateSettings({ infra: infraUpdate })
      setSaveStatus('success')
      addToast(t('settings.saved'), 'success')
    } catch {
      setSaveStatus('error')
      addToast(t('settings.saveFailed'), 'error')
    }
  }, [sshHost, sshPort, sshUser, gitlabUrl, gitlabToken, alertCpu, alertMemory, alertDisk, debugMode, logLevel, updateSettings, validationErrors, addToast, t])

  // Derived state
  const currentProvider = formState.provider ?? settings?.provider ?? 'anthropic'
  const providerConfig = settings?.provider_config
  const customModels = providerConfig?.custom_models ?? []
  const isMaxModels = customModels.length >= 20
  const showBaseUrl = currentProvider === 'zai' || currentProvider === 'local'

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
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-destructive">
        <AlertCircle className="h-8 w-8" />
        <p className="text-sm">{error}</p>
      </div>
    )
  }

  // ── Helper: input border class with error state ──────────────────────────
  const inputBorderClass = (fieldKey: string) =>
    cn(
      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
      'text-card-foreground',
      'focus:outline-none focus:ring-2',
      validationErrors[fieldKey]
        ? 'border-[#FF4D6A] focus:ring-[#FF4D6A]/30 focus:border-[#FF4D6A]'
        : 'border-white/10 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
    )

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-6">
      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Form-level error banner from store */}
      {error && settings && (
        <div className="flex items-center gap-2 rounded-lg border border-[#FF4D6A]/30 bg-[#FF4D6A]/10 px-4 py-3 text-sm text-[#FF4D6A]">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20">
            <Settings className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-card-foreground">
            {t('settings.title')}
          </h1>
        </div>

        <button
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
          className={cn(
            'inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium',
            'bg-primary text-primary-foreground hover:bg-primary/90',
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

      {/* ── Provider & Model Section ─────────────────────────────────────── */}
      <section className="rounded-xl border border-white/10 bg-[rgba(255,255,255,0.04)] p-5 shadow-sm backdrop-blur-[14px] backdrop-saturate-[140%]">
        <div className="mb-4 flex items-center gap-2">
          <Server className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.provider')}
          </h2>
        </div>

        <div className="space-y-5">
          {/* ── Provider selector (3 buttons) ── */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              {t('settings.provider')}
            </label>
            <div className="flex gap-2">
              {([
                { id: 'anthropic', labelKey: 'settings.providerAnthropic' },
                { id: 'zai', labelKey: 'settings.providerZai' },
                { id: 'local', labelKey: 'settings.providerLocal' },
              ] as const).map((p) => (
                <button
                  key={p.id}
                  onClick={() => updateField('provider', p.id)}
                  className={cn(
                    'flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                    currentProvider === p.id
                      ? 'border-[#7C6CFF] bg-[#7C6CFF]/10 text-[#7C6CFF]'
                      : 'border-white/10 bg-background text-muted-foreground hover:bg-accent',
                  )}
                >
                  {t(p.labelKey)}
                </button>
              ))}
            </div>
          </div>

          {/* ── API Key input ── */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Key className="h-3.5 w-3.5" />
                {t('settings.apiKey')}
                {providerConfig && (
                  <span
                    className={cn(
                      'ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium',
                      providerConfig.api_key_set
                        ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                        : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30',
                    )}
                  >
                    {providerConfig.api_key_set ? t('settings.apiKeySet') : t('settings.apiKeyNotSet')}
                  </span>
                )}
              </span>
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={t('settings.apiKeyPlaceholder')}
                  className={cn(
                    'w-full rounded-lg border border-white/10 bg-background px-3 py-2 pr-20 text-sm',
                    'text-card-foreground placeholder:text-muted-foreground/50',
                    'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                  )}
                />
                <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex gap-1">
                  <button
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="rounded-md p-1.5 text-muted-foreground hover:text-card-foreground hover:bg-white/5 transition-colors"
                    type="button"
                  >
                    {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                  {apiKeyInput && (
                    <button
                      onClick={() => { setApiKeyInput(''); setValidationStatus('idle'); setValidationMessage(''); }}
                      className="rounded-md p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                      type="button"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Validate button */}
              <button
                onClick={handleValidate}
                disabled={!apiKeyInput || validationStatus === 'validating'}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  validationStatus === 'success'
                    ? 'border-[#4DFF88]/30 bg-[#4DFF88]/10 text-[#4DFF88]'
                    : validationStatus === 'error'
                      ? 'border-[#FF4D6A]/30 bg-[#FF4D6A]/10 text-[#FF4D6A]'
                      : 'border-[#4DE1FF]/30 bg-[#4DE1FF]/10 text-[#4DE1FF] hover:bg-[#4DE1FF]/20',
                )}
              >
                {validationStatus === 'validating' ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {t('settings.validating')}
                  </>
                ) : validationStatus === 'success' ? (
                  <>
                    <CheckCircle className="h-3.5 w-3.5" />
                    {t('settings.validationSuccess')}
                  </>
                ) : validationStatus === 'error' ? (
                  <>
                    <AlertCircle className="h-3.5 w-3.5" />
                    {t('settings.validationFailed')}
                  </>
                ) : (
                  t('settings.validate')
                )}
              </button>
            </div>
            {/* Validation message */}
            {validationMessage && (
              <p className={cn(
                'mt-1.5 text-xs',
                validationStatus === 'success' ? 'text-[#4DFF88]' : 'text-[#FF4D6A]',
              )}>
                {validationMessage}
              </p>
            )}
          </div>

          {/* ── Base URL (for zai and local modes) ── */}
          {showBaseUrl && currentProvider !== 'local' && (
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                {t('settings.baseUrl')}
              </label>
              <input
                type="text"
                value={baseUrlInput}
                onChange={(e) => setBaseUrlInput(e.target.value)}
                placeholder="https://api.example.com/v1"
                className={cn(
                  'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                  'text-card-foreground placeholder:text-muted-foreground/50',
                  'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                )}
              />
            </div>
          )}

          {/* ── Local model fields ── */}
          {currentProvider === 'local' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  {t('settings.localModelName')}
                </label>
                <input
                  type="text"
                  value={localModelName}
                  onChange={(e) => setLocalModelName(e.target.value)}
                  placeholder="my-local-model"
                  className={cn(
                    'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                    'text-card-foreground placeholder:text-muted-foreground/50',
                    'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                  )}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  {t('settings.localModelUrl')}
                </label>
                <input
                  type="text"
                  value={localModelUrl}
                  onChange={(e) => setLocalModelUrl(e.target.value)}
                  placeholder="http://localhost:11434/v1"
                  className={cn(
                    'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                    'text-card-foreground placeholder:text-muted-foreground/50',
                    'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                  )}
                />
              </div>
            </div>
          )}

          {/* ── Model selector ── */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
              {t('settings.model')}
            </label>
            <select
              value={formState.model ?? ''}
              onChange={(e) => updateField('model', e.target.value)}
              className={cn(
                'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                'text-card-foreground',
                'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
              )}
            >
              {settings?.available_models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>

          {/* ── Custom Model Editor (T013) ── */}
          <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-muted-foreground">
                  {t('settings.customModels')}
                </label>
                {customModels.length > 0 && (
                  <span className="inline-flex items-center rounded-full bg-[#7C6CFF]/10 border border-[#7C6CFF]/30 px-2 py-0.5 text-[10px] font-medium text-[#7C6CFF]">
                    {customModels.length} custom
                  </span>
                )}
              </div>

              {/* Add model button */}
              <div className="relative">
                <button
                  onClick={() => !isMaxModels && setShowAddModel(!showAddModel)}
                  disabled={isMaxModels}
                  title={isMaxModels ? t('settings.maxModelsReached') : undefined}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                    isMaxModels
                      ? 'cursor-not-allowed border-white/5 bg-white/[0.02] text-muted-foreground/40'
                      : 'border-[#4DE1FF]/30 bg-[#4DE1FF]/10 text-[#4DE1FF] hover:bg-[#4DE1FF]/20',
                  )}
                >
                  <Plus className="h-3 w-3" />
                  {t('settings.addModel')}
                </button>
                {/* Tooltip for disabled state */}
                {isMaxModels && (
                  <div className="absolute -top-8 right-0 whitespace-nowrap rounded-md bg-card border border-white/10 px-2.5 py-1 text-[10px] text-muted-foreground shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity">
                    {t('settings.maxModelsReached')}
                  </div>
                )}
              </div>
            </div>

            {/* Add model input row */}
            {showAddModel && (
              <div className="mb-3 flex gap-2">
                <input
                  type="text"
                  value={newModelId}
                  onChange={(e) => setNewModelId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleAddCustomModel(); if (e.key === 'Escape') { setShowAddModel(false); setNewModelId(''); } }}
                  placeholder={t('settings.modelIdPlaceholder')}
                  autoFocus
                  className={cn(
                    'flex-1 rounded-lg border border-white/10 bg-background px-3 py-1.5 text-sm',
                    'text-card-foreground placeholder:text-muted-foreground/50',
                    'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                  )}
                />
                <button
                  onClick={handleAddCustomModel}
                  disabled={!newModelId.trim() || addingModel}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-lg border border-[#7C6CFF]/30 bg-[#7C6CFF]/10 px-3 py-1.5 text-xs font-medium text-[#7C6CFF] transition-colors',
                    'hover:bg-[#7C6CFF]/20',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                >
                  {addingModel ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <CheckCircle className="h-3 w-3" />
                  )}
                  {t('common.confirm')}
                </button>
                <button
                  onClick={() => { setShowAddModel(false); setNewModelId(''); }}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-muted-foreground hover:bg-white/5 transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}

            {/* Custom models list */}
            {customModels.length > 0 ? (
              <ul className="space-y-1.5">
                {customModels.map((model) => (
                  <li
                    key={model}
                    className="group flex items-center justify-between rounded-md border border-white/5 bg-white/[0.02] px-3 py-2 text-sm text-card-foreground"
                  >
                    <span className="truncate font-mono text-xs">{model}</span>
                    <button
                      onClick={() => handleRemoveCustomModel(model)}
                      disabled={removingModelId === model}
                      className={cn(
                        'ml-2 rounded-md p-1 transition-colors',
                        'text-muted-foreground/50 hover:text-destructive hover:bg-destructive/10',
                        'opacity-0 group-hover:opacity-100',
                        removingModelId === model && 'opacity-100',
                      )}
                    >
                      {removingModelId === model ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <X className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-center text-xs text-muted-foreground/50 py-3">
                {t('common.noData')}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* ── T016: Proxy Configuration Section ────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Network className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.proxy')}
          </h2>
        </div>

        <div className="space-y-4">
          {/* Enable/disable toggle */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-card-foreground">
              {proxyEnabled ? t('settings.proxyEnabled') : t('settings.proxyDisabled')}
            </span>
            <button
              onClick={() => setProxyEnabled(!proxyEnabled)}
              className="flex items-center"
            >
              <div
                className={cn(
                  'h-6 w-11 rounded-full transition-colors',
                  proxyEnabled ? 'bg-[#7C6CFF]' : 'bg-muted-foreground/30',
                )}
              >
                <div
                  className={cn(
                    'h-5 w-5 translate-y-0.5 rounded-full bg-white shadow-sm transition-transform',
                    proxyEnabled ? 'translate-x-5' : 'translate-x-0.5',
                  )}
                />
              </div>
            </button>
          </div>

          {proxyEnabled && (
            <>
              {/* Proxy type buttons */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  {t('settings.proxyType')}
                </label>
                <div className="flex gap-2">
                  {(['http', 'https', 'socks5'] as const).map((pt) => (
                    <button
                      key={pt}
                      onClick={() => setProxyType(pt)}
                      className={cn(
                        'flex-1 rounded-lg border px-4 py-2 text-sm font-medium uppercase transition-colors',
                        proxyType === pt
                          ? 'border-[#7C6CFF]/30 bg-[#7C6CFF]/10 text-[#7C6CFF]'
                          : 'border-white/10 bg-background text-muted-foreground hover:bg-accent',
                      )}
                    >
                      {pt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Host + Port */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.proxyHost')}
                  </label>
                  <input
                    type="text"
                    value={proxyHost}
                    onChange={(e) => setProxyHost(e.target.value)}
                    placeholder="proxy.example.com"
                    className={cn(
                      'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                      'text-card-foreground placeholder:text-muted-foreground/50',
                      'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                    )}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.proxyPort')}
                  </label>
                  <input
                    type="number"
                    value={proxyPort}
                    onChange={(e) => setProxyPort(Number(e.target.value))}
                    min={1}
                    max={65535}
                    className={inputBorderClass('proxyPort')}
                  />
                  <FieldError message={validationErrors.proxyPort} />
                </div>
              </div>

              {/* Username + Password */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.proxyUsername')}
                  </label>
                  <input
                    type="text"
                    value={proxyUsername}
                    onChange={(e) => setProxyUsername(e.target.value)}
                    placeholder={t('settings.proxyUsername')}
                    className={cn(
                      'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                      'text-card-foreground placeholder:text-muted-foreground/50',
                      'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                    )}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.proxyPassword')}
                  </label>
                  <div className="relative">
                    <input
                      type={showProxyPassword ? 'text' : 'password'}
                      value={proxyPassword}
                      onChange={(e) => setProxyPassword(e.target.value)}
                      placeholder="••••••••"
                      className={cn(
                        'w-full rounded-lg border border-white/10 bg-background px-3 py-2 pr-10 text-sm',
                        'text-card-foreground placeholder:text-muted-foreground/50',
                        'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                      )}
                    />
                    <button
                      onClick={() => setShowProxyPassword(!showProxyPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:text-card-foreground transition-colors"
                      type="button"
                    >
                      {showProxyPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
              </div>

              {/* NO_PROXY textarea */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  {t('settings.proxyNoProxy')}
                </label>
                <textarea
                  value={proxyNoProxy}
                  onChange={(e) => setProxyNoProxy(e.target.value)}
                  placeholder="localhost,127.0.0.1,192.168.0.0/16"
                  rows={3}
                  className={cn(
                    'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                    'text-card-foreground placeholder:text-muted-foreground/50 resize-none',
                    'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                  )}
                />
              </div>

              {/* Actions row: Save + Test */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleSaveProxy}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                    'border-[#7C6CFF]/30 bg-[#7C6CFF]/10 text-[#7C6CFF] hover:bg-[#7C6CFF]/20',
                  )}
                >
                  <Save className="h-3.5 w-3.5" />
                  {t('common.save')}
                </button>

                <button
                  onClick={handleTestProxy}
                  disabled={!proxyHost || proxyTestStatus === 'testing'}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                    proxyTestStatus === 'success'
                      ? 'border-green-500/30 bg-green-500/10 text-green-400'
                      : proxyTestStatus === 'error'
                        ? 'border-destructive/30 bg-destructive/10 text-destructive'
                        : 'border-[#4DE1FF]/30 bg-[#4DE1FF]/10 text-[#4DE1FF] hover:bg-[#4DE1FF]/20',
                  )}
                >
                  {proxyTestStatus === 'testing' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : proxyTestStatus === 'success' ? (
                    <CheckCircle className="h-3.5 w-3.5" />
                  ) : proxyTestStatus === 'error' ? (
                    <AlertCircle className="h-3.5 w-3.5" />
                  ) : (
                    <Wifi className="h-3.5 w-3.5" />
                  )}
                  {t('settings.proxyTest')}
                </button>

                {/* Test result */}
                {proxyTestMessage && (
                  <span className={cn(
                    'text-xs',
                    proxyTestStatus === 'success' ? 'text-green-400' : 'text-destructive',
                  )}>
                    {proxyTestMessage}
                    {proxyTestLatency != null && ` (${proxyTestLatency}ms)`}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </section>

      {/* ── T019: Runtime Settings + Plugins Section ──────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <Sliders className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.runtime')}
          </h2>
        </div>

        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Max turns */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                {t('settings.maxTurns')}
              </label>
              <input
                type="number"
                value={runtimeMaxTurns}
                onChange={(e) => setRuntimeMaxTurns(Number(e.target.value))}
                min={1}
                max={999}
                className={inputBorderClass('maxTurns')}
              />
              <FieldError message={validationErrors.maxTurns} />
            </div>

            {/* Timeout */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <Timer className="h-3.5 w-3.5" />
                  {t('settings.timeout')}
                </span>
              </label>
              <div className="relative">
                <input
                  type="number"
                  value={runtimeTimeout}
                  onChange={(e) => setRuntimeTimeout(Number(e.target.value))}
                  min={1}
                  max={99999}
                  className={cn(inputBorderClass('timeout'), 'pr-12')}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                  {t('settings.timeout') === t('settings.timeout') ? 'сек' : 'sec'}
                </span>
              </div>
              <FieldError message={validationErrors.timeout} />
            </div>
          </div>

          {/* Step streaming toggle */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-card-foreground">
              {t('settings.stepStreaming')}
            </span>
            <button
              onClick={() => setRuntimeStepStreaming(!runtimeStepStreaming)}
              className="flex items-center"
            >
              <div
                className={cn(
                  'h-6 w-11 rounded-full transition-colors',
                  runtimeStepStreaming ? 'bg-[#7C6CFF]' : 'bg-muted-foreground/30',
                )}
              >
                <div
                  className={cn(
                    'h-5 w-5 translate-y-0.5 rounded-full bg-white shadow-sm transition-transform',
                    runtimeStepStreaming ? 'translate-x-5' : 'translate-x-0.5',
                  )}
                />
              </div>
            </button>
          </div>

          {/* Save runtime */}
          <button
            onClick={handleSaveRuntime}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
              'border-[#7C6CFF]/30 bg-[#7C6CFF]/10 text-[#7C6CFF] hover:bg-[#7C6CFF]/20',
            )}
          >
            <Save className="h-3.5 w-3.5" />
            {t('common.save')}
          </button>

          {/* T019b — Plugins sub-section */}
          <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
            <div className="mb-3 flex items-center gap-2">
              <Wrench className="h-4 w-4 text-muted-foreground" />
              <label className="text-xs font-medium text-muted-foreground">
                {t('settings.plugins')}
              </label>
              {plugins.length > 0 && (
                <span className="inline-flex items-center rounded-full bg-[#7C6CFF]/10 border border-[#7C6CFF]/30 px-2 py-0.5 text-[10px] font-medium text-[#7C6CFF]">
                  {plugins.length}
                </span>
              )}
            </div>

            {pluginsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            ) : plugins.length > 0 ? (
              <ul className="space-y-1.5">
                {plugins.map((plugin) => (
                  <li
                    key={plugin.name}
                    className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.02] px-3 py-2 text-sm text-card-foreground"
                  >
                    <div className="flex flex-col">
                      <span className="font-mono text-xs">{plugin.name}</span>
                      {plugin.description && (
                        <span className="text-[10px] text-muted-foreground">{plugin.description}</span>
                      )}
                    </div>
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border',
                        plugin.enabled
                          ? 'bg-green-500/10 text-green-400 border-green-500/30'
                          : 'bg-muted-foreground/10 text-muted-foreground border-white/10',
                      )}
                    >
                      {plugin.enabled ? t('settings.pluginEnabled') : t('settings.pluginDisabled')}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-center text-xs text-muted-foreground/50 py-3">
                {t('common.noData')}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* ── T022: Claude Account Section ──────────────────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.claudeAccount')}
          </h2>
          {/* Status indicator */}
          {settings?.claude_account && (
            <span
              className={cn(
                'ml-auto inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-medium border',
                settings.claude_account.active
                  ? 'bg-green-500/10 text-green-400 border-green-500/30'
                  : settings.claude_account.credentials_exist
                    ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
                    : 'bg-destructive/10 text-destructive border-destructive/30',
              )}
            >
              {settings.claude_account.active
                ? t('settings.credentialsExist')
                : settings.claude_account.credentials_exist
                  ? t('settings.credentialsExpired')
                  : t('settings.credentialsMissing')}
            </span>
          )}
        </div>

        <div className="space-y-4">
          {settings?.claude_account?.credentials_exist ? (
            <>
              {/* Credential details grid */}
              <div className="grid gap-4 sm:grid-cols-2">
                {settings.claude_account.subscription_type && (
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t('settings.subscriptionType')}
                    </label>
                    <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
                      {settings.claude_account.subscription_type}
                    </div>
                  </div>
                )}
                {settings.claude_account.rate_limit_tier && (
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t('settings.rateLimitTier')}
                    </label>
                    <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
                      {settings.claude_account.rate_limit_tier}
                    </div>
                  </div>
                )}
                {settings.claude_account.expires_at && (
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t('settings.expiresAt')}
                    </label>
                    <div className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground">
                      {new Date(settings.claude_account.expires_at).toLocaleDateString()}
                    </div>
                  </div>
                )}
              </div>

              {/* Scopes badges */}
              {settings.claude_account.scopes.length > 0 && (
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.scopes')}
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {settings.claude_account.scopes.map((scope) => (
                      <span
                        key={scope}
                        className="inline-flex items-center rounded-full border border-[#4DE1FF]/30 bg-[#4DE1FF]/10 px-2.5 py-0.5 text-[10px] font-medium text-[#4DE1FF]"
                      >
                        <Lock className="mr-1 h-2.5 w-2.5" />
                        {scope}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Delete credentials */}
              <button
                onClick={handleDeleteCredentials}
                className={cn(
                  'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                  'border-destructive/30 bg-destructive/10 text-destructive hover:bg-destructive/20',
                )}
              >
                <Trash2 className="h-3.5 w-3.5" />
                {t('settings.deleteCredentials')}
              </button>
            </>
          ) : (
            <>
              {/* Upload credentials JSON */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  {t('settings.uploadCredentials')}
                </label>
                <textarea
                  value={credentialsJson}
                  onChange={(e) => setCredentialsJson(e.target.value)}
                  placeholder={t('settings.credentialsPlaceholder')}
                  rows={6}
                  className={cn(
                    'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm font-mono',
                    'text-card-foreground placeholder:text-muted-foreground/50 resize-none',
                    'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                  )}
                />
              </div>

              <button
                onClick={handleUploadCredentials}
                disabled={!credentialsJson.trim() || credUploadStatus === 'uploading'}
                className={cn(
                  'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  'border-[#7C6CFF]/30 bg-[#7C6CFF]/10 text-[#7C6CFF] hover:bg-[#7C6CFF]/20',
                )}
              >
                {credUploadStatus === 'uploading' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <KeyRound className="h-3.5 w-3.5" />
                )}
                {t('settings.uploadCredentials')}
              </button>

              {/* Upload feedback */}
              {credUploadMessage && (
                <p className={cn(
                  'text-xs',
                  credUploadStatus === 'success' ? 'text-[#4DFF88]' : 'text-[#FF4D6A]',
                )}>
                  {credUploadMessage}
                </p>
              )}
            </>
          )}
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
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-background text-muted-foreground hover:bg-accent',
                  )}
                >
                  {opt.toUpperCase()}
                </button>
              ))}
            </div>
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
                      ? 'border-primary bg-primary/10 text-primary'
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
                  ? 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400'
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
                  formState.yolo_mode ? 'bg-yellow-500' : 'bg-muted-foreground/30',
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

      {/* ── T025: Infrastructure Section (collapsible) ────────────────────── */}
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <button
          onClick={() => setInfraExpanded(!infraExpanded)}
          className="flex w-full items-center gap-2"
        >
          <Server className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold text-card-foreground">
            {t('settings.infrastructure')}
          </h2>
          <div className="ml-auto">
            {infraExpanded ? (
              <ChevronDown className="h-5 w-5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            )}
          </div>
        </button>

        {infraExpanded && (
          <div className="mt-5 space-y-6">
            {/* SSH sub-section */}
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t('settings.sshSettings')}
              </label>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.sshHost')}
                  </label>
                  <input
                    type="text"
                    value={sshHost}
                    onChange={(e) => setSshHost(e.target.value)}
                    placeholder="192.168.0.116"
                    className={cn(
                      'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                      'text-card-foreground placeholder:text-muted-foreground/50',
                      'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                    )}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.sshPort')}
                  </label>
                  <input
                    type="number"
                    value={sshPort}
                    onChange={(e) => setSshPort(Number(e.target.value))}
                    min={1}
                    max={65535}
                    className={inputBorderClass('sshPort')}
                  />
                  <FieldError message={validationErrors.sshPort} />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.sshUser')}
                  </label>
                  <input
                    type="text"
                    value={sshUser}
                    onChange={(e) => setSshUser(e.target.value)}
                    placeholder="root"
                    className={cn(
                      'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                      'text-card-foreground placeholder:text-muted-foreground/50',
                      'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                    )}
                  />
                </div>
              </div>
            </div>

            {/* GitLab sub-section */}
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t('settings.gitlabSettings')}
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.gitlabUrl')}
                  </label>
                  <input
                    type="text"
                    value={gitlabUrl}
                    onChange={(e) => setGitlabUrl(e.target.value)}
                    placeholder="https://gitlab.example.com"
                    className={cn(
                      'w-full rounded-lg border border-white/10 bg-background px-3 py-2 text-sm',
                      'text-card-foreground placeholder:text-muted-foreground/50',
                      'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                    )}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      {t('settings.gitlabToken')}
                      {settings?.infra?.gitlab_token_set && (
                        <span className="ml-2 inline-flex items-center rounded-full bg-green-500/10 text-green-400 border border-green-500/30 px-2 py-0.5 text-[10px] font-medium">
                          {t('settings.gitlabTokenSet')}
                        </span>
                      )}
                    </span>
                  </label>
                  <div className="relative">
                    <input
                      type={showGitlabToken ? 'text' : 'password'}
                      value={gitlabToken}
                      onChange={(e) => setGitlabToken(e.target.value)}
                      placeholder="glpat-xxxxxxxxxx"
                      className={cn(
                        'w-full rounded-lg border border-white/10 bg-background px-3 py-2 pr-10 text-sm',
                        'text-card-foreground placeholder:text-muted-foreground/50',
                        'focus:outline-none focus:ring-2 focus:ring-[#7C6CFF]/30 focus:border-[#7C6CFF]',
                      )}
                    />
                    <button
                      onClick={() => setShowGitlabToken(!showGitlabToken)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:text-card-foreground transition-colors"
                      type="button"
                    >
                      {showGitlabToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Monitoring sub-section */}
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t('settings.monitoring')}
              </label>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.alertCpu')}
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={alertCpu}
                      onChange={(e) => setAlertCpu(Number(e.target.value))}
                      min={0}
                      max={100}
                      className={cn(inputBorderClass('alertCpu'), 'pr-8')}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                  </div>
                  <FieldError message={validationErrors.alertCpu} />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.alertMemory')}
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={alertMemory}
                      onChange={(e) => setAlertMemory(Number(e.target.value))}
                      min={0}
                      max={100}
                      className={cn(inputBorderClass('alertMemory'), 'pr-8')}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                  </div>
                  <FieldError message={validationErrors.alertMemory} />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.alertDisk')}
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={alertDisk}
                      onChange={(e) => setAlertDisk(Number(e.target.value))}
                      min={0}
                      max={100}
                      className={cn(inputBorderClass('alertDisk'), 'pr-8')}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                  </div>
                  <FieldError message={validationErrors.alertDisk} />
                </div>
              </div>
            </div>

            {/* Debug sub-section */}
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t('settings.debugMode')}
              </label>
              <div className="space-y-3">
                {/* Debug toggle */}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-card-foreground">
                    {t('settings.debugMode')}
                  </span>
                  <button
                    onClick={() => setDebugMode(!debugMode)}
                    className="flex items-center"
                  >
                    <div
                      className={cn(
                        'h-6 w-11 rounded-full transition-colors',
                        debugMode ? 'bg-yellow-500' : 'bg-muted-foreground/30',
                      )}
                    >
                      <div
                        className={cn(
                          'h-5 w-5 translate-y-0.5 rounded-full bg-white shadow-sm transition-transform',
                          debugMode ? 'translate-x-5' : 'translate-x-0.5',
                        )}
                      />
                    </div>
                  </button>
                </div>

                {/* Log level */}
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    {t('settings.logLevel')}
                  </label>
                  <div className="flex gap-2">
                    {(['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const).map((level) => (
                      <button
                        key={level}
                        onClick={() => setLogLevel(level)}
                        className={cn(
                          'flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                          logLevel === level
                            ? 'border-[#7C6CFF]/30 bg-[#7C6CFF]/10 text-[#7C6CFF]'
                            : 'border-white/10 bg-background text-muted-foreground hover:bg-accent',
                        )}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Save infra */}
            <button
              onClick={handleSaveInfra}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                'border-[#7C6CFF]/30 bg-[#7C6CFF]/10 text-[#7C6CFF] hover:bg-[#7C6CFF]/20',
              )}
            >
              <Save className="h-3.5 w-3.5" />
              {t('common.save')}
            </button>
          </div>
        )}
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
                  ? 'border-primary bg-primary/10 text-primary'
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
