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

// --------------------------------------------------------------------------
// Plano de estudo (Fase 4)
// --------------------------------------------------------------------------
export type StudyTaskKind =
  'THEORY' | 'QUESTIONS' | 'REVIEW' | 'FLASHCARDS' | 'SIMULATION' | 'SPRINT'

export type StudyTaskStatus = 'PENDING' | 'DONE' | 'SKIPPED' | 'RESCHEDULED' | 'DROPPED'

export interface AvailabilityDay {
  weekday: number
  minutes: number
  label: string
}

export interface SubjectShare {
  key: string
  name: string
  share: number
  minutes: number
  breakdown: Record<string, number>
}

export interface StudyPlan {
  public_id: string
  name: string
  status: string
  exam_date: string | null
  starts_on: string
  weekly_minutes_target: number
  generated_at: string | null
  recalculated_at: string | null
  availability: AvailabilityDay[]
  shares: SubjectShare[]
  minutes_by_kind: Record<string, number>
  total_planned_minutes: number
  days_until_exam: number | null
}

export interface StudyTask {
  public_id: string
  scheduled_for: string
  kind: StudyTaskKind
  kind_label: string
  subject_key: string | null
  subject_label: string | null
  color_token: string
  planned_minutes: number
  actual_minutes: number
  status: StudyTaskStatus
  order_index: number
  source: string
  reschedule_count: number
  rescheduled_from: string | null
  score_breakdown: Record<string, unknown>
}

export interface TodayMission {
  day: string
  plan_public_id: string
  plan_name: string
  days_until_exam: number | null
  planned_minutes: number
  done_minutes: number
  overdue_count: number
  tasks: StudyTask[]
}

export interface CalendarDay {
  day: string
  planned_minutes: number
  done_minutes: number
  tasks: StudyTask[]
}

export interface StudyCalendar {
  start: string
  end: string
  exam_date: string | null
  days: CalendarDay[]
}

export interface RebalanceResult {
  rescheduled: number
  dropped: number
  dropped_minutes: number
  days_touched: number
  summary: string
}

export interface StudySession {
  public_id: string
  status: 'RUNNING' | 'PAUSED' | 'FINISHED' | 'ABANDONED'
  kind: string
  subject_key: string | null
  subject_label: string | null
  started_at: string
  ended_at: string | null
  focus_seconds: number
  pause_seconds: number
  notes: string | null
  task_public_id: string | null
}

export interface SubjectProgress {
  subject_key: string
  subject_label: string
  color_token: string
  planned_minutes: number
  studied_minutes: number
  tasks_done: number
  tasks_skipped: number
  completion: number
  last_studied_at: string | null
}

// --------------------------------------------------------------------------- //
// Questões e simulados
// --------------------------------------------------------------------------- //
export type QuestionDifficulty = 'EASY' | 'MEDIUM' | 'HARD'
export type QuestionStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED' | 'NEEDS_REVIEW'
export type QuestionOrigin = 'OFFICIAL' | 'AI_GENERATED' | 'EDITORIAL'
export type SimulationKind =
  'OFFICIAL' | 'BOARD' | 'ERRORS' | 'FINAL_STRETCH' | 'FLASH' | 'CUSTOM' | 'ADAPTIVE'

export interface Alternative {
  public_id: string
  letter: string
  content: string
}

export interface AlternativeAdmin extends Alternative {
  is_correct: boolean
  feedback: string | null
}

export interface QuestionStats {
  attempts: number
  /** Nulo enquanto a amostra for pequena: a tela mostra “dados insuficientes”. */
  accuracy: number | null
  average_time_seconds: number | null
}

export interface Question {
  public_id: string
  statement: string
  kind: string
  difficulty: QuestionDifficulty
  origin: QuestionOrigin
  year: number | null
  subject_name: string | null
  tags: string[]
  alternatives: Alternative[]
  stats: QuestionStats | null
}

export interface QuestionAdmin extends Omit<Question, 'alternatives'> {
  status: QuestionStatus
  explanation: string | null
  source_note: string | null
  alternatives: AlternativeAdmin[]
  ai_suggestion: Record<string, unknown>
  created_at: string
}

export interface AnswerFeedback {
  is_correct: boolean
  is_blank: boolean
  selected_letter: string | null
  correct_letter: string | null
  correct_feedback: string | null
  selected_feedback: string | null
  explanation: string | null
  time_seconds: number
}

export interface AttemptHistoryItem {
  public_id: string
  question_public_id: string
  question_statement: string
  selected_letter: string | null
  is_correct: boolean
  is_blank: boolean
  time_seconds: number
  created_at: string
}

export interface ImportSummary {
  created: number
  skipped_duplicates: number
  errors: string[]
}

export interface ClassificationSuggestion {
  subject: string | null
  topic: string | null
  difficulty: QuestionDifficulty | null
  tags: string[]
  confidence: number | null
  rationale: string | null
  model: string | null
  prompt_version: string | null
  applied: boolean
}

export interface Simulation {
  public_id: string
  kind: SimulationKind
  name: string
  questions_count: number
  duration_minutes: number | null
  config: Record<string, unknown>
  created_at: string
}

