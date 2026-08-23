/** Contratos da API — espelham os schemas Pydantic do backend. */

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
    request_id: string | null
  }
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  session_id: string
}

export interface MessageResponse {
  message: string
  detail?: Record<string, unknown> | null
}

export interface RoleSummary {
  slug: string
  name: string
}

export interface Profile {
  avatar_url: string | null
  phone: string | null
  birth_date: string | null
  city: string | null
  state: string | null
  timezone: string
  locale: string
  theme: 'light' | 'dark' | 'system'
  study_goal: string | null
  bio: string | null
  preferences: Record<string, unknown>
  onboarding_completed_at: string | null
}

export interface User {
  public_id: string
  email: string
  full_name: string
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'DELETED'
  is_superuser: boolean
  email_verified_at: string | null
  last_login_at: string | null
  created_at: string
  roles: RoleSummary[]
}

export interface CurrentUser extends User {
  profile: Profile | null
  permissions: string[]
}

export interface SessionInfo {
  public_id: string
  device_label: string | null
  user_agent: string | null
  ip_address: string | null
  created_at: string
  last_used_at: string | null
  expires_at: string
  is_current: boolean
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface Permission {
  slug: string
  resource: string
  action: string
  description: string
}

export interface Role {
  slug: string
  name: string
  description: string
  is_system: boolean
  permissions: Permission[]
}

export interface AuditLog {
  id: number
  actor_email: string | null
  actor_ip: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  status: string
  meta: Record<string, unknown>
  request_id: string | null
  created_at: string
}

export interface AdminOverview {
  users_total: number
  users_active: number
  users_pending: number
  users_suspended: number
  users_created_last_7_days: number
  sessions_active: number
  logins_last_24h: number
}
