// ---------------------------------------------------------------------------
// Zustand settings store — manages application settings state
// ---------------------------------------------------------------------------

import { create } from 'zustand'
import { api } from '@/services/api'
import type {
  SettingsResponse,
  UpdateSettingsRequest,
  ProviderValidateRequest,
  ProviderValidateResponse,
  CustomModelRequest,
  CustomModelResponse,
  CredentialsUploadRequest,
  CredentialsUploadResponse,
  ProxyTestRequest,
  ProxyTestResponse,
} from '@/types/api'

// ── Public types ──────────────────────────────────────────────────────────

export interface SettingsState {
  settings: SettingsResponse | null
  isLoading: boolean
  error: string | null

  // Actions
  fetchSettings: () => Promise<void>
  updateSettings: (data: UpdateSettingsRequest) => Promise<void>
  validateProvider: (req: ProviderValidateRequest) => Promise<ProviderValidateResponse>
  addCustomModel: (provider: string, modelId: string) => Promise<CustomModelResponse>
  removeCustomModel: (provider: string, modelId: string) => Promise<CustomModelResponse>
  uploadCredentials: (json: string) => Promise<CredentialsUploadResponse>
  testProxy: (req: ProxyTestRequest) => Promise<ProxyTestResponse>
}

// ── Store ─────────────────────────────────────────────────────────────────

export const useSettingsStore = create<SettingsState>()((set, get) => ({
  settings: null,
  isLoading: false,
  error: null,

  fetchSettings: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get<SettingsResponse>('/settings')
      set({ settings: data, isLoading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load settings'
      set({ error: message, isLoading: false })
    }
  },

  updateSettings: async (payload: UpdateSettingsRequest) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.patch<SettingsResponse>('/settings', payload)
      set({ settings: data, isLoading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update settings'
      set({ error: message, isLoading: false })
      throw err
    }
  },

  validateProvider: async (req: ProviderValidateRequest) => {
    const { data } = await api.post<ProviderValidateResponse>(
      '/settings/provider/validate',
      req,
    )
    return data
  },

  addCustomModel: async (provider: string, modelId: string) => {
    const req: CustomModelRequest = { provider, model_id: modelId }
    const { data } = await api.post<CustomModelResponse>(
      '/settings/models/custom',
      req,
    )
    // Refresh settings to update available_models
    get().fetchSettings()
    return data
  },

  removeCustomModel: async (provider: string, modelId: string) => {
    const { data } = await api.delete<CustomModelResponse>(
      '/settings/models/custom',
      { data: { provider, model_id: modelId } },
    )
    // Refresh settings to update available_models
    get().fetchSettings()
    return data
  },

  uploadCredentials: async (json: string) => {
    const req: CredentialsUploadRequest = { credentials_json: json }
    const { data } = await api.post<CredentialsUploadResponse>(
      '/settings/claude-account/credentials',
      req,
    )
    // Refresh settings to update claude_account status
    get().fetchSettings()
    return data
  },

  testProxy: async (req: ProxyTestRequest) => {
    const { data } = await api.post<ProxyTestResponse>(
      '/settings/proxy/test',
      req,
    )
    return data
  },
}))
