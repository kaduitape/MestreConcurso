import { api } from './client'
import type {
  AnswerFeedback,
  AttemptHistoryItem,
  ClassificationSuggestion,
  ImportSummary,
  MessageResponse,
  Page,
  Question,
  QuestionAdmin,
  QuestionDifficulty,
  QuestionStatus,
  Simulation,
  SimulationAttempt,
  SimulationKind,
  SimulationRun,
} from './types'

export interface QuestionFilters {
  page: number
  page_size: number
  search?: string
  subject?: string
  difficulty?: QuestionDifficulty | ''
  board?: string
  year?: number | ''
  status?: QuestionStatus | ''
}

function toSearch(filters: QuestionFilters): string {
  const search = new URLSearchParams({
    page: String(filters.page),
    page_size: String(filters.page_size),
  })
  for (const key of ['search', 'subject', 'difficulty', 'board', 'status'] as const) {
    const value = filters[key]
    if (value) search.set(key, String(value))
  }
  if (filters.year) search.set('year', String(filters.year))
  return search.toString()
}

export interface AlternativeInput {
  letter: string
  content: string
  is_correct: boolean
  feedback?: string | null
}

export interface QuestionInput {
  statement: string
  alternatives: AlternativeInput[]
  difficulty?: QuestionDifficulty
  status?: QuestionStatus
  year?: number | null
  explanation?: string | null
  source_note?: string | null
  tags?: string[]
  subject_public_id?: string | null
  board_slug?: string | null
}

export const questionsApi = {
  search: (filters: QuestionFilters) =>
    api.get<Page<Question>>(`/questions?${toSearch(filters)}`),

  answer: (publicId: string, input: { letter: string | null; time_seconds?: number }) =>
    api.post<AnswerFeedback>(`/questions/${publicId}/answer`, {
      letter: input.letter,
      time_seconds: input.time_seconds ?? 0,
    }),

  history: (params: { page: number; page_size: number }) =>
    api.get<Page<AttemptHistoryItem>>(
      `/questions/history?page=${params.page}&page_size=${params.page_size}`,
    ),
}

export interface SimulationInput {
  kind: SimulationKind
  questions_count: number
  subject_public_id?: string | null
  board_slug?: string | null
  duration_minutes?: number | null
}

export const simulationsApi = {
  create: (input: SimulationInput) => api.post<Simulation>('/simulations', input),

  start: (publicId: string) => api.post<SimulationRun>(`/simulations/${publicId}/start`),

  attempt: (publicId: string) => api.get<SimulationRun>(`/simulations/attempts/${publicId}`),

  current: () => api.get<SimulationRun | null>('/simulations/current'),

  saveAnswer: (
    attemptPublicId: string,
    input: { question_public_id: string; letter: string | null; time_seconds?: number },
  ) =>
    api.post<MessageResponse>(`/simulations/attempts/${attemptPublicId}/answer`, {
      question_public_id: input.question_public_id,
      letter: input.letter,
      time_seconds: input.time_seconds ?? 0,
    }),

  pause: (publicId: string) =>
    api.post<SimulationAttempt>(`/simulations/attempts/${publicId}/pause`),

  resume: (publicId: string) =>
    api.post<SimulationAttempt>(`/simulations/attempts/${publicId}/resume`),

  finish: (publicId: string) =>
    api.post<SimulationAttempt>(`/simulations/attempts/${publicId}/finish`),

  history: () => api.get<SimulationAttempt[]>('/simulations/history'),
}

export const adminQuestionsApi = {
  list: (filters: QuestionFilters) =>
    api.get<Page<QuestionAdmin>>(`/admin/questions?${toSearch(filters)}`),

  get: (publicId: string) => api.get<QuestionAdmin>(`/admin/questions/${publicId}`),

  create: (input: QuestionInput) => api.post<QuestionAdmin>('/admin/questions', input),

  update: (publicId: string, input: Partial<QuestionInput>) =>
    api.patch<QuestionAdmin>(`/admin/questions/${publicId}`, input),

  remove: (publicId: string) => api.delete<MessageResponse>(`/admin/questions/${publicId}`),

  import: (input: {
    questions: unknown[]
    subject_public_id?: string | null
    board_slug?: string | null
  }) => api.post<ImportSummary>('/admin/questions/import', input),

  suggestClassification: (publicId: string) =>
    api.post<ClassificationSuggestion>(`/admin/questions/${publicId}/suggest-classification`),

  applyClassification: (
    publicId: string,
    input: { subject_public_id?: string | null; difficulty?: QuestionDifficulty | null },
  ) => api.post<QuestionAdmin>(`/admin/questions/${publicId}/apply-classification`, input),
}
