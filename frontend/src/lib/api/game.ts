import { api } from './client'
import type {
  AchievementList,
  Battle,
  BattleAnswerResult,
  BattleArmory,
  BattleAssetSlot,
  BattleCampaign,
  BattlePowerKey,
  BattleRanking,
  BattleSetting,
  BattleViewport,
  BoardBattle,
  ChallengeMode,
  Duel,
  DuelHistoryEntry,
  ClaimResult,
  DailyBoard,
  GameProfile,
  GameRule,
  GameRun,
  Journey,
  League,
  PublishedCard,
  LeaguePreferences,
  Page,
  RankHistory,
  RunAnswerResult,
  RunHistoryEntry,
  Season,
  SeasonHistoryEntry,
  ShareCard,
  SpecialEvent,
  StreakInfo,
  TerritoryMap,
  WarCampaign,
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

  startBattle: (
    viewport: BattleViewport,
    options: { boss?: boolean; subject?: string } = {},
  ) => {
    const params = new URLSearchParams({ viewport })
    if (options.boss) params.set('boss', 'true')
    if (options.subject) params.set('subject', options.subject)
    return api.post<Battle>(`/game/battle?${params.toString()}`)
  },

  battleArmory: () => api.get<BattleArmory>('/game/battle/armory'),

  saveBattleLoadout: (input: {
    class_slug: string
    weapon_slug: string
    armor_slug: string
    trinket_slug: string
  }) => api.put<BattleArmory>('/game/battle/armory', input),

  battleCampaign: () => api.get<BattleCampaign>('/game/battle/campaign'),

  battleRanking: () => api.get<BattleRanking>('/game/battle/ranking'),

  currentBattle: (viewport: BattleViewport) =>
    api.get<Battle | null>(`/game/battle/current?viewport=${viewport}`),

  battle: (publicId: string, viewport: BattleViewport) =>
    api.get<Battle>(`/game/battle/${publicId}?viewport=${viewport}`),

  answerBattle: (
    publicId: string,
    viewport: BattleViewport,
    input: { question_public_id: string; letter: string | null; time_seconds: number },
  ) =>
    api.post<BattleAnswerResult>(`/game/battle/${publicId}/answer?viewport=${viewport}`, input),

  useBattlePower: (publicId: string, viewport: BattleViewport, power: BattlePowerKey) =>
    api.post<Battle>(`/game/battle/${publicId}/power?viewport=${viewport}`, { power }),

  createDuel: () => api.post<Duel>('/game/duels'),

  acceptDuel: (code: string) => api.post<Duel>('/game/duels/accept', { code }),

  duel: (publicId: string) => api.get<Duel>(`/game/duels/${publicId}`),

  duels: () => api.get<DuelHistoryEntry[]>('/game/duels'),

  events: () => api.get<SpecialEvent[]>('/game/events'),

  warMode: () => api.get<WarCampaign>('/game/war'),

  startWarMode: (input: { days: number; daily_minutes: number; daily_questions: number }) =>
    api.post<WarCampaign>('/game/war', input),

  abandonWarMode: () => api.post<WarCampaign>('/game/war/abandon'),

  warHistory: () => api.get<WarCampaign[]>('/game/war/history'),

  previewCard: (input: { include: string[]; display_name?: string }) =>
    api.post<ShareCard>('/game/cards/preview', input),

  publishCard: (input: { include: string[]; display_name?: string }) =>
    api.post<PublishedCard>('/game/cards', input),

  cards: () => api.get<PublishedCard[]>('/game/cards'),

  revokeCard: (publicId: string) => api.delete<PublishedCard>(`/game/cards/${publicId}`),
}

export const battleSettingsApi = {
  list: () => api.get<BattleSetting[]>('/admin/game/battle-settings'),

  update: (key: string, value: number) =>
    api.put<BattleSetting>(`/admin/game/battle-settings/${key}`, { value }),
}

export const battleArtApi = {
  list: () => api.get<BattleAssetSlot[]>('/admin/game/battle-art'),

  upload: (kind: string, slug: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return api.put<BattleAssetSlot>(`/admin/game/battle-art/${kind}/${slug}`, body)
  },

  remove: (publicId: string) =>
    api.delete<BattleAssetSlot>(`/admin/game/battle-art/${publicId}`),
}

export const gameRulesApi = {
  list: () => api.get<GameRule[]>('/admin/game/rules'),

  update: (
    key: string,
    input: { xp_value?: number; daily_cap?: number; is_enabled?: boolean },
  ) => api.put<GameRule>(`/admin/game/rules/${key}`, input),
}
