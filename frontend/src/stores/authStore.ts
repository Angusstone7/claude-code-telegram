// ---------------------------------------------------------------------------
// Zustand auth store – manages authentication state
// ---------------------------------------------------------------------------
// Access token is stored in memory only (this store).
// Refresh token is handled by the server via HttpOnly cookie.
// ---------------------------------------------------------------------------

import { create } from 'zustand'
import axios from 'axios'
import type { LoginResponse, RefreshResponse, UserProfile, UpdateProfileRequest } from '@/types/api'

// ── Public types ──────────────────────────────────────────────────────────

export interface UpdateProfileData {
  display_name?: string
  telegram_id?: number | null
}

export interface AuthState {
  user: UserProfile | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<boolean>
  updateProfile: (data: UpdateProfileData) => Promise<void>
  setUser: (user: UserProfile) => void
  setToken: (token: string) => void
  clearAuth: () => void
}

// ── Internal Axios instance (avoids circular dep with api.ts) ─────────────
// This is a *plain* instance without the JWT interceptor so we can call
// auth endpoints without triggering infinite refresh loops.

const authApi = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // send refresh-token cookie
})

// ── Store ─────────────────────────────────────────────────────────────────

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: false,

  // ─── Login ──────────────────────────────────────────────────────────

  login: async (username: string, password: string) => {
    set({ isLoading: true })
    try {
      const { data } = await authApi.post<LoginResponse>('/auth/login', {
        username,
        password,
      })

      set({
        user: data.user,
        accessToken: data.access_token,
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  // ─── Logout ─────────────────────────────────────────────────────────

  logout: async () => {
    const { accessToken } = get()
    try {
      await authApi.post('/auth/logout', null, {
        headers: accessToken
          ? { Authorization: `Bearer ${accessToken}` }
          : undefined,
      })
    } catch {
      // Ignore errors – we clear local state regardless
    } finally {
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
      })
    }
  },

  // ─── Token refresh ──────────────────────────────────────────────────

  refreshToken: async () => {
    try {
      const { data } = await authApi.post<RefreshResponse>('/auth/refresh')

      set({
        accessToken: data.access_token,
        isAuthenticated: true,
      })
      return true
    } catch {
      // Refresh failed – clear auth state
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
      })
      return false
    }
  },

  // ─── Update profile ─────────────────────────────────────────────────

  updateProfile: async (data: UpdateProfileData) => {
    const { accessToken } = get()
    const payload: UpdateProfileRequest = {}
    if (data.display_name !== undefined) payload.display_name = data.display_name
    if (data.telegram_id !== undefined) payload.telegram_id = data.telegram_id

    const { data: updatedUser } = await authApi.patch<UserProfile>(
      '/auth/me',
      payload,
      {
        headers: accessToken
          ? { Authorization: `Bearer ${accessToken}` }
          : undefined,
      },
    )

    set({ user: updatedUser })
  },

  // ─── Simple setters ─────────────────────────────────────────────────

  setUser: (user: UserProfile) => set({ user, isAuthenticated: true }),

  setToken: (token: string) => set({ accessToken: token, isAuthenticated: true }),

  clearAuth: () =>
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
    }),
}))
