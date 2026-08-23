import { API_BASE, api, tokenStorage } from './client'
import type { CurrentUser, MessageResponse, Profile, SessionInfo } from './types'

export interface AccountUpdateInput {
  full_name?: string
  profile?: Partial<Pick<Profile, 'city' | 'state' | 'phone' | 'bio' | 'study_goal' | 'theme'>>
}

export const usersApi = {
  me: () => api.get<CurrentUser>('/users/me'),

  update: (input: AccountUpdateInput) => api.patch<CurrentUser>('/users/me', input),

  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<MessageResponse>('/users/me/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),

  sessions: () => api.get<SessionInfo[]>('/users/me/sessions'),

  revokeSession: (publicId: string) =>
    api.delete<MessageResponse>(`/users/me/sessions/${publicId}`),

  deleteAccount: (password: string) =>
    api.delete<MessageResponse>('/users/me', { password, confirmation: 'EXCLUIR' }),

  /** Baixa o JSON de exportação LGPD usando o token atual. */
  exportData: async (): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/users/me/export`, {
      headers: { Authorization: `Bearer ${tokenStorage.access ?? ''}` },
    })
    if (!response.ok) throw new Error('Não foi possível exportar seus dados agora.')
    return response.blob()
  },
}
