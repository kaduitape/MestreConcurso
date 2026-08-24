import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './api/client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Erros de autenticação/permissão não melhoram com nova tentativa.
        if (error instanceof ApiError && error.status < 500) return false
        return failureCount < 2
      },
    },
    mutations: { retry: false },
  },
})

export const queryKeys = {
  me: ['me'] as const,
  sessions: ['sessions'] as const,
  adminOverview: ['admin', 'overview'] as const,
  adminUsers: (params: unknown) => ['admin', 'users', params] as const,
  adminRoles: ['admin', 'roles'] as const,
  adminAudit: (params: unknown) => ['admin', 'audit', params] as const,
  aiProviders: ['admin', 'ai', 'providers'] as const,
  aiAvailable: ['admin', 'ai', 'available'] as const,
  aiFeatures: ['admin', 'ai', 'features'] as const,
  aiCache: ['admin', 'ai', 'cache'] as const,
  adminBoards: (params: unknown) => ['admin', 'catalog', 'boards', params] as const,
  adminOrganizations: (params: unknown) =>
    ['admin', 'catalog', 'organizations', params] as const,
  adminCompetitions: (params: unknown) => ['admin', 'catalog', 'competitions', params] as const,
  adminCompetition: (publicId: string) =>
    ['admin', 'catalog', 'competition', publicId] as const,
  adminSubjects: (params: unknown) => ['admin', 'catalog', 'subjects', params] as const,
  adminTopics: (subjectId: string) => ['admin', 'catalog', 'topics', subjectId] as const,
  adminNotices: (params: unknown) => ['admin', 'notices', params] as const,
  boardKnowledge: (publicId: string) => ['catalog', 'board-knowledge', publicId] as const,
  competitions: (params: unknown) => ['catalog', 'competitions', params] as const,
  competition: (publicId: string) => ['catalog', 'competition', publicId] as const,
  competitionNotices: (publicId: string) =>
    ['catalog', 'competition-notices', publicId] as const,
  studyPlan: ['study', 'plan'] as const,
  studyToday: (day?: string) => ['study', 'today', day ?? 'hoje'] as const,
  studyCalendar: (start: string, end: string) => ['study', 'calendar', start, end] as const,
  studyProgress: ['study', 'progress'] as const,
  studySession: ['study', 'session'] as const,
  studyWeekMinutes: ['study', 'week-minutes'] as const,
  questions: (params: unknown) => ['questions', params] as const,
  questionHistory: (params: unknown) => ['questions', 'history', params] as const,
  adminQuestions: (params: unknown) => ['admin', 'questions', params] as const,
  simulationHistory: ['simulations', 'history'] as const,
  simulationCurrent: ['simulations', 'current'] as const,
  simulationAttempt: (publicId: string) => ['simulations', 'attempt', publicId] as const,
  incidence: (boardSlug: string) => ['intelligence', 'incidence', boardSlug] as const,
  boardDna: (boardSlug: string) => ['intelligence', 'board-dna', boardSlug] as const,
  priority: ['intelligence', 'priority'] as const,
  errorNotebook: ['errors', 'notebook'] as const,
  errorPending: ['errors', 'pending'] as const,
  errorTraps: ['errors', 'traps'] as const,
  errorList: (params: unknown) => ['errors', 'list', params] as const,
  conversations: ['tutor', 'conversations'] as const,
  conversation: (publicId: string) => ['tutor', 'conversation', publicId] as const,
  vocabulary: (params: unknown) => ['vocabulary', params] as const,
  adminVideos: (params: unknown) => ['admin', 'videos', params] as const,
}
