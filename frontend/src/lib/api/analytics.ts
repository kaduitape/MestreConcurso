import { api } from './client'
import type {
  AnalyticsChart,
  AnalyticsOverview,
  ExamProjection,
  MasterScore,
  ScoreHistory,
  StudyPath,
} from './types'

export const analyticsApi = {
  masterScore: () => api.get<MasterScore>('/analytics/master-score'),

  masterScoreHistory: (days = 90) =>
    api.get<ScoreHistory>(`/analytics/master-score/history?days=${days}`),

  projection: () => api.get<ExamProjection>('/analytics/projection'),

  path: () => api.get<StudyPath>('/analytics/path'),

  dashboard: () => api.get<{ charts: AnalyticsChart[] }>('/analytics/dashboard'),

  overview: () => api.get<AnalyticsOverview>('/analytics/overview'),
}
