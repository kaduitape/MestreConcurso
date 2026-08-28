import { api } from './client'
import type {
  AchievementList,
  BoardBattle,
  ChallengeMode,
  ClaimResult,
  DailyBoard,
  GameProfile,
  GameRule,
  GameRun,
  Journey,
  League,
  LeaguePreferences,
  Page,
  RankHistory,
  RunAnswerResult,
  RunHistoryEntry,
  Season,
  SeasonHistoryEntry,
  StreakInfo,
  TerritoryMap,
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

  rankHistory: (days = 90) => api.get<RankHistory>(`/game/rank/history?days=${days}`),

  boardBattle: () => api.get<BoardBattle>('/game/board-battle'),

  journey: () => api.get<Journey>('/game/journey'),

  territory: () => api.get<TerritoryMap>('/game/territory'),

  season: () => api.get<Season>('/game/season'),

  seasonHistory: () => api.get<SeasonHistoryEntry[]>('/game/season/history'),

  league: () => api.get<League>('/game/league'),

  leaguePreferences: () => api.get<LeaguePreferences>('/game/league/preferences'),

  updateLeaguePreferences: (input: { opt_out?: boolean; display_name?: string }) =>
    api.put<LeaguePreferences>('/game/league/preferences', input),

  challengeModes: () => api.get<ChallengeMode[]>('/game/challenges/modes'),

  currentRun: () => api.get<GameRun | null>('/game/challenges/current'),

  startRun: (mode: string) => api.post<GameRun>(`/game/challenges/${mode}`),

  run: (publicId: string) => api.get<GameRun>(`/game/challenges/runs/${publicId}`),

  answerRun: (
    publicId: string,
    input: { question_public_id: string; letter: string | null; time_seconds: number },
  ) => api.post<RunAnswerResult>(`/game/challenges/runs/${publicId}/answer`, input),

  finishRun: (publicId: string, abandon = false) =>
    api.post<GameRun>(`/game/challenges/runs/${publicId}/finish?abandon=${abandon}`),

  runHistory: () => api.get<RunHistoryEntry[]>('/game/challenges/history'),
}

export const gameRulesApi = {
  list: () => api.get<GameRule[]>('/admin/game/rules'),

  update: (
    key: string,
    input: { xp_value?: number; daily_cap?: number; is_enabled?: boolean },
  ) => api.put<GameRule>(`/admin/game/rules/${key}`, input),
}