export interface SubjectResult {
  subject_id: number | null
  subject_name: string
  total: number
  correct: number
  wrong: number
  blank: number
  accuracy: number
  average_time_seconds: number
}

export interface DifficultyResult {
  difficulty: QuestionDifficulty
  total: number
  correct: number
  accuracy: number
}

export interface SimulationAnalysis {
  score: number
  accuracy: number
  total: number
  correct: number
  wrong: number
  blank: number
  total_time_seconds: number
  average_time_seconds: number
  previous_accuracy: number | null
  accuracy_delta: number | null
  by_subject: SubjectResult[]
  by_difficulty: DifficultyResult[]
  weakest_subjects: string[]
  strongest_subjects: string[]
  recommendations: string[]
}

export interface SimulationAttempt {
  public_id: string
  status: 'IN_PROGRESS' | 'PAUSED' | 'FINISHED' | 'ABANDONED'
  started_at: string
  finished_at: string | null
  elapsed_seconds: number
  correct_count: number
  wrong_count: number
  blank_count: number
  score: number | null
  simulation: Simulation | null
  analysis: Partial<SimulationAnalysis>
}

export interface SimulationRunQuestion {
  order_index: number
  question: Question
  selected_letter: string | null
}

export interface SimulationRun {
  attempt: SimulationAttempt
  questions: SimulationRunQuestion[]
  /** Nulo quando o simulado não tem tempo definido. */
  remaining_seconds: number | null
}

// --------------------------------------------------------------------------- //
// Inteligência: incidência, DNA da banca, prioridade e erros
// --------------------------------------------------------------------------- //
export interface IncidenceRow {
  subject_name: string
  topic_name: string | null
  questions_count: number
  exams_count: number
  incidence_pct: number
  /** Nulo quando a amostra não cobre dois anos — “estável” seria afirmação sem base. */
  trend: number | null
  confidence: number
  board_questions_count: number
}

export interface IncidenceMap {
  board_slug: string
  board_name: string
  period_start_year: number | null
  period_end_year: number | null
  board_questions_count: number
  rows: IncidenceRow[]
  computed_at: string | null
  empty_reason: string | null
}

export interface BoardMetric {
  metric_slug: string
  label: string
  value: number
  unit: string
  detail: Record<string, number>
  sample_questions: number
  sample_exams: number
  period_start_year: number | null
  period_end_year: number | null
  confidence: number
}

export interface BoardDna {
  board_slug: string
  board_name: string
  metrics: BoardMetric[]
  computed_at: string | null
  empty_reason: string | null
}

export interface RecomputeResult {
  board_slug: string
  questions_sampled: number
  incidence_rows: number
  profile_metrics: number
  incidence_blocked: string | null
  profile_blocked: string | null
}

export interface PriorityContribution {
  key: string
  label: string
  points: number
  max_points: number
  detail: string
}

export interface Priority {
  scope_key: string
  label: string
  color_token: string
  score: number
  /** As parcelas somam exatamente `score` — é o “por quê?” do número. */
  contributions: PriorityContribution[]
  missing_signals: string[]
  coverage: number
  computed_at: string | null
}

export interface PriorityList {
  items: Priority[]
  computed_at: string | null
  board_slug: string | null
  notes: string[]
}

export type ErrorCause =
  | 'UNKNOWN_CONTENT'
  | 'INTERPRETATION'
  | 'CONFUSION'
  | 'FORGETTING'
  | 'RUSH'
  | 'TRAP'
  | 'ALTERNATIVE_DOUBT'

export interface TrapPattern {
  public_id: string
  slug: string
  name: string
  category: string
  description: string | null
  detection_hint: string | null
}

export interface ErrorAnalysis {
  public_id: string
  cause: ErrorCause
  cause_label: string
  question_public_id: string
  question_statement: string
  subject_name: string | null
  selected_letter: string | null
  trap_slug: string | null
  trap_name: string | null
  note: string | null
  source: 'USER' | 'AI'
  model_slug: string | null
  rationale: string | null
  /** Sugestão de IA fica falsa até a pessoa confirmar; só então conta. */
  is_confirmed: boolean
  is_resolved: boolean
  created_at: string
}

export interface PendingAttempt {
  attempt_public_id: string
  question_public_id: string
  question_statement: string
  subject_name: string | null
  selected_letter: string | null
  created_at: string
}

export interface CauseSuggestion {
  cause: ErrorCause | null
  cause_label: string | null
  trap_slug: string | null
  confidence: number | null
  rationale: string | null
  study_tip: string | null
  model: string
  prompt_version: string
  confirmed: boolean
}

export interface CauseSummary {
  cause: ErrorCause
  label: string
  count: number
  share: number
  action: string
}

export interface TrapSummary {
  slug: string
  name: string
  count: number
  share: number
}

export interface SubjectErrorSummary {
  subject_name: string
  count: number
  dominant_cause: ErrorCause | null
  dominant_cause_label: string | null
}

export interface ErrorNotebook {
  total: number
  resolved: number
  by_cause: CauseSummary[]
  by_subject: SubjectErrorSummary[]
  traps: TrapSummary[]
  insights: string[]
  /** Por que alguma seção veio vazia. */
  notes: string[]
  causes_catalogue: Record<string, { label: string; action: string }>
}
