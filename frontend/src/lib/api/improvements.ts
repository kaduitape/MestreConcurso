import { api } from './client'
import type {
  ImprovementDetector,
  ImprovementFinding,
  ImprovementRun,
} from './types'

/** Nenhuma destas rotas aplica nada: o analista propõe, uma pessoa decide. */
export const improvementsApi = {
  detectors: () => api.get<ImprovementDetector[]>('/admin/improvements/detectors'),

  setDetector: (key: string, input: { is_enabled?: boolean; config?: Record<string, number> }) =>
    api.patch<ImprovementDetector>(`/admin/improvements/detectors/${key}`, input),

  findings: (params: { status?: string; detector?: string } = {}) => {
    const busca = new URLSearchParams()
    if (params.status) busca.set('status', params.status)
    if (params.detector) busca.set('detector', params.detector)
    const consulta = busca.toString()
    return api.get<ImprovementFinding[]>(
      `/admin/improvements/findings${consulta ? `?${consulta}` : ''}`,
    )
  },

  run: () => api.post<ImprovementRun>('/admin/improvements/run'),

  decide: (publicId: string, input: { status: string; reason?: string }) =>
    api.patch<ImprovementFinding>(`/admin/improvements/findings/${publicId}`, input),
}
