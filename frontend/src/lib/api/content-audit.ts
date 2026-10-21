import { api } from './client'
import type { AuditRule, AuditRuleInput, ContentAudit, Page } from './types'

export const contentAuditApi = {
  rules: () => api.get<AuditRule[]>('/admin/content-audit/rules'),
  saveRule: (key: string, input: AuditRuleInput) =>
    api.put<AuditRule>(`/admin/content-audit/rules/${key}`, input),
  audits: (params: { page: number; page_size: number; target_kind?: string }) => {
    const query = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.target_kind) query.set('target_kind', params.target_kind)
    return api.get<Page<ContentAudit>>(`/admin/content-audit?${query.toString()}`)
  },
  run: (target_kind: string, target_public_id: string) =>
    api.post<ContentAudit>('/admin/content-audit/run', { target_kind, target_public_id }),
}
