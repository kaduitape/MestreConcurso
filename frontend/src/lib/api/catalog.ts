import { api } from './client'
import type {
  BoardKnowledgeCoverage,
  BoardKnowledgeEntry,
  Competition,
  CompetitionSummary,
  ExamBoard,
  MessageResponse,
  Notice,
  Organization,
  Page,
  Position,
  Subject,
  Topic,
} from './types'

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  const asString = search.toString()
  return asString ? `?${asString}` : ''
}

export interface TopicImportResult {
  created: number
  updated: number
  skipped: number
  errors: string[]
}

export interface ListParams {
  page: number
  page_size: number
  search?: string
}

/** Endpoints do candidato: só enxergam o que está publicado. */
export const catalogApi = {
  competitions: (
    params: ListParams & { exam_board?: string; year?: number; status?: string },
  ) => api.get<Page<CompetitionSummary>>(`/catalog/competitions${query({ ...params })}`),

  competition: (publicId: string) => api.get<Competition>(`/catalog/competitions/${publicId}`),

  competitionNotices: (publicId: string) =>
    api.get<Notice[]>(`/catalog/competitions/${publicId}/notices`),

  boards: (params: { page: number; page_size: number }) =>
    api.get<Page<ExamBoard>>(`/catalog/boards${query({ ...params })}`),

  boardKnowledge: (publicId: string) =>
    api.get<BoardKnowledgeEntry[]>(`/catalog/boards/${publicId}/knowledge`),

  subjects: (params: { page: number; page_size: number }) =>
    api.get<Page<Subject>>(`/catalog/subjects${query({ ...params })}`),

  topics: (subjectPublicId: string) =>
    api.get<Topic[]>(`/catalog/subjects/${subjectPublicId}/topics`),
}

export interface BoardInput {
  name: string
  short_name: string
  website?: string | null
  description?: string | null
  is_active?: boolean
}

export interface OrganizationInput {
  name: string
  short_name: string
  sphere: string
  uf?: string | null
}

export interface CompetitionInput {
  name: string
  year: number
  organization_public_id: string
  exam_board_public_id?: string | null
  status?: string
  vacancies_total?: number | null
  salary_max_cents?: number | null
  registration_start?: string | null
  registration_end?: string | null
  exam_date?: string | null
  source_url?: string | null
  is_published?: boolean
}

export interface PositionInput {
  name: string
  education_level?: string | null
  salary_cents?: number | null
  vacancies?: number | null
  questions_count?: number | null
  exam_duration_minutes?: number | null
}

/** Endpoints administrativos do catálogo. */
export const adminCatalogApi = {
  boards: (params: ListParams) =>
    api.get<Page<ExamBoard>>(`/admin/catalog/boards${query({ ...params })}`),
  createBoard: (input: BoardInput) => api.post<ExamBoard>('/admin/catalog/boards', input),
  updateBoard: (publicId: string, input: Partial<BoardInput>) =>
    api.patch<ExamBoard>(`/admin/catalog/boards/${publicId}`, input),
  deleteBoard: (publicId: string) =>
    api.delete<MessageResponse>(`/admin/catalog/boards/${publicId}`),

  boardKnowledge: (publicId: string) =>
    api.get<BoardKnowledgeEntry[]>(`/admin/catalog/boards/${publicId}/knowledge`),
  boardKnowledgeCoverage: (publicId: string) =>
    api.get<BoardKnowledgeCoverage>(`/admin/catalog/boards/${publicId}/knowledge/coverage`),
  saveBoardKnowledge: (
    publicId: string,
    input: {
      kind: string
      entry_key: string
      title: string
      content?: string | null
      source: string
      sample_exams?: number | null
      sample_questions?: number | null
      period_start_year?: number | null
      period_end_year?: number | null
    },
  ) => api.put<BoardKnowledgeEntry>(`/admin/catalog/boards/${publicId}/knowledge`, input),
  deleteBoardKnowledge: (publicId: string, entryId: number) =>
    api.delete<MessageResponse>(`/admin/catalog/boards/${publicId}/knowledge/${entryId}`),

  organizations: (params: ListParams & { uf?: string }) =>
    api.get<Page<Organization>>(`/admin/catalog/organizations${query({ ...params })}`),
  createOrganization: (input: OrganizationInput) =>
    api.post<Organization>('/admin/catalog/organizations', input),
  updateOrganization: (publicId: string, input: Partial<OrganizationInput>) =>
    api.patch<Organization>(`/admin/catalog/organizations/${publicId}`, input),

  competitions: (
    params: ListParams & { status?: string; exam_board?: string; year?: number },
  ) => api.get<Page<CompetitionSummary>>(`/admin/catalog/competitions${query({ ...params })}`),
  competition: (publicId: string) =>
    api.get<Competition>(`/admin/catalog/competitions/${publicId}`),
  createCompetition: (input: CompetitionInput) =>
    api.post<Competition>('/admin/catalog/competitions', input),
  updateCompetition: (publicId: string, input: Partial<CompetitionInput>) =>
    api.patch<Competition>(`/admin/catalog/competitions/${publicId}`, input),
  deleteCompetition: (publicId: string) =>
    api.delete<MessageResponse>(`/admin/catalog/competitions/${publicId}`),

  createPosition: (competitionPublicId: string, input: PositionInput) =>
    api.post<Position>(`/admin/catalog/competitions/${competitionPublicId}/positions`, input),
  deletePosition: (publicId: string) =>
    api.delete<MessageResponse>(`/admin/catalog/positions/${publicId}`),
  setPositionSubject: (
    positionPublicId: string,
    input: {
      subject_public_id: string
      weight: string
      questions_count?: number | null
      is_eliminatory?: boolean
    },
  ) => api.put<Position>(`/admin/catalog/positions/${positionPublicId}/subjects`, input),
  removePositionSubject: (positionPublicId: string, subjectPublicId: string) =>
    api.delete<Position>(
      `/admin/catalog/positions/${positionPublicId}/subjects/${subjectPublicId}`,
    ),

  subjects: (params: ListParams) =>
    api.get<Page<Subject>>(`/admin/catalog/subjects${query({ ...params })}`),
  createSubject: (input: { name: string; area?: string | null; color_token: string }) =>
    api.post<Subject>('/admin/catalog/subjects', input),
  updateSubject: (
    publicId: string,
    input: { name?: string; area?: string | null; color_token?: string; is_active?: boolean },
  ) => api.patch<Subject>(`/admin/catalog/subjects/${publicId}`, input),

  topics: (subjectPublicId: string) =>
    api.get<Topic[]>(`/admin/catalog/subjects/${subjectPublicId}/topics`),
  createTopic: (
    subjectPublicId: string,
    input: { name: string; parent_public_id?: string | null; sort_order?: number },
  ) => api.post<Topic>(`/admin/catalog/subjects/${subjectPublicId}/topics`, input),
  deleteTopic: (publicId: string) =>
    api.delete<MessageResponse>(`/admin/catalog/topics/${publicId}`),
  importTopics: (subjectPublicId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<TopicImportResult>(
      `/admin/catalog/subjects/${subjectPublicId}/topics/import`,
      form,
    )
  },
}
