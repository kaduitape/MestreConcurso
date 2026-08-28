import type { ReactNode } from 'react'
import { Suspense, lazy } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { AppShell } from '@/components/layout/app-shell'
import {
  ProtectedRoute,
  PublicOnlyRoute,
  RequirePermission,
} from '@/components/auth/protected-route'
import { LoginPage } from '@/features/auth/login-page'
import { RegisterPage } from '@/features/auth/register-page'
import { VerifyEmailPage } from '@/features/auth/verify-email-page'
import { ForgotPasswordPage } from '@/features/auth/forgot-password-page'
import { ResetPasswordPage } from '@/features/auth/reset-password-page'
import { TodayPage } from '@/features/today/today-page'
import { AccountPage } from '@/features/account/account-page'
import { NotFoundPage } from '@/features/not-found-page'

// Áreas pesadas entram sob demanda: o primeiro carregamento fica menor.
const AdminPage = lazy(() =>
  import('@/features/admin/admin-page').then((module) => ({ default: module.AdminPage })),
)
const NoticeDetailPage = lazy(() =>
  import('@/features/admin/notices/notice-detail-page').then((module) => ({
    default: module.NoticeDetailPage,
  })),
)
const PlanPage = lazy(() =>
  import('@/features/study/plan-page').then((module) => ({ default: module.PlanPage })),
)
const PlanSetupPage = lazy(() =>
  import('@/features/study/plan-setup-page').then((module) => ({
    default: module.PlanSetupPage,
  })),
)
const StudyCalendarPage = lazy(() =>
  import('@/features/study/calendar-page').then((module) => ({
    default: module.StudyCalendarPage,
  })),
)
const QuestionsPage = lazy(() =>
  import('@/features/questions/questions-page').then((module) => ({
    default: module.QuestionsPage,
  })),
)
const SimulationsPage = lazy(() =>
  import('@/features/simulations/simulations-page').then((module) => ({
    default: module.SimulationsPage,
  })),
)
const SimulationRunPage = lazy(() =>
  import('@/features/simulations/simulation-run-page').then((module) => ({
    default: module.SimulationRunPage,
  })),
)
const SimulationResultPage = lazy(() =>
  import('@/features/simulations/simulation-result-page').then((module) => ({
    default: module.SimulationResultPage,
  })),
)
const MissionsPage = lazy(() =>
  import('@/features/game/missions-page').then((module) => ({ default: module.MissionsPage })),
)
const GameProfilePage = lazy(() =>
  import('@/features/game/profile-page').then((module) => ({
    default: module.GameProfilePage,
  })),
)
const BoardBattlePage = lazy(() =>
  import('@/features/game/board-battle-page').then((module) => ({
    default: module.BoardBattlePage,
  })),
)
const JourneyPage = lazy(() =>
  import('@/features/game/journey-page').then((module) => ({ default: module.JourneyPage })),
)
const SeasonPage = lazy(() =>
  import('@/features/game/season-page').then((module) => ({ default: module.SeasonPage })),
)
const ChallengesPage = lazy(() =>
  import('@/features/game/challenges-page').then((module) => ({
    default: module.ChallengesPage,
  })),
)
const DeckPage = lazy(() =>
  import('@/features/flashcards/deck-page').then((module) => ({ default: module.DeckPage })),
)
const ReviewPage = lazy(() =>
  import('@/features/flashcards/review-page').then((module) => ({
    default: module.ReviewPage,
  })),
)
const TutorPage = lazy(() =>
  import('@/features/tutor/tutor-page').then((module) => ({ default: module.TutorPage })),
)
const VocabularyPage = lazy(() =>
  import('@/features/tutor/vocabulary-page').then((module) => ({
    default: module.VocabularyPage,
  })),
)
const BoardIntelPage = lazy(() =>
  import('@/features/intelligence/board-intel-page').then((module) => ({
    default: module.BoardIntelPage,
  })),
)
const ErrorsPage = lazy(() =>
  import('@/features/errors/errors-page').then((module) => ({ default: module.ErrorsPage })),
)
const CompetitionsPage = lazy(() =>
  import('@/features/competitions/competitions-page').then((module) => ({
    default: module.CompetitionsPage,
  })),
)
const CompetitionDetailPage = lazy(() =>
  import('@/features/competitions/competition-detail-page').then((module) => ({
    default: module.CompetitionDetailPage,
  })),
)

function lazyRoute(element: ReactNode): ReactNode {
  return (
    <Suspense
      fallback={
        <div className="flex items-center gap-3 p-8 text-muted">
          <Loader2 className="size-5 animate-spin" aria-hidden />
          <span className="text-sm">Carregando…</span>
        </div>
      }
    >
      {element}
    </Suspense>
  )
}

export const router = createBrowserRouter([
  {
    element: <PublicOnlyRoute />,
    children: [
      { path: '/entrar', element: <LoginPage /> },
      { path: '/criar-conta', element: <RegisterPage /> },
      { path: '/esqueci-senha', element: <ForgotPasswordPage /> },
    ],
  },
  { path: '/verificar-email', element: <VerifyEmailPage /> },
  { path: '/redefinir-senha', element: <ResetPasswordPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/', element: <Navigate to="/hoje" replace /> },
          { path: '/hoje', element: <TodayPage /> },
          { path: '/plano', element: lazyRoute(<PlanPage />) },
          { path: '/plano/novo', element: lazyRoute(<PlanSetupPage />) },
          { path: '/calendario', element: lazyRoute(<StudyCalendarPage />) },
          { path: '/questoes', element: lazyRoute(<QuestionsPage />) },
          { path: '/simulados', element: lazyRoute(<SimulationsPage />) },
          {
            path: '/simulados/resultado/:attemptId',
            element: lazyRoute(<SimulationResultPage />),
          },
          { path: '/simulados/:attemptId', element: lazyRoute(<SimulationRunPage />) },
          { path: '/inteligencia', element: lazyRoute(<BoardIntelPage />) },
          { path: '/meus-erros', element: lazyRoute(<ErrorsPage />) },
          { path: '/mestre-ia', element: lazyRoute(<TutorPage />) },
          { path: '/vocabulario', element: lazyRoute(<VocabularyPage />) },
          { path: '/flashcards', element: lazyRoute(<DeckPage />) },
          { path: '/revisao', element: lazyRoute(<ReviewPage />) },
          { path: '/missoes', element: lazyRoute(<MissionsPage />) },
          { path: '/progresso', element: lazyRoute(<GameProfilePage />) },
          { path: '/voce-vs-banca', element: lazyRoute(<BoardBattlePage />) },
          { path: '/jornada', element: lazyRoute(<JourneyPage />) },
          { path: '/temporada', element: lazyRoute(<SeasonPage />) },
          { path: '/desafios', element: lazyRoute(<ChallengesPage />) },
          { path: '/concursos', element: lazyRoute(<CompetitionsPage />) },
          { path: '/concursos/:publicId', element: lazyRoute(<CompetitionDetailPage />) },
          { path: '/conta', element: <AccountPage /> },
          {
            element: <RequirePermission permission="admin_dashboard:read" />,
            children: [
              { path: '/admin', element: lazyRoute(<AdminPage />) },
              {
                path: '/admin/editais/:publicId',
                element: lazyRoute(<NoticeDetailPage />),
              },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
