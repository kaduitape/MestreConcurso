import { api } from './client'
import type { AgentCatalog, AgentPreflight, AgentRun, Page } from './types'

export const agentsApi = {
  catalog: () => api.get<AgentCatalog>('/admin/agents/catalog'),
  runs: (params: { page: number; page_size: number }) =>
    api.get<Page<AgentRun>>(`/admin/agents?page=${params.page}&page_size=${params.page_size}`),
  run: (publicId: string) => api.get<AgentRun>(`/admin/agents/${publicId}`),
  create: (competition_public_id: string) =>
    api.post<AgentRun>('/admin/agents', { competition_public_id }),
  execute: (publicId: string) => api.post<AgentRun>(`/admin/agents/${publicId}/run`),
  executeOne: (publicId: string, agentKey: string) =>
    api.post<AgentRun>(`/admin/agents/${publicId}/run/${agentKey}`),

  /** O que falta antes de disparar os oito agentes. Não chama IA. */
  preflight: (publicId: string) =>
    api.get<AgentPreflight>(`/admin/agents/${publicId}/preflight`),

  cancel: (publicId: string) => api.post<AgentRun>(`/admin/agents/${publicId}/cancel`),
}
