import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Button } from '@/components/ui/button'
import { authApi } from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'

type State = { status: 'loading' | 'success' | 'error'; message: string }

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const requested = useRef(false)
  const [state, setState] = useState<State>({
    status: 'loading',
    message: 'Confirmando seu e-mail…',
  })

  useEffect(() => {
    if (!token) {
      setState({ status: 'error', message: 'Link de confirmação inválido.' })
      return
    }
    if (requested.current) return
    requested.current = true

    authApi
      .verifyEmail(token)
      .then((response) => setState({ status: 'success', message: response.message }))
      .catch((error: unknown) =>
        setState({
          status: 'error',
          message:
            error instanceof ApiError
              ? error.message
              : 'Não foi possível confirmar seu e-mail agora.',
        }),
      )
  }, [token])

  const icons = {
    loading: <Loader2 className="size-6 animate-spin text-primary" aria-hidden />,
    success: <CheckCircle2 className="size-6 text-success" aria-hidden />,
    error: <XCircle className="size-6 text-danger" aria-hidden />,
  }

  return (
    <AuthLayout title="Confirmação de e-mail" subtitle="Validação do seu link de acesso.">
      <div className="space-y-5">
        <div className="flex items-center gap-3 rounded-md border border-border bg-surface-muted p-4">
          {icons[state.status]}
          <p className="text-sm">{state.message}</p>
        </div>

        {state.status === 'success' && (
          <Button asChild block size="lg">
            <Link to="/entrar">Entrar agora</Link>
          </Button>
        )}
        {state.status === 'error' && (
          <Button asChild variant="outline" block>
            <Link to="/entrar">Voltar para o login</Link>
          </Button>
        )}
      </div>
    </AuthLayout>
  )
}
