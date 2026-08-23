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

// --------------------------------------------------------------------------
// Configuração de IA
// --------------------------------------------------------------------------
export interface AIModel {
  slug: string
  display_name: string
  kind: 'chat' | 'embedding' | 'rerank'
  context_window: number | null
  max_output_tokens: number | null
  input_cost_per_1k: string | null
  output_cost_per_1k: string | null
  supports_tools: boolean
  supports_json: boolean
  is_active: boolean
}

export interface AIProvider {
  slug: string
  display_name: string
  base_url: string | null
  organization: string | null
  is_active: boolean
  has_api_key: boolean
  api_key_hint: string | null
  api_key_set_at: string | null
  last_tested_at: string | null
  last_test_status: 'OK' | 'FAILED' | null
  last_test_message: string | null
  models: AIModel[]
}

export interface AIAvailableProviders {
  available: string[]
  configured: string[]
}

export interface ConnectionCheck {
  ok: boolean
  message: string
  latency_ms: number
  models_available: number
  sample_models: string[]
}

export interface AIFeatureBinding {
  feature: string
  label: string
  description: string
  is_enabled: boolean
  provider_slug: string | null
  model_slug: string | null
  temperature: string | null
  max_output_tokens: number | null
  cache_ttl_hours: number | null
}

export interface AICacheStats {
  entries: number
  total_hits: number
  tokens_stored: number
  tokens_saved: number
  cost_saved_cents: string
  expired_entries: number
}

// --------------------------------------------------------------------------
// Catálogo
// --------------------------------------------------------------------------
export interface ExamBoard {
  public_id: string
  slug: string
  name: string
  short_name: string
  aliases: string[]
  website: string | null
  logo_url: string | null
  description: string | null
  is_active: boolean
}

export interface Organization {
  public_id: string
  slug: string
  name: string
  short_name: string
  sphere: 'FEDERAL' | 'ESTADUAL' | 'MUNICIPAL' | 'DISTRITAL'
  uf: string | null
  website: string | null
  logo_url: string | null
  is_active: boolean
}

export interface Subject {
  public_id: string
  slug: string
  name: string
  area: string | null
  color_token: string
  description: string | null
  is_active: boolean
  sort_order: number
}

export interface Topic {
  public_id: string
  name: string
  slug: string
  depth: number
  path: string
  sort_order: number
  description: string | null
  parent_public_id: string | null
}

export interface PositionSubject {
  subject: Subject
  weight: string
  questions_count: number | null
  min_score: string | null
  is_eliminatory: boolean
  source: string
}

export interface Position {
  public_id: string
  name: string
  education_level: string | null
  salary_cents: number | null
  vacancies: number | null
  cr_vacancies: number | null
  workload_hours: number | null
  requirements: string | null
  questions_count: number | null
  exam_duration_minutes: number | null
  subjects: PositionSubject[]
}

export type CompetitionStatus = 'ANNOUNCED' | 'OPEN' | 'IN_PROGRESS' | 'CONCLUDED' | 'CANCELED'

export interface CompetitionSummary {
  public_id: string
  slug: string
  name: string
  year: number
  status: CompetitionStatus
  exam_date: string | null
  vacancies_total: number | null
  salary_max_cents: number | null
  is_published: boolean
  organization: Organization
  exam_board: ExamBoard | null
}

export interface Competition extends CompetitionSummary {
  education_level: string | null
  registration_start: string | null
  registration_end: string | null
  source_url: string | null
  notes: string | null
  positions: Position[]
}

export interface NoticeFile {
  public_id: string
  original_name: string
  mime_type: string
  size_bytes: number
  checksum_sha256: string
  page_count: number | null
  status: string
  error_message: string | null
  created_at: string
}

export interface Notice {
  public_id: string
  title: string
  kind: 'MAIN' | 'RECTIFICATION' | 'ADDENDUM' | 'RESULT'
  number: string | null
  published_at: string | null
  source_url: string | null
  status: string
  summary: string | null
  created_at: string
  files: NoticeFile[]
}

export interface BoardKnowledgeEntry {
  id: number
  kind: string
  entry_key: string
  title: string
  content: string | null
  data: Record<string, unknown>
  source: 'COMPUTED' | 'AI' | 'EDITORIAL' | 'OFFICIAL'
  confidence: string | null
  sample_exams: number | null
  sample_questions: number | null
  period_start_year: number | null
  period_end_year: number | null
  provider_slug: string | null
  model_slug: string | null
  prompt_version: string | null
  input_tokens: number
  output_tokens: number
  collected_at: string
  expires_at: string | null
  is_expired: boolean
}

export interface BoardKnowledgeCoverage {
  total: number
  by_kind: Record<string, number>
  by_source: Record<string, number>
  expired: number
  ai_tokens_stored: number
}

// --------------------------------------------------------------------------
// Análise de edital (Fase 3)
// --------------------------------------------------------------------------
export type EvidenceLevel = 'OFFICIAL' | 'CONFIRMED' | 'INFERRED' | 'NOT_FOUND'

export type StepStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'SKIPPED' | 'FAILED'

export interface AnalysisStep {
  key: string
  label: string
  status: StepStatus
  detail: string | null
  at: string | null
}

export interface AnalysisState {
  notice_public_id: string
  status: string
  steps: AnalysisStep[]
  started_at: string | null
  finished_at: string | null
  error: string | null
  coverage: Record<string, number>
}

export interface AnalysisStarted {
  notice_public_id: string
  status: string
  message: string
  executed_inline: boolean
}

export interface NoticeFact {
  id: number
  field_path: string
  label: string
  value: unknown
  evidence_level: EvidenceLevel
  confidence: number | null
  page_number: number | null
  quote: string | null
  extracted_by: string
  model_slug: string | null
  prompt_version: string | null
}

export interface NoticeSubjectView {
  public_id: string
  name: string
  weight: number | null
  questions_count: number | null
  topics_count: number
  topics: string[]
  evidence_level: EvidenceLevel
  page_number: number | null
}

export interface NoticeEventView {
  kind: string
  title: string
  date_start: string | null
  date_end: string | null
  is_critical: boolean
  days_until: number | null
  evidence_level: EvidenceLevel
  page_number: number | null
}

export interface AttentionPoint {
  kind: string
  title: string
  detail: string
}

export interface Radiography {
  notice_public_id: string
  title: string
  status: string
  exam_date: string | null
  days_until_exam: number | null
  page_count: number | null
  subjects_count: number
  topics_count: number
  questions_count: number | null
  vacancies: number | null
  salary_cents: number | null
  facts: NoticeFact[]
  subjects: NoticeSubjectView[]
  events: NoticeEventView[]
  critical_events: NoticeEventView[]
  largest_subjects: NoticeSubjectView[]
  attention_points: AttentionPoint[]
  coverage: Record<string, number>
}
