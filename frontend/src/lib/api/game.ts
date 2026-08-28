import { api } from './client'
import type {
  AchievementList,
  ClaimResult,
  DailyBoard,
  GameProfile,
  GameRule,
  Page,
  StreakInfo,
  XPTransaction,
} from './types'

export const gameApi = {
  profile: () => api.get<GameProfile>('/game/profile'),

  missionsToday: () => api.get<DailyBoard>('/game/missions/today'),

  claim: (publicId: string) => api.post<ClaimResult>(`/game/missions/${publicId}/claim`),

  achievements: () => api.get<AchievementList>('/game/achievements'),

  streak: () => api.get<StreakInfo>('/game/streak'),

  xpHistory: (params: { page: number; page_size: number }) =>
    api.get<Page<XPTransaction>>(
      `/game/xp/history?page=${params.page}&page_size=${params.page_size}`,
    ),
}

export const gameRulesApi = {
  list: () => api.get<GameRule[]>('/admin/game/rules'),

  update: (
    key: string,
    input: { xp_value?: number; daily_cap?: number; is_enabled?: boolean },
  ) => api.put<GameRule>(`/admin/game/rules/${key}`, input),
}
