import { api } from './client'
import type {
  RebalanceResult,
  StudyCalendar,
  StudyPlan,
  StudySession,
  StudyTask,
  SubjectProgress,
  TodayMission,
} from './types'

export interface PlanInput {
  minutes_by_weekday: Record<number, number>
  notice_public_id?: string | null
  position_public_id?: string | null
  exam_date?: string | null
  name?: string | null
}

export const studyApi = {
  createPlan: (input: PlanInput) => api.post<StudyPlan>('/study/plan', input),

  plan: () => api.get<StudyPlan>('/study/plan'),

  updateAvailability: (minutesByWeekday: Record<number, number>) =>
    api.patch<StudyPlan>('/study/plan', { minutes_by_weekday: minutesByWeekday }),

  today: (day?: string) => api.get<TodayMission>(`/study/today${day ? `?day=${day}` : ''}`),

  calendar: (start: string, end: string) =>
    api.get<StudyCalendar>(`/study/calendar?start=${start}&end=${end}`),

  completeTask: (publicId: string, minutes?: number) =>
    api.post<StudyTask>(`/study/tasks/${publicId}/complete`, { minutes: minutes ?? null }),

  skipTask: (publicId: string) => api.post<StudyTask>(`/study/tasks/${publicId}/skip`),

  reopenTask: (publicId: string) => api.post<StudyTask>(`/study/tasks/${publicId}/reopen`),

  rebalance: () => api.post<RebalanceResult>('/study/rebalance'),

  sprint: (minutes: number, subjectKey?: string | null) =>
    api.post<StudyTask[]>('/study/sprint', { minutes, subject_key: subjectKey ?? null }),

  progress: () => api.get<SubjectProgress[]>('/study/progress'),

  currentSession: () => api.get<StudySession | null>('/study/sessions/current'),

  startSession: (taskPublicId?: string | null) =>
    api.post<StudySession>('/study/sessions', { task_public_id: taskPublicId ?? null }),

  pauseSession: (publicId: string) =>
    api.post<StudySession>(`/study/sessions/${publicId}/pause`),

  resumeSession: (publicId: string) =>
    api.post<StudySession>(`/study/sessions/${publicId}/resume`),

  finishSession: (publicId: string, notes?: string) =>
    api.post<StudySession>(`/study/sessions/${publicId}/finish`, { notes: notes ?? null }),

  weekMinutes: () => api.get<{ minutes: number }>('/study/sessions/week-minutes'),
}
