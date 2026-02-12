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
  projects: ProjectResponse[]
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
  contexts: ContextResponse[]
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
  variables: VariableResponse[]
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

// ── Settings: Nested Config Types ────────────────────────────────────────

export interface ProviderConfig {
  mode: string        // "anthropic" | "zai" | "local"
  api_key_set: boolean
  base_url: string | null
  custom_models: string[]
}

export interface ProviderConfigUpdate {
  mode?: string
  api_key?: string
  base_url?: string
}

export interface ProxyConfig {
  enabled: boolean
  type: string        // "http" | "https" | "socks5"
  host: string
  port: number
  username: string
  password_set: boolean
  no_proxy: string
}

export interface ProxyConfigUpdate {
  enabled?: boolean
  type?: string
  host?: string
  port?: number
  username?: string
  password?: string
  no_proxy?: string
}

export interface RuntimeConfig {
  max_turns: number
  timeout: number
  step_streaming: boolean
  permission_mode: string
  yolo_mode: boolean
  backend: string
}

export interface RuntimeConfigUpdate {
  max_turns?: number
  timeout?: number
  step_streaming?: boolean
  permission_mode?: string
  yolo_mode?: boolean
  backend?: string
}

export interface ClaudeAccountInfo {
  active: boolean
  credentials_exist: boolean
  subscription_type: string | null
  rate_limit_tier: string | null
  expires_at: string | null
  scopes: string[]
}

export interface InfraConfig {
  ssh_host: string
  ssh_port: number
  ssh_user: string
  gitlab_url: string
  gitlab_token_set: boolean
  alert_cpu: number
  alert_memory: number
  alert_disk: number
  debug: boolean
  log_level: string
}

export interface InfraConfigUpdate {
  ssh_host?: string
  ssh_port?: number
  ssh_user?: string
  gitlab_url?: string
  gitlab_token?: string
  alert_cpu?: number
  alert_memory?: number
  alert_disk?: number
  debug?: boolean
  log_level?: string
}

export interface ProviderValidateRequest {
  provider: string
  api_key: string
  base_url?: string
}

export interface ProviderValidateResponse {
  valid: boolean
  models: string[]
  message: string
}

export interface CustomModelRequest {
  provider: string
  model_id: string
}

export interface CustomModelResponse {
  provider: string
  models: string[]
  custom_models: string[]
}

export interface CredentialsUploadRequest {
  credentials_json: string
}

export interface CredentialsUploadResponse {
  success: boolean
  subscription_type: string | null
  rate_limit_tier: string | null
  message: string
}

export interface ProxyTestRequest {
  type: string
  host: string
  port: number
  username?: string
  password?: string
}

export interface ProxyTestResponse {
  success: boolean
  message: string
  latency_ms: number | null
}

export interface SettingsResponse {
  // Existing top-level fields (backward-compatible aliases)
  yolo_mode: boolean
  step_streaming: boolean
  backend: string
  model: string
  provider: string
  available_models: string[]
  permission_mode: string
  language: string
  // New nested config objects
  provider_config?: ProviderConfig
  proxy?: ProxyConfig
  runtime?: RuntimeConfig
  claude_account?: ClaudeAccountInfo
  infra?: InfraConfig
}

export interface UpdateSettingsRequest {
  yolo_mode?: boolean
  step_streaming?: boolean
  backend?: string
  model?: string
  provider?: string  // "anthropic" | "zai" | "local"
  permission_mode?: string
  language?: string
  // Nested config updates
  provider_config?: ProviderConfigUpdate
  proxy?: ProxyConfigUpdate
  runtime?: RuntimeConfigUpdate
  infra?: InfraConfigUpdate
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
