import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/auth/auth-layout'
import { PasswordStrength } from '@/components/auth/password-strength'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { authApi } from '@/lib/api/auth'
import { ApiError } from '@/lib/api/client'

const schema = z
  .object({
    password: z
      .string()
      .min(10, 'A senha precisa de pelo menos 10 caracteres.')
      .regex(/[A-Z]/, 'Inclua ao menos uma letra maiúscula.')
      .regex(/[a-z]/, 'Inclua ao menos uma letra minúscula.')
      .regex(/\d/, 'Inclua ao menos um número.')
      .regex(/[^A-Za-z0-9]/, 'Inclua ao menos um símbolo.'),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    path: ['confirm'],
    message: 'As senhas não conferem.',
  })

type FormValues = z.infer<typeof schema>

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token')
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    if (!token) return
    setFormError(null)
    try {
      const response = await authApi.resetPassword(token, values.password)
      toast.success(response.message)
      navigate('/entrar', { replace: true })
    } catch (error) {
      setFormError(
        error instanceof ApiError ? error.message : 'Não foi possível redefinir a senha.',
      )
    }
  }

  return (
    <AuthLayout
      title="Nova senha"
      subtitle="Defina uma senha forte para proteger sua preparação."
      footer={
        <Link to="/entrar" className="font-medium text-primary hover:underline">
          Voltar para o login
        </Link>
      }
    >
      {!token ? (
        <Alert tone="danger" title="Link inválido">
          Solicite uma nova recuperação de senha para receber um link válido.
        </Alert>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {formError && <Alert tone="danger">{formError}</Alert>}

          <Field label="Nova senha" htmlFor="password" error={errors.password?.message}>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              invalid={Boolean(errors.password)}
              {...register('password')}
            />
          </Field>
          <PasswordStrength value={watch('password') ?? ''} />

          <Field label="Confirmar senha" htmlFor="confirm" error={errors.confirm?.message}>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              invalid={Boolean(errors.confirm)}
              {...register('confirm')}
            />
          </Field>

          <Alert tone="info">
            Ao redefinir, todas as sessões abertas em outros dispositivos serão encerradas.
          </Alert>

          <Button type="submit" block size="lg" loading={isSubmitting}>
            Salvar nova senha
          </Button>
        </form>
      )}
    </AuthLayout>
  )
}
