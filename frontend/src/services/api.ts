// ---------------------------------------------------------------------------
// Axios-based API client with JWT interceptor
// ---------------------------------------------------------------------------

import axios from 'axios'
import type { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

// ── Axios instance ────────────────────────────────────────────────────────

const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // send refresh-token cookie with every request
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Request interceptor – attach Bearer token ─────────────────────────────

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { accessToken } = useAuthStore.getState()
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ── Response interceptor – refresh on 401 ─────────────────────────────────

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: AxiosResponse) => void
  reject: (reason: unknown) => void
  config: InternalAxiosRequestConfig
}> = []

function processQueue(error: unknown | null) {
  for (const entry of failedQueue) {
    if (error) {
      entry.reject(error)
    } else {
      // Retry with the new token (already set in store)
      apiClient.request(entry.config).then(entry.resolve).catch(entry.reject)
    }
  }
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // Only attempt refresh for 401 responses that haven't already been retried
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    // Don't try to refresh if the failing request is the refresh endpoint itself
    if (originalRequest.url?.includes('/auth/refresh')) {
      useAuthStore.getState().clearAuth()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // If a refresh is already in-flight, queue this request
    if (isRefreshing) {
      return new Promise<AxiosResponse>((resolve, reject) => {
        failedQueue.push({ resolve, reject, config: originalRequest })
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    try {
      const success = await useAuthStore.getState().refreshToken()

      if (!success) {
        processQueue(new Error('Token refresh failed'))
        window.location.href = '/login'
        return Promise.reject(error)
      }

      // Update the Authorization header with the new token
      const { accessToken } = useAuthStore.getState()
      if (accessToken && originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
      }

      processQueue(null)

      // Retry the original request
      return apiClient.request(originalRequest)
    } catch (refreshError) {
      processQueue(refreshError)
      useAuthStore.getState().clearAuth()
      window.location.href = '/login'
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

// ── Typed helper methods ──────────────────────────────────────────────────

export const api = {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return apiClient.get<T>(url, config)
  },

  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return apiClient.post<T>(url, data, config)
  },

  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return apiClient.patch<T>(url, data, config)
  },

  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return apiClient.put<T>(url, data, config)
  },

  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return apiClient.delete<T>(url, config)
  },
}

export default apiClient
