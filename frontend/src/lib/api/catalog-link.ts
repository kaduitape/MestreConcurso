import { api } from './client'
import type {
  CatalogLinkInput,
  CatalogMatch,
  Competition,
  CompetitionEditorialStatus,
  LinkableKind,
  LinkedContent,
  Page,
  PendingLink,
  StudyFocus,
} from './types'

export const catalogLinkApi = {
  pending: (params: { page: number; page_size: number }) =>
    api.get<Page<PendingLink>>(
      `/admin/catalog/links/pending?page=${params.page}&page_size=${params.page_size}`,
    ),
  topics: (kind: LinkableKind, publicId: string, subjectPublicId: string) =>
    api.get<CatalogMatch>(
      `/admin/catalog/links/${kind}/${publicId}/topics?subject_public_id=${subjectPublicId}`,
    ),
  link: (kind: LinkableKind, publicId: string, input: CatalogLinkInput) =>
    api.put<LinkedContent>(`/admin/catalog/links/${kind}/${publicId}`, input),
  setEditorialStatus: (publicId: string, editorial_status: CompetitionEditorialStatus) =>
    api.put<Competition>(`/admin/catalog/competitions/${publicId}/editorial-status`, {
      editorial_status,
    }),
}

export const studyFocusApi = {
  get: () => api.get<StudyFocus>('/users/me/focus'),
  set: (competition_public_id: string | null) =>
    api.put<StudyFocus>('/users/me/focus', { competition_public_id }),
}
