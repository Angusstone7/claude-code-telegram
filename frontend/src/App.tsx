import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ChatPage } from '@/pages/ChatPage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { FileBrowserPage } from '@/pages/FileBrowserPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { DockerPage } from '@/pages/DockerPage'
import { PluginsPage } from '@/pages/PluginsPage'
import { SSHPage } from '@/pages/SSHPage'
import { GitLabPage } from '@/pages/GitLabPage'
import { UsersPage } from '@/pages/UsersPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="files" element={<FileBrowserPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="docker" element={<DockerPage />} />
              <Route path="plugins" element={<PluginsPage />} />
              <Route path="ssh" element={<SSHPage />} />
              <Route path="gitlab" element={<GitLabPage />} />
              <Route path="users" element={<UsersPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
