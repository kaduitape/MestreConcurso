import { createBrowserRouter, Navigate } from 'react-router-dom'
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
import { AdminPage } from '@/features/admin/admin-page'
import { NotFoundPage } from '@/features/not-found-page'

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
          { path: '/conta', element: <AccountPage /> },
          {
            element: <RequirePermission permission="admin_dashboard:read" />,
            children: [{ path: '/admin', element: <AdminPage /> }],
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
