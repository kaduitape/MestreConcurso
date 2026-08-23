import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { authApi } from '@/lib/api/auth'

const schema = z.object({ email: z.email('Informe um e-mail válido.') })
type FormValues = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const [sent, setSent] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    const response = await authApi.forgotPassword(values.email)
    setSent(response.message)
  }

  return (
    <AuthLayout
      title="Recuperar acesso"
      subtitle="Enviaremos um link para você definir uma nova senha."
      footer={
        <Link to="/entrar" className="font-medium text-primary hover:underline">
          Voltar para o login
        </Link>
      }
    >
      {sent ? (
        <Alert tone="success" title="Verifique seu e-mail">
          {sent} O link expira em 60 minutos e só pode ser usado uma vez.
        </Alert>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Field label="E-mail da conta" htmlFor="email" error={errors.email?.message}>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="voce@exemplo.com.br"
              invalid={Boolean(errors.email)}
              {...register('email')}
            />
          </Field>
          <Button type="submit" block size="lg" loading={isSubmitting}>
            Enviar link de recuperação
          </Button>
        </form>
      )}
    </AuthLayout>
  )
}
