import { apiGet, apiPost } from '@/api/client'
import type { CurrentUser } from '../types/auth'

export interface LoginInput {
  email: string
  password: string
}

export const authApi = {
  login: (data: LoginInput) => apiPost<CurrentUser>('/api/v1/auth/login', data),
  logout: () => apiPost<void>('/api/v1/auth/logout'),
  me: () => apiGet<CurrentUser>('/api/v1/auth/me'),
}
