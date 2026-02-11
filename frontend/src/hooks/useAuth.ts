// ---------------------------------------------------------------------------
// Auth hooks — TanStack Query wrappers for authentication operations
// ---------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/services/api'
import type {
  UserProfile,
  CreateUserRequest,
  ResetPasswordRequest,
  MessageResponse,
} from '@/types/api'
import type { UpdateProfileData } from '@/stores/authStore'

// ── Query keys ───────────────────────────────────────────────────────────────

export const authKeys = {
  all: ['auth'] as const,
  profile: () => [...authKeys.all, 'profile'] as const,
  users: () => [...authKeys.all, 'users'] as const,
}

// ── useLogin ─────────────────────────────────────────────────────────────────

export function useLogin() {
  const queryClient = useQueryClient()
  const login = useAuthStore((s) => s.login)

  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      login(username, password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: authKeys.all })
    },
  })
}

// ── useLogout ────────────────────────────────────────────────────────────────

export function useLogout() {
  const queryClient = useQueryClient()
  const logout = useAuthStore((s) => s.logout)

  return useMutation({
    mutationFn: () => logout(),
    onSuccess: () => {
      queryClient.clear()
    },
  })
}

// ── useProfile ───────────────────────────────────────────────────────────────

export function useProfile() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  return useQuery({
    queryKey: authKeys.profile(),
    queryFn: async () => {
      const { data } = await api.get<UserProfile>('/auth/me')
      return data
    },
    enabled: isAuthenticated,
  })
}

// ── useUpdateProfile ─────────────────────────────────────────────────────────

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  const updateProfile = useAuthStore((s) => s.updateProfile)

  return useMutation({
    mutationFn: (data: UpdateProfileData) => updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: authKeys.profile() })
    },
  })
}

// ── useUsers ─────────────────────────────────────────────────────────────────

export function useUsers() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  return useQuery({
    queryKey: authKeys.users(),
    queryFn: async () => {
      const { data } = await api.get<UserProfile[]>('/auth/users')
      return data
    },
    enabled: isAuthenticated,
  })
}

// ── useCreateUser ────────────────────────────────────────────────────────────

export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateUserRequest) => {
      const { data } = await api.post<UserProfile>('/auth/users', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: authKeys.users() })
    },
  })
}

// ── useResetPassword ─────────────────────────────────────────────────────────

export function useResetPassword() {
  return useMutation({
    mutationFn: async ({
      userId,
      newPassword,
    }: {
      userId: string
      newPassword: string
    }) => {
      const payload: ResetPasswordRequest = { new_password: newPassword }
      const { data } = await api.patch<MessageResponse>(
        `/auth/users/${userId}/password`,
        payload,
      )
      return data
    },
  })
}
