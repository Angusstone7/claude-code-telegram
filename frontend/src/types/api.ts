// ---------------------------------------------------------------------------
// API type definitions – mirrors backend Pydantic schemas
// ---------------------------------------------------------------------------

// ── Auth ──────────────────────────────────────────────────────────────────

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface RefreshResponse {
  access_token: string
  token_type: string
}

// ── Users / Profiles ──────────────────────────────────────────────────────

export interface UserProfile {
  id: string
  username: string
  display_name: string
  telegram_id: number | null
  role: string
  created_at?: string
}

export interface UpdateProfileRequest {
  display_name?: string
  telegram_id?: number | null
}

export interface CreateUserRequest {
  username: string
  password: string
  display_name: string
  role?: string
  telegram_id?: number | null
}

export interface ResetPasswordRequest {
  new_password: string
}

// ── Projects ──────────────────────────────────────────────────────────────

export interface ProjectResponse {
  id: string
  name: string
  path: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface ProjectListResponse {
  items: ProjectResponse[]
  total: number
}

export interface CreateProjectRequest {
  name: string
  path: string
  description?: string
}

// ── Contexts ──────────────────────────────────────────────────────────────

export interface ContextResponse {
  id: string
  project_id: string
  name: string
  messages_count: number
  created_at: string
  updated_at: string
}

export interface ContextListResponse {
  items: ContextResponse[]
  total: number
}

export interface CreateContextRequest {
  name: string
  project_id: string
}

// ── Variables ─────────────────────────────────────────────────────────────

export interface VariableResponse {
  id: string
  key: string
  value: string
  scope: 'global' | 'project'
  project_id: string | null
  created_at: string
  updated_at: string
}

export interface VariableListResponse {
  items: VariableResponse[]
  total: number
}

export interface CreateVariableRequest {
  key: string
  value: string
  scope?: 'global' | 'project'
  project_id?: string | null
}

// ── File Browser ──────────────────────────────────────────────────────────

export interface FileEntry {
  name: string
  path: string
  is_directory: boolean
  size: number | null
  modified_at: string | null
}

export interface FileBrowserResponse {
  current_path: string
  parent_path: string | null
  entries: FileEntry[]
}

export interface MkdirRequest {
  path: string
}

// ── Settings ──────────────────────────────────────────────────────────────

export interface SettingsResponse {
  yolo_mode: boolean
  step_streaming: boolean
  backend: string
  model: string
  available_models: string[]
  permission_mode: string
  language: string
}

export interface UpdateSettingsRequest {
  yolo_mode?: boolean
  step_streaming?: boolean
  backend?: string
  model?: string
  permission_mode?: string
  language?: string
}

// ── Docker Containers ─────────────────────────────────────────────────────

export interface ContainerResponse {
  name: string
  status: string
  image: string
  ports: string[]
  uptime: string | null
  created_at: string | null
}

export interface ContainerListResponse {
  containers: ContainerResponse[]
  total: number
}

export interface ContainerLogsResponse {
  name: string
  logs: string
  lines: number
}

export interface ContainerActionResponse {
  name: string
  action: string
  success: boolean
  message: string
}

// ── System Metrics ───────────────────────────────────────────────────────

export interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  memory_used_gb: number
  disk_percent: number
  load_avg_1m: number
  active_tasks: number
}

// ── Plugins ───────────────────────────────────────────────────────────────

export interface PluginCommand {
  name: string
  description: string | null
}

export interface PluginResponse {
  name: string
  enabled: boolean
  description: string | null
  source: string | null
  commands: PluginCommand[]
}

export interface PluginListResponse {
  plugins: PluginResponse[]
  total: number
}

// ── SSH ──────────────────────────────────────────────────────────────────

export interface SSHCommandRequest {
  command: string
  timeout?: number
}

export interface SSHCommandResponse {
  command: string
  output: string
  exit_code: number
  executed_at: string
  duration_ms: number
}

export interface SSHHistoryResponse {
  commands: SSHCommandResponse[]
  total: number
}

// ── Chat / Messages ───────────────────────────────────────────────────────

export interface ChatMessageResponse {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tool_use?: ToolInput | null
  created_at: string
}

export interface MessageListResponse {
  items: ChatMessageResponse[]
  total: number
}

// ── Tasks ─────────────────────────────────────────────────────────────────

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number | null
  result: unknown | null
  error: string | null
  created_at: string
  updated_at: string
}

// ── Generic ───────────────────────────────────────────────────────────────

export interface MessageResponse {
  message: string
}

// ── GitLab ───────────────────────────────────────────────────────────────

export interface GitLabProjectResponse {
  id: number
  name: string
  path_with_namespace: string
  web_url: string
  default_branch: string | null
  last_activity_at: string | null
}

export interface GitLabProjectListResponse {
  projects: GitLabProjectResponse[]
  total: number
}

export interface PipelineStageResponse {
  name: string
  status: string
}

export interface PipelineResponse {
  id: number
  status: string
  ref: string
  sha: string
  created_at: string
  updated_at: string | null
  web_url: string | null
  stages: PipelineStageResponse[]
}

export interface PipelineListResponse {
  pipelines: PipelineResponse[]
  total: number
}

// ── Utility ───────────────────────────────────────────────────────────────

export type ToolInput = Record<string, unknown>
