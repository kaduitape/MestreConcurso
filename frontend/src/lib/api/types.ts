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
// Estúdio de treinamento
// --------------------------------------------------------------------------
export interface TrainingScene {
  id: number
  type: string
  narration: string
  dialogue: string
  screen_text: string
  keywords: string[]
  emphasis: string[]
  visual_elements: string[]
  duration: number
  transition: string
  character: { emotion?: string; animation?: string; gesture?: string }
  options?: string[]
  correct_option?: number
  feedback?: string
}

export interface TrainingScript {
  title?: string
  objectives?: string[]
  scenes: TrainingScene[]
}

export interface Training {
  public_id: string
  title: string
  subject: string
  topic: string
  character_name: string
  additional_prompt: string | null
  level: string
  style: string
  target_duration_minutes: number
  board_name: string | null
  research_before_generate: boolean
  status: 'DRAFT' | 'GENERATING' | 'READY' | 'PUBLISHED' | 'ARCHIVED'
  script: TrainingScript
  generation_error: string | null
  model_slug: string | null
  generated_at: string | null
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface TrainingInput {
  subject: string
  topic: string
  character_name: string
  additional_prompt?: string
  level: 'BASICO' | 'INTERMEDIARIO' | 'AVANCADO' | 'ESPECIALISTA'
  style:
    | 'AULA'
    | 'HISTORIA'
    | 'MISSAO'
    | 'BATALHA'
    | 'INVESTIGACAO'
    | 'MILITAR'
    | 'DESAFIO'
    | 'REVISAO'
  target_duration_minutes: number
  board_name?: string
  research_before_generate: boolean
}

export interface TrainingProgress {
  status: 'STARTED' | 'COMPLETED'
  current_scene: number
  completed_scenes: number
  focus_seconds: number
  started_at: string
  last_seen_at: string
  completed_at: string | null
  xp_awarded: number
}

export interface TrainingMetrics {
  starts: number
  completions: number
  completion_rate: number
  total_focus_seconds: number
  average_focus_seconds: number
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

// --------------------------------------------------------------------------- //
// Mestre IA
// --------------------------------------------------------------------------- //
export type ChatMode = 'TUTOR' | 'TEACHER'
export type ClaimStatus = 'CITED' | 'COMPUTED' | 'UNSOURCED'
export type ClaimKind = 'FACT' | 'GUIDANCE' | 'STATISTIC'

export interface Conversation {
  public_id: string
  title: string
  mode: ChatMode
  message_count: number
  last_message_at: string | null
  created_at: string
}

export interface Claim {
  text: string
  kind: ClaimKind
  status: ClaimStatus
  quote: string | null
  chunk_id: number | null
  page_number: number | null
  document_title: string | null
  /** Por que a afirmação ficou sem origem conferida. */
  note: string | null
}

export interface ChatSource {
  chunk_id: number
  document_title: string
  page_number: number
  score: number
  excerpt: string
}

export interface ChatMessage {
  public_id: string
  role: 'USER' | 'ASSISTANT'
  content: string
  claims: Claim[]
  sources: ChatSource[]
  computed_context: Record<string, unknown>
  is_refusal: boolean
  refusal_reason: string | null
  /** Fração das afirmações factuais com origem conferida. */
  grounding_ratio: number | null
  model_slug: string | null
  input_tokens: number
  output_tokens: number
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[]
}

export interface TutorVideo {
  public_id: string
  title: string
  url: string
  provider: string
  channel: string | null
  duration_seconds: number | null
  summary: string | null
  verified_at: string | null
}

export interface AskResult {
  message: ChatMessage
  videos: TutorVideo[]
  suggested_terms: { term: string; definition: string }[]
}

export interface TutorStage {
  key: string
  label: string
  detail: string | null
}

export interface VocabularyTerm {
  public_id: string
  term: string
  definition: string
  subject_name: string | null
  /** CITED quando herdou uma citação conferida; GENERATED quando é redação do modelo. */
  origin: 'CITED' | 'GENERATED'
  source_quote: string | null
  source_page: number | null
  source_document: string | null
  times_reviewed: number
  created_at: string
}

export interface VideoAdmin extends TutorVideo {
  subject_name: string | null
  is_active: boolean
  is_verified: boolean
}

// --------------------------------------------------------------------------- //
// Flashcards e repetição espaçada
// --------------------------------------------------------------------------- //
export type CardOrigin = 'USER' | 'AI' | 'QUESTION' | 'ERROR' | 'NOTICE' | 'EDITORIAL'
export type CardRating = 'AGAIN' | 'HARD' | 'GOOD' | 'EASY'
export type CardState = 'NEW' | 'LEARNING' | 'REVIEW' | 'RELEARNING'

export interface Flashcard {
  public_id: string
  front: string
  back: string
  hint: string | null
  tags: string[]
  subject_name: string | null
  /** Governa o selo de procedência exibido na interface. */
  origin: CardOrigin
  source_ref: string | null
  source_quote: string | null
  source_page: number | null
  source_document: string | null
  model_slug: string | null
  is_owned: boolean
  created_at: string
}

export interface CardMemoryState {
  state: CardState
  interval_days: number
  due_on: string
  repetitions: number
  lapses: number
  ease_factor: number
  last_rating: CardRating | null
  postponed_count: number
}

export interface QueueItem {
  card: Flashcard
  state: CardMemoryState
  is_new: boolean
}

export interface QueuePlan {
  review_count: number
  new_count: number
  overdue_count: number
  absence_days: number
  rescheduled_count: number
  /** Frase que explica o que aconteceu com a fila hoje. */
  summary: string
}

export interface ReviewQueue {
  items: QueueItem[]
  plan: QueuePlan
  total_cards: number
  reviewed_today: number
  upcoming: { day: string; count: number }[]
}

export interface ReviewResult {
  interval_days: number
  due_on: string
  state: CardState
  /** Como o intervalo foi calculado — o "por quê?" do próximo encontro. */
  breakdown: Record<string, unknown>
  remaining_today: number
}

export interface ReviewStats {
  total_cards: number
  by_state: Record<string, number>
  due_today: number
  mature_cards: number
  total_reviews: number
  reviewed_today: number
  /** Nulo enquanto não houver revisão registrada. */
  recall_rate: number | null
  ratings: Record<string, number>
  upcoming: { day: string; count: number }[]
}

export interface CardGeneration {
  created: Flashcard[]
  /** Cartões descartados por citação não conferida. */
  discarded: string[]
  skipped_reason: string | null
  model: string | null
  prompt_version: string | null
}

// --------------------------------------------------------------------------- //
// Gamificação
// --------------------------------------------------------------------------- //
export type RankSlug =
  'FERRO' | 'BRONZE' | 'PRATA' | 'OURO' | 'PLATINA' | 'DIAMANTE' | 'MESTRE' | 'GRAO_MESTRE'
export type MissionStatus = 'PENDING' | 'DONE' | 'CLAIMED' | 'EXPIRED'
export type MissionPriority = 'HIGH' | 'MEDIUM' | 'LOW'

export interface LevelInfo {
  level: number
  xp_total: number
  xp_into_level: number
  xp_for_next: number | null
  ratio: number
  is_max: boolean
}

export interface RankComponent {
  key: string
  label: string
  weight: number
  /** Nulo quando o sinal ainda não tem amostra. */
  value: number | null
  points: number
  available: boolean
  detail: string
}

export interface RankInfo {
  slug: RankSlug
  name: string
  color_token: string
  score: number
  /** As contribuições somam exatamente o score. */
  components: RankComponent[]
  missing_signals: string[]
  coverage: number
  next_tier: string | null
  next_tier_name: string | null
  progress_to_next: number
}

export interface StreakInfo {
  current: number
  longest: number
  average: number
  active_days: number
  shields_left: number
  last_qualified_on: string | null
  history: { day: string; qualified: boolean; shielded: boolean }[]
  /** Texto factual, sem linguagem de ameaça. */
  message: string
}

export interface GameProfile {
  level: LevelInfo
  rank: RankInfo
  streak: StreakInfo
  xp_today: number
  missions_completed: number
  achievements_count: number
  metrics: Record<string, number>
  computed_at: string | null
  /** O Mestre Score chega na Fase 9; aqui ele é declarado, não inventado. */
  master_score: number | null
  master_score_low: number | null
  master_score_high: number | null
  master_score_confidence: ConfidenceLevel | null
  master_score_note: string
}

export interface Mission {
  public_id: string
  scope: string
  kind: string
  title: string
  description: string
  target_metric: string
  target_value: number
  current_value: number
  progress_ratio: number
  xp_reward: number
  priority: MissionPriority
  difficulty: string
  estimated_minutes: number
  status: MissionStatus
  /** O número real que gerou a missão. */
  rationale: string
  valid_from: string
}

export interface DailyBoard {
  missions: Mission[]
  completed: number
  total: number
  bonus_xp: number
  bonus_claimed: boolean
  all_done: boolean
  xp_today: number
  has_plan: boolean
  empty_reason: string | null
}

export interface ClaimResult {
  mission: Mission
  xp_awarded: number
  leveled_up: boolean
  level: number
  bonus: { amount: number; reason: string } | null
}

export interface GameAchievement {
  slug: string
  name: string
  description: string
  category: string
  icon: string
  tier: string
  xp_reward: number
  is_secret: boolean
  unlocked: boolean
  unlocked_at: string | null
  current: number
  threshold: number
  ratio: number | null
  blocked_reason: string | null
}

export interface AchievementList {
  items: GameAchievement[]
  unlocked_count: number
  total_visible: number
  secret_count: number
  secret_unlocked: number
}

export interface XPTransaction {
  public_id: string
  event_kind: string
  amount: number
  reason: string
  capped: boolean
  cap_reason: string | null
  day: string
  created_at: string
}

// --------------------------------------------------------------------------- //
// Gamificação — Fase 2: telas comparativas
// --------------------------------------------------------------------------- //
export interface RankPoint {
  day: string
  rank_slug: RankSlug
  rank_score: number
  /** XP ao lado do rank: acumular e dominar são coisas diferentes. */
  xp_total: number
  level: number
}

export interface RankHistory {
  points: RankPoint[]
  first: RankPoint | null
  last: RankPoint | null
  /** Nulo com menos de duas fotos: uma medição não é tendência. */
  delta: number | null
  empty_reason: string | null
}

export interface SubjectScore {
  subject_id: number | null
  subject_name: string
  answers: number
  correct: number
  you: number
  board: number
  is_sufficient: boolean
  insufficient_reason: string | null
}

export interface BattleWeek {
  week_start: string
  answers: number
  accuracy: number
}

export interface BoardBattle {
  board_slug: string
  board_name: string
  answers: number
  correct: number
  /** you + board somam 100 quando há placar. */
  you: number
  board: number
  is_sufficient: boolean
  is_winning: boolean
  subjects: SubjectScore[]
  evolution: BattleWeek[]
  empty_reason: string | null
}

export type MilestoneState = 'DONE' | 'CURRENT' | 'PENDING'

export interface Milestone {
  key: string
  label: string
  description: string
  state: MilestoneState
  current: number
  target: number
  ratio: number
  detail: string
}

export interface Journey {
  milestones: Milestone[]
  current_key: string | null
  completed: number
  total: number
  days_until_exam: number | null
  /** Obrigatório na tela: a jornada não prevê aprovação. */
  disclaimer: string
  empty_reason: string | null
}

export type TerritoryState = 'LOCKED' | 'STARTED' | 'STUDYING' | 'MASTERED' | 'NEEDS_REVIEW'

export interface TerritoryPart {
  key: string
  label: string
  weight: number
  value: number | null
  points: number
  available: boolean
  detail: string
}

export interface Territory {
  subject_key: string
  subject_name: string
  color_token: string
  subject_id: number | null
  state: TerritoryState
  mastery: number
  parts: TerritoryPart[]
  missing_signals: string[]
  studied_minutes: number
  planned_minutes: number
  days_since_studied: number | null
  note: string
}

export interface TerritoryMap {
  territories: Territory[]
  mastered: number
  needs_review: number
  empty_reason: string | null
}

// --------------------------------------------------------------------------- //
// Gamificação — Fase 3: temporadas, ligas e desafios
// --------------------------------------------------------------------------- //
export interface SeasonReward {
  slug: string
  label: string
  /** Para que serve. Prêmio sem utilidade declarada não existe aqui. */
  utility: string
  criterion: string
}

export interface SeasonStanding {
  seasonal_xp: number
  qualified_days: number
  questions: number
  challenges: number
  position: number | null
  participants: number
}

export interface Season {
  slug: string | null
  name: string | null
  description: string | null
  starts_on: string | null
  ends_on: string | null
  days_left: number | null
  progress: number
  standing: SeasonStanding | null
  rewards: SeasonReward[]
  missed_rewards: SeasonReward[]
  /** A temporada mede esforço; quem mede aprendizado é o rank. */
  note: string
  empty_reason: string | null
}

export interface SeasonHistoryEntry {
  season_name: string
  context_label: string
  seasonal_xp: number
  qualified_days: number
  position: number | null
  participants: number
  rewards: SeasonReward[]
  closed_at: string | null
}

export interface LeagueMember {
  position: number
  label: string
  seasonal_xp: number
  active_days: number
  is_you: boolean
  /** Falso quando o candidato permanece anônimo — o padrão. */
  is_named: boolean
}

export interface League {
  context_label: string
  participants: number
  division_index: number
  division_label: string
  members: LeagueMember[]
  your_position: number | null
  your_division_position: number | null
  note: string
  empty_reason: string | null
}

export interface LeaguePreferences {
  opt_out: boolean
  display_name: string | null
}

/** `BATTLE` existe no servidor mas não é oferecido em Desafios: tem tela própria. */
export type ChallengeModeKey = 'BOSS' | 'SURVIVAL' | 'COMBO' | 'TIME_ATTACK' | 'BATTLE'

export interface ChallengeMode {
  mode: ChallengeModeKey
  name: string
  description: string
  questions: number
  lives: number | null
  time_limit_seconds: number | null
  /** O critério de vitória, escrito. */
  rule: string
}

export interface RunState {
  answered: number
  correct: number
  wrong: number
  lives_left: number | null
  combo: number
  best_combo: number
  multiplier: number
  elapsed_seconds: number
  seconds_left: number | null
  questions_left: number
  /** Nulo sem resposta alguma: zero de zero não é zero por cento. */
  accuracy: number | null
  is_over: boolean
  over_reason: string | null
}

export interface RunScoreLine {
  label: string
  value: string
}

export interface RunScore {
  score: number
  xp: number
  achieved: boolean
  headline: string
  /** A conta aberta do XP da rodada. */
  breakdown: RunScoreLine[]
}

export interface GameRun {
  public_id: string
  mode: ChallengeModeKey
  mode_name: string
  status: 'RUNNING' | 'FINISHED' | 'ABANDONED'
  subject_label: string | null
  /** Por que estas questões e não outras. */
  selection: Record<string, unknown>
  state: RunState
  question: Question | null
  score: RunScore | null
  xp_awarded: number
  started_at: string
  ended_at: string | null
}

export interface RunAnswerResult {
  run: GameRun
  is_correct: boolean
  correct_letter: string | null
  selected_feedback: string | null
  correct_feedback: string | null
  explanation: string | null
}

export interface RunHistoryEntry {
  public_id: string
  mode: ChallengeModeKey
  mode_name: string
  status: string
  score: number
  best_combo: number
  xp_awarded: number
  achieved: boolean
  subject_label: string | null
  summary: Record<string, unknown>
  ended_at: string | null
}

// --------------------------------------------------------------------------- //
// Gamificação — Fase 4: duelos, eventos, Modo Guerra e card compartilhável
// --------------------------------------------------------------------------- //
export interface DuelSide {
  display_name: string
  answered: number
  correct: number
  time_seconds: number
  finished: boolean
}

export type DuelOutcome = 'WIN' | 'LOSS' | 'TIE' | 'WALKOVER' | 'EXPIRED' | 'UNDECIDED'

export interface Duel {
  public_id: string
  /** Código curto que o candidato compartilha para convidar alguém. */
  code: string
  status: string
  outcome: DuelOutcome
  /** A frase do resultado. Vitória por ausência é dita com esse nome. */
  headline: string
  lines: string[]
  is_challenger: boolean
  challenger: DuelSide
  opponent: DuelSide | null
  you_won: boolean | null
  my_run: GameRun | null
  expires_at: string
  resolved_at: string | null
}

export interface DuelHistoryEntry {
  public_id: string
  code: string
  status: string
  outcome: DuelOutcome | null
  headline: string
  is_challenger: boolean
  you_won: boolean | null
  resolved_at: string | null
}

export interface EventGoal {
  metric: string
  label: string
  current: number
  target: number
  ratio: number
  completed: boolean
}

export interface SpecialEvent {
  slug: string
  name: string
  description: string | null
  starts_on: string
  ends_on: string
  days_left: number | null
  is_open: boolean
  goals: EventGoal[]
  completed: boolean
  completed_goals: number
  total_goals: number
  reward_label: string | null
  /** Prêmio sem utilidade declarada não é aceito na criação. */
  reward_utility: string | null
  note: string
}

export interface WarDay {
  day: string
  minutes: number
  questions: number
  met: boolean
  is_future: boolean
}

export interface WarCampaign {
  public_id: string | null
  status: string | null
  starts_on: string | null
  days: number
  daily_minutes: number
  daily_questions: number
  days_met: number
  days_missed: number
  days_left: number
  ratio: number
  is_over: boolean
  succeeded: boolean
  /** Texto factual: descreve o período, não julga o candidato. */
  message: string
  schedule: WarDay[]
  warnings: { field?: string; message: string }[]
  empty_reason: string | null
}

export interface CardStat {
  key: string
  label: string
  value: string
  detail: string
}

export interface ShareCard {
  display_name: string
  headline: string
  stats: CardStat[]
  /** O que ficou de fora, com o motivo. */
  omitted: string[]
  footer: string
}

export interface PublishedCard extends ShareCard {
  public_id: string
  token: string
  revoked_at: string | null
  created_at: string
}

// --------------------------------------------------------------------------- //
// Analytics (Fase 9) — Mestre Score, projeção, caminho e painéis
// --------------------------------------------------------------------------- //
export type ConfidenceLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'

export interface ScoreComponent {
  key: string
  label: string
  weight: number
  /** Pontos na escala 0–1000. As parcelas somam exatamente o score exibido. */
  points: number
  value: number | null
  low: number | null
  high: number | null
  sample: number
  available: boolean
  confidence: ConfidenceLevel
  detail: string
}

export interface MasterScore {
  value: number
  /** A faixa aparece na tela junto do valor, sempre. */
  low: number
  high: number
  band: string
  band_note: string
  confidence: ConfidenceLevel
  available_weight: number
  components: ScoreComponent[]
  missing_signals: string[]
  interval_note: string
  empty_reason: string | null
}

export interface ScorePoint {
  day: string
  value: number
  low: number
  high: number
  band: string
  confidence: ConfidenceLevel
}

export interface ScoreHistory {
  points: ScorePoint[]
  delta: number | null
  empty_reason: string | null
}

export interface SubjectProjection {
  subject_id: number | null
  name: string
  questions: number
  weight: number
  is_eliminatory: boolean
  accuracy: number | null
  low: number | null
  high: number | null
  expected: number | null
  expected_low: number | null
  expected_high: number | null
  sample: number
  included: boolean
  confidence: ConfidenceLevel
  detail: string
  risk_note: string | null
}

export interface ExamProjection {
  total_questions: number
  covered_questions: number
  /** Fatia da prova coberta pela estimativa. Sempre exibida. */
  coverage: number
  expected: number | null
  expected_low: number | null
  expected_high: number | null
  expected_percent: number | null
  subjects: SubjectProjection[]
  confidence: ConfidenceLevel
  is_reliable: boolean
  /** A plataforma não estima chance de aprovação. */
  disclaimer: string
  empty_reason: string | null
}

export type PathActionKind = 'MEASURE' | 'IMPROVE' | 'MAINTAIN'

export interface PathStep {
  subject_id: number | null
  subject_name: string
  kind: PathActionKind
  label: string
  action: string
  /** O número real que gerou a recomendação. */
  evidence: string
  questions_at_stake: number
  is_eliminatory: boolean
  risk_note: string | null
}

export interface StudyPath {
  steps: PathStep[]
  disclaimer: string
  empty_reason: string | null
}

export interface ChartPoint {
  label: string
  value: number
  low: number | null
  high: number | null
  sample: number
  day: string | null
}

export interface AnalyticsChart {
  key: string
  title: string
  /** Para que serve decidir. Nenhum gráfico entra sem isto. */
  decision: string
  unit: string
  points: ChartPoint[]
  empty_reason: string | null
  note: string
}

export interface AnalyticsOverview {
  master_score: MasterScore
  projection: ExamProjection
  path: StudyPath
  charts: AnalyticsChart[]
}

// --------------------------------------------------------------------------- //
// Comercial (Fase 10) — planos, assinatura, limites e faturamento
// --------------------------------------------------------------------------- //
export interface PlanEntitlement {
  feature: string
  label: string
  /** Falso = sem acesso. Diferente de `limit: null`, que é sem teto. */
  enabled: boolean
  limit: number | null
  period: 'DAY' | 'MONTH' | 'TOTAL'
  description: string
}

export interface BillingPlan {
  slug: string
  name: string
  description: string
  price_cents: number
  months: number
  trial_days: number
  is_public: boolean
  entitlements: PlanEntitlement[]
}

export interface Quota {
  feature: string
  label: string
  allowed: boolean
  /** Nulo = sem teto. */
  limit: number | null
  used: number
  remaining: number | null
  period: string
  resets_on: string | null
  /** Vazio quando permitido; explica a recusa quando não. */
  reason: string
}

export interface SubscriptionInfo {
  public_id: string | null
  plan_slug: string
  plan_name: string
  status: string
  status_label: string
  started_on: string | null
  current_period_start: string | null
  current_period_end: string | null
  trial_ends_on: string | null
  grace_ends_on: string | null
  canceled_at: string | null
  scheduled_plan_slug: string | null
  is_paid: boolean
}

export interface CouponResult {
  valid: boolean
  discount_cents: number
  final_cents: number
  reason: string
  description: string
}

export interface BillingPayment {
  public_id: string
  reference: string
  status: string
  amount_cents: number
  discount_cents: number
  checkout_url: string | null
  paid_at: string | null
  created_at: string
}

export interface SubscribeResult {
  subscription: SubscriptionInfo
  payment: BillingPayment | null
  coupon: CouponResult | null
  detail: string
}

export interface ChangePlanResult {
  subscription: SubscriptionInfo
  kind: 'UPGRADE' | 'DOWNGRADE' | 'SAME'
  immediate: boolean
  credit_cents: number
  charge_cents: number
  reason: string
  payment: BillingPayment | null
}

export interface Invoice {
  description: string
  amount_cents: number
  discount_cents: number
  credit_cents: number
  total_cents: number
  period_start: string | null
  period_end: string | null
  created_at: string
}

export interface SaasMetric {
  key: string
  label: string
  /** Nulo quando não há base para calcular — nunca zero por omissão. */
  value: number | null
  unit: string
  /** O denominador ou a amostra, escritos. */
  basis: string
  empty_reason: string | null
}

export interface SaasDashboard {
  metrics: SaasMetric[]
  period_start: string | null
  period_end: string | null
}

// --------------------------------------------------------------------------- //
// Batalha RPG
// --------------------------------------------------------------------------- //
export type BattleLayout = 'monster-arena' | 'compact-answer'
export type BattleViewport = 'desktop' | 'tablet' | 'mobile'

export interface BattleMonster {
  letter: string
  species: string
  name: string
  /** Silhueta desenhada no cliente; arte em WebP pode substituí-la depois. */
  shape: string
  color_token: string
  accent_token: string
  variant: number
}

export interface BattleStatus {
  player_hp: number
  player_max_hp: number
  player_hp_ratio: number
  enemy_hp: number
  enemy_max_hp: number
  enemy_hp_ratio: number
  answered: number
  correct: number
  wrong: number
  questions: number
  is_over: boolean
  victory: boolean
  defeat: boolean
  outcome_reason: string | null
  /** Fase 2 — tudo derivado das respostas, como o HP. */
  combo: number
  best_combo: number
  coins: number
  coins_earned: number
  coins_spent: number
  criticals: number
}

export type BattlePowerKey = 'SHIELD' | 'ELIMINATE' | 'HINT'

/** As réguas do combate: combo, crítico, moedas e preço dos poderes. */
export interface BattleCombatSettings {
  critical_seconds: number
  critical_bonus_percent: number
  combo_damage_percent: number
  max_combo_steps: number
  coins_per_correct: number
  coins_per_combo_step: number
  starting_coins: number
  shield_cost: number
  eliminate_cost: number
  hint_cost: number
}

export interface BattlePowerOffer {
  power: BattlePowerKey
  label: string
  description: string
  cost: number
  affordable: boolean
  used: boolean
  removed_letter: string | null
  hint: string | null
}

/** As réguas que decidem o layout — vêm do banco, ajustáveis sem deploy. */
export interface BattleLayoutSettings {
  short_answer_max: number
  short_average_max: number
  tablet_short_answer_max: number
  tablet_short_average_max: number
  mobile_short_answer_max: number
  mobile_short_average_max: number
  max_options_for_arena: number
  chars_per_line_desktop: number
  chars_per_line_tablet: number
  chars_per_line_mobile: number
  max_lines_for_arena: number
}

export interface Battle {
  run: GameRun
  enemy_species: string
  enemy_name: string
  enemy_shape: string
  enemy_color_token: string
  enemy_accent_token: string
  status: BattleStatus
  monsters: BattleMonster[]
  layout: BattleLayout
  layout_reason: string
  settings: BattleLayoutSettings
  combat: BattleCombatSettings
  powers: BattlePowerOffer[]
  /** Letras eliminadas nesta questão: a tela não as renderiza. */
  removed_letters: string[]
  hint: string | null
}

export interface BattleAnswerResult {
  battle: Battle
  is_correct: boolean
  correct_letter: string | null
  selected_feedback: string | null
  correct_feedback: string | null
  explanation: string | null
  /** Quem apanhou depende de quem errou. `null` quando o escudo absorveu. */
  damage: number
  damage_target: 'enemy' | 'player' | null
  combo: number
  is_critical: boolean
  shielded: boolean
  coins: number
}

export interface BattleSetting {
  key: string
  label: string
  value: number
}

export interface GameRule {
  key: string
  label: string
  xp_value: number
  daily_cap: number
  is_enabled: boolean
  updated_at: string
}
