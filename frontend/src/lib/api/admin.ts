import { api } from './client'
import type { AdminOverview, AuditLog, Page, Permission, Role, User } from './types'

export interface UserListParams {
  page: number
  page_size: number
  search?: string
  status?: string
  role?: string
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  const asString = search.toString()
  return asString ? `?${asString}` : ''
}

export const adminApi = {
  overview: () => api.get<AdminOverview>('/admin/overview'),

  users: (params: UserListParams) => api.get<Page<User>>(`/admin/users${query({ ...params })}`),

  user: (publicId: string) => api.get<User>(`/admin/users/${publicId}`),

  updateUser: (publicId: string, input: { status?: string; full_name?: string }) =>
    api.patch<User>(`/admin/users/${publicId}`, input),

  assignRoles: (publicId: string, roles: string[]) =>
    api.put<User>(`/admin/users/${publicId}/roles`, { roles }),

  roles: () => api.get<Role[]>('/admin/roles'),

  permissions: () => api.get<Permission[]>('/admin/permissions'),

  auditLogs: (params: { page: number; page_size: number; action?: string; since_days?: number }) =>
    api.get<Page<AuditLog>>(`/admin/audit-logs${query({ ...params })}`),
}
