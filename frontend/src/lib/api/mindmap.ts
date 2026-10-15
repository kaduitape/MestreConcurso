import { api } from './client'
import type { MindMap, MindMapContent, MindMapInput, MindMapPanelSpec, Page } from './types'

export const mindmapApi = {
  published: (params: { page: number; page_size: number }) =>
    api.get<Page<MindMap>>(`/mindmaps?page=${params.page}&page_size=${params.page_size}`),
  map: (publicId: string) => api.get<MindMap>(`/mindmaps/${publicId}`),

  panels: () => api.get<MindMapPanelSpec[]>('/admin/mindmaps/panels'),
  adminList: (params: { page: number; page_size: number }) =>
    api.get<Page<MindMap>>(`/admin/mindmaps?page=${params.page}&page_size=${params.page_size}`),
  adminMap: (publicId: string) => api.get<MindMap>(`/admin/mindmaps/${publicId}`),
  create: (input: MindMapInput) => api.post<MindMap>('/admin/mindmaps', input),
  generate: (publicId: string) => api.post<MindMap>(`/admin/mindmaps/${publicId}/generate`),
  saveContent: (publicId: string, input: { title: string; content: MindMapContent }) =>
    api.put<MindMap>(`/admin/mindmaps/${publicId}/content`, input),
  publish: (publicId: string) => api.post<MindMap>(`/admin/mindmaps/${publicId}/publish`),
}
