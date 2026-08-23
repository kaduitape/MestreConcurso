import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { PasswordStrength } from '@/components/auth/password-strength'
import { ApiError } from '@/lib/api/client'
import { authApi } from '@/lib/api/auth'
import { usersApi } from '@/lib/api/users'
import { useAuth } from '@/providers/auth-provider'

const schema = z
  .object({
    current_password: z.string().min(1, 'Informe a senha atual.'),
    new_password: z
      .string()
      .min(10, 'A senha precisa de pelo menos 10 caracteres.')
      .regex(/[A-Z]/, 'Inclua ao menos uma letra maiúscula.')
      .regex(/[a-z]/, 'Inclua ao menos uma letra minúscula.')
      .regex(/\d/, 'Inclua ao menos um número.')
      .regex(/[^A-Za-z0-9]/, 'Inclua ao menos um símbolo.'),
    confirm: z.string(),
  })
  .refine((data) => data.new_password === data.confirm, {
    path: ['confirm'],
    message: 'As senhas não conferem.',
  })

type FormValues = z.infer<typeof schema>

export function SecuritySection() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const change = useMutation({
    mutationFn: (values: FormValues) =>
      usersApi.changePassword(values.current_password, values.new_password),
    onSuccess: (response) => {
      toast.success(response.message)
      reset()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível alterar a senha.'),
  })

  const logoutEverywhere = useMutation({
    mutationFn: async () => {
      await authApi.logoutAll()
      await logout()
    },
    onSuccess: () => navigate('/entrar', { replace: true }),
    onError: () => toast.error('Não foi possível encerrar as sessões agora.'),
  })

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Alterar senha</CardTitle>
          <CardDescription>
            Ao trocar a senha, as sessões nos outros dispositivos são encerradas.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit((values) => change.mutate(values))}
            className="space-y-4"
            noValidate
          >
            <Field
              label="Senha atual"
              htmlFor="current_password"
              error={errors.current_password?.message}
            >
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                invalid={Boolean(errors.current_password)}
                {...register('current_password')}
              />
            </Field>

            <Field label="Nova senha" htmlFor="new_password" error={errors.new_password?.message}>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                invalid={Boolean(errors.new_password)}
                {...register('new_password')}
              />
            </Field>
            <PasswordStrength value={watch('new_password') ?? ''} />

            <Field label="Confirmar nova senha" htmlFor="confirm" error={errors.confirm?.message}>
              <Input
                id="confirm"
                type="password"
                autoComplete="new-password"
                invalid={Boolean(errors.confirm)}
                {...register('confirm')}
              />
            </Field>

            <div className="flex justify-end">
              <Button type="submit" loading={change.isPending}>
                Alterar senha
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sessões</CardTitle>
          <CardDescription>
            Encerre o acesso em todos os aparelhos, inclusive neste, caso suspeite de uso
            indevido.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert tone="info">
            O acesso usa tokens curtos com renovação rotativa: se um token de renovação for
            reapresentado depois de usado, toda a cadeia daquela sessão é revogada
            automaticamente.
          </Alert>
          <Button
            variant="outline"
            onClick={() => logoutEverywhere.mutate()}
            loading={logoutEverywhere.isPending}
          >
            Sair de todos os dispositivos
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
