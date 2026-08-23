import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { MailCheck } from 'lucide-react'
import { AuthLayout } from '@/components/auth/auth-layout'
import { PasswordStrength } from '@/components/auth/password-strength'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { ApiError } from '@/lib/api/client'
import { authApi } from '@/lib/api/auth'

const schema = z
  .object({
    full_name: z.string().trim().min(3, 'Informe seu nome completo.').max(160),
    email: z.email('Informe um e-mail válido.'),
    password: z
      .string()
      .min(10, 'A senha precisa de pelo menos 10 caracteres.')
      .regex(/[A-Z]/, 'Inclua ao menos uma letra maiúscula.')
      .regex(/[a-z]/, 'Inclua ao menos uma letra minúscula.')
      .regex(/\d/, 'Inclua ao menos um número.')
      .regex(/[^A-Za-z0-9]/, 'Inclua ao menos um símbolo.'),
    confirm: z.string(),
    accepted_terms: z.literal(true, 'É necessário aceitar os termos.'),
  })
  .refine((data) => data.password === data.confirm, {
    path: ['confirm'],
    message: 'As senhas não conferem.',
  })

type FormValues = z.infer<typeof schema>

export function RegisterPage() {
  const [done, setDone] = useState<string | null>(null)
  const [formError, setFormError] = useState<ApiError | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const password = watch('password') ?? ''

  const onSubmit = async (values: FormValues) => {
    setFormError(null)
    try {
      await authApi.register({
        email: values.email,
        password: values.password,
        full_name: values.full_name,
        accepted_terms: values.accepted_terms,
      })
      setDone(values.email)
    } catch (error) {
      if (error instanceof ApiError) setFormError(error)
      else throw error
    }
  }

  if (done) {
    return (
      <AuthLayout
        title="Confirme seu e-mail"
        subtitle="Falta um passo para liberar sua conta."
        footer={
          <Link to="/entrar" className="font-medium text-primary hover:underline">
            Voltar para o login
          </Link>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3 rounded-md bg-success-soft p-4 text-success">
            <MailCheck className="size-5 shrink-0" aria-hidden />
            <p className="text-sm">
              Enviamos um link de confirmação para <strong>{done}</strong>. O link vale por 48
              horas.
            </p>
          </div>
          <p className="text-sm text-muted">
            Não recebeu? Confira a caixa de spam ou{' '}
            <button
              type="button"
              className="font-medium text-primary hover:underline"
              onClick={() => authApi.resendVerification(done)}
            >
              reenviar o e-mail
            </button>
            .
          </p>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Criar conta"
      subtitle="Comece montando sua estratégia a partir do edital."
      footer={
        <>
          Já tem conta?{' '}
          <Link to="/entrar" className="font-medium text-primary hover:underline">
            Entrar
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError && (
          <Alert tone="danger">
            <p>{formError.message}</p>
            {formError.fieldMessages.length > 0 && (
              <ul className="mt-1 list-inside list-disc">
                {formError.fieldMessages.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </Alert>
        )}

        <Field label="Nome completo" htmlFor="full_name" error={errors.full_name?.message}>
          <Input
            id="full_name"
            autoComplete="name"
            placeholder="Como você quer ser chamado"
            invalid={Boolean(errors.full_name)}
            {...register('full_name')}
          />
        </Field>

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
            autoComplete="new-password"
            invalid={Boolean(errors.password)}
            {...register('password')}
          />
        </Field>
        <PasswordStrength value={password} />

        <Field label="Confirmar senha" htmlFor="confirm" error={errors.confirm?.message}>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            invalid={Boolean(errors.confirm)}
            {...register('confirm')}
          />
        </Field>

        <label className="flex items-start gap-2.5 text-sm text-muted">
          <input
            type="checkbox"
            className="mt-0.5 size-4 rounded border-border-strong accent-[var(--primary)]"
            {...register('accepted_terms')}
          />
          <span>
            Li e aceito os Termos de Uso e a Política de Privacidade, incluindo o tratamento dos
            meus dados conforme a LGPD.
          </span>
        </label>
        {errors.accepted_terms && (
          <p className="text-xs font-medium text-danger">{errors.accepted_terms.message}</p>
        )}

        <Button type="submit" block size="lg" loading={isSubmitting}>
          Criar minha conta
        </Button>
      </form>
    </AuthLayout>
  )
}
