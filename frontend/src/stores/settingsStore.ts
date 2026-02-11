// ---------------------------------------------------------------------------
// Zustand settings store — manages application settings state
// ---------------------------------------------------------------------------

import { create } from 'zustand'
import { api } from '@/services/api'
import type { SettingsResponse, UpdateSettingsRequest } from '@/types/api'

// ── Public types ──────────────────────────────────────────────────────────

export interface SettingsState {
  settings: SettingsResponse | null
  isLoading: boolean
  error: string | null

  // Actions
  fetchSettings: () => Promise<void>
  updateSettings: (data: UpdateSettingsRequest) => Promise<void>
}

// ── Store ─────────────────────────────────────────────────────────────────

export const useSettingsStore = create<SettingsState>()((set) => ({
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
}))
