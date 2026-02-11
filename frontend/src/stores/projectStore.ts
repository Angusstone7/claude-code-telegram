// ---------------------------------------------------------------------------
// Zustand project store — manages active project selection state
// ---------------------------------------------------------------------------

import { create } from 'zustand'
import type { ProjectResponse } from '@/types/api'

// ── Public types ──────────────────────────────────────────────────────────

export interface ProjectState {
  activeProject: ProjectResponse | null
  setActiveProject: (project: ProjectResponse | null) => void
}

// ── Store ─────────────────────────────────────────────────────────────────

export const useProjectStore = create<ProjectState>()((set) => ({
  activeProject: null,
  setActiveProject: (project) => set({ activeProject: project }),
}))
