// ---------------------------------------------------------------------------
// useProjects — TanStack Query hooks for project, context, and variable CRUD
// ---------------------------------------------------------------------------

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import type {
  ProjectResponse,
  ProjectListResponse,
  CreateProjectRequest,
  ContextResponse,
  ContextListResponse,
  CreateContextRequest,
  VariableResponse,
  VariableListResponse,
  CreateVariableRequest,
  MessageResponse,
} from '@/types/api'

// ── Query keys ───────────────────────────────────────────────────────────────

export const projectKeys = {
  all: ['projects'] as const,
  list: () => [...projectKeys.all, 'list'] as const,
  detail: (id: string) => [...projectKeys.all, 'detail', id] as const,
  contexts: (projectId: string) =>
    [...projectKeys.all, 'contexts', projectId] as const,
  variables: (projectId: string) =>
    [...projectKeys.all, 'variables', projectId] as const,
}

// ── Projects ─────────────────────────────────────────────────────────────────

export function useProjects() {
  return useQuery({
    queryKey: projectKeys.list(),
    queryFn: async () => {
      const { data } = await api.get<ProjectListResponse>('/projects')
      return data
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateProjectRequest) => {
      const { data } = await api.post<ProjectResponse>('/projects', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.list() })
    },
  })
}

export function useActivateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data } = await api.post<ProjectResponse>(
        `/projects/${projectId}/activate`,
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.list() })
    },
  })
}

// ── Contexts ─────────────────────────────────────────────────────────────────

export function useContexts(projectId: string | null) {
  return useQuery({
    queryKey: projectKeys.contexts(projectId ?? ''),
    queryFn: async () => {
      const { data } = await api.get<ContextListResponse>(
        `/projects/${projectId}/contexts`,
      )
      return data
    },
    enabled: projectId !== null,
  })
}

export function useCreateContext() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      name,
    }: {
      projectId: string
      name: string
    }) => {
      const payload: CreateContextRequest = { name, project_id: projectId }
      const { data } = await api.post<ContextResponse>(
        `/projects/${projectId}/contexts`,
        payload,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.contexts(variables.projectId),
      })
    },
  })
}

export function useActivateContext() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      contextId,
    }: {
      projectId: string
      contextId: string
    }) => {
      const { data } = await api.post<ContextResponse>(
        `/projects/${projectId}/contexts/${contextId}/activate`,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.contexts(variables.projectId),
      })
    },
  })
}

export function useDeleteContext() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      contextId,
    }: {
      projectId: string
      contextId: string
    }) => {
      const { data } = await api.delete<MessageResponse>(
        `/projects/${projectId}/contexts/${contextId}`,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.contexts(variables.projectId),
      })
    },
  })
}

export function useClearContextMessages() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      contextId,
    }: {
      projectId: string
      contextId: string
    }) => {
      const { data } = await api.delete<MessageResponse>(
        `/projects/${projectId}/contexts/${contextId}/messages`,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.contexts(variables.projectId),
      })
    },
  })
}

// ── Variables ────────────────────────────────────────────────────────────────

export function useVariables(projectId: string | null) {
  return useQuery({
    queryKey: projectKeys.variables(projectId ?? ''),
    queryFn: async () => {
      const { data } = await api.get<VariableListResponse>(
        `/projects/${projectId}/variables`,
        { params: { scope: 'all' } },
      )
      return data
    },
    enabled: projectId !== null,
  })
}

export function useCreateVariable() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      payload,
    }: {
      projectId: string
      payload: CreateVariableRequest
    }) => {
      const { data } = await api.post<VariableResponse>(
        `/projects/${projectId}/variables`,
        payload,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.variables(variables.projectId),
      })
    },
  })
}

export function useUpdateVariable() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      variableId,
      payload,
    }: {
      projectId: string
      variableId: string
      payload: Partial<CreateVariableRequest>
    }) => {
      const { data } = await api.put<VariableResponse>(
        `/projects/${projectId}/variables/${variableId}`,
        payload,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.variables(variables.projectId),
      })
    },
  })
}

export function useDeleteVariable() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      projectId,
      variableId,
    }: {
      projectId: string
      variableId: string
    }) => {
      const { data } = await api.delete<MessageResponse>(
        `/projects/${projectId}/variables/${variableId}`,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: projectKeys.variables(variables.projectId),
      })
    },
  })
}
