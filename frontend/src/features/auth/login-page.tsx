import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { ApiError } from '@/lib/api/client'
import { authApi } from '@/lib/api/auth'
import { useAuth } from '@/providers/auth-provider'

const schema = z.object({
  email: z.email('Informe um e-mail válido.'),
  password: z.string().min(1, 'Informe sua senha.'),
})

type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [formError, setFormError] = useState<ApiError | null>(null)
  const [resending, setResending] = useState(false)

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const destination = (location.state as { from?: string } | null)?.from ?? '/hoje'

  const onSubmit = async (values: FormValues) => {
    setFormError(null)
    try {
      await login(values.email, values.password)
      navigate(destination, { replace: true })
    } catch (error) {
      if (error instanceof ApiError) setFormError(error)
      else throw error
    }
  }

  const resendVerification = async () => {
    setResending(true)
    try {
      const { message } = await authApi.resendVerification(getValues('email'))
      toast.success(message)
    } finally {
      setResending(false)
    }
  }

  return (
    <AuthLayout
      title="Entrar"
      subtitle="Continue sua preparação de onde parou."
      footer={
        <>
          Ainda não tem conta?{' '}
          <Link to="/criar-conta" className="font-medium text-primary hover:underline">
            Criar conta
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError && (
          <Alert tone={formError.code === 'email_not_verified' ? 'warning' : 'danger'}>
            <p>{formError.message}</p>
            {formError.code === 'email_not_verified' && (
              <Button
                type="button"
                variant="link"
                size="sm"
                className="h-auto p-0"
                loading={resending}
                onClick={resendVerification}
              >
                Reenviar e-mail de confirmação
              </Button>
            )}
          </Alert>
        )}

        <Field label="E-mail" htmlFor="email" error={errors.email?.message}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="voce@exemplo.com.br"
            invalid={Boolean(errors.email)}
            {...register('email')}
          />
        </Field>

        <Field label="Senha" htmlFor="password" error={errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••••"
            invalid={Boolean(errors.password)}
            {...register('password')}
          />
        </Field>

        <div className="flex justify-end">
          <Link to="/esqueci-senha" className="text-sm text-muted hover:text-foreground">
            Esqueci minha senha
          </Link>
        </div>

        <Button type="submit" block size="lg" loading={isSubmitting}>
          Entrar
        </Button>
      </form>
    </AuthLayout>
  )
}
