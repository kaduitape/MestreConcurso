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
