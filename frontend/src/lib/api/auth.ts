import { api, tokenStorage } from './client'
import type { CurrentUser, MessageResponse, TokenPair } from './types'

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  accepted_terms: boolean
}

export const authApi = {
  register: (input: RegisterInput) =>
    api.post<MessageResponse>('/auth/register', input, { skipAuth: true }),

  login: async (email: string, password: string, deviceLabel?: string) => {
    const tokens = await api.post<TokenPair>(
      '/auth/login',
      { email, password, device_label: deviceLabel },
      { skipAuth: true },
    )
    tokenStorage.save(tokens)
    return tokens
  },

  verifyEmail: (token: string) =>
    api.post<MessageResponse>('/auth/verify-email', { token }, { skipAuth: true }),

  resendVerification: (email: string) =>
    api.post<MessageResponse>('/auth/resend-verification', { email }, { skipAuth: true }),

  forgotPassword: (email: string) =>
    api.post<MessageResponse>('/auth/forgot-password', { email }, { skipAuth: true }),

  resetPassword: (token: string, newPassword: string) =>
    api.post<MessageResponse>(
      '/auth/reset-password',
      { token, new_password: newPassword },
      { skipAuth: true },
    ),

  me: () => api.get<CurrentUser>('/auth/me'),

  logout: async () => {
    try {
      await api.post<MessageResponse>('/auth/logout')
    } finally {
      tokenStorage.clear()
    }
  },

  logoutAll: async () => {
    try {
      return await api.post<MessageResponse>('/auth/logout-all')
    } finally {
      tokenStorage.clear()
    }
  },
}
