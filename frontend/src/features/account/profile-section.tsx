import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ApiError } from '@/lib/api/client'
import { usersApi } from '@/lib/api/users'
import { queryKeys } from '@/lib/query-client'
import { useAuth } from '@/providers/auth-provider'

const schema = z.object({
  full_name: z.string().trim().min(3, 'Informe seu nome completo.').max(160),
  city: z.string().max(120).optional(),
  state: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{2}$/, 'Use a sigla do estado (ex.: DF).')
    .optional()
    .or(z.literal('')),
  phone: z.string().max(32).optional(),
  study_goal: z.string().max(255).optional(),
  bio: z.string().max(500).optional(),
})

type FormValues = z.infer<typeof schema>

export function ProfileSection() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: {
      full_name: user?.full_name ?? '',
      city: user?.profile?.city ?? '',
      state: user?.profile?.state ?? '',
      phone: user?.profile?.phone ?? '',
      study_goal: user?.profile?.study_goal ?? '',
      bio: user?.profile?.bio ?? '',
    },
  })

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      usersApi.update({
        full_name: values.full_name,
        profile: {
          city: values.city || null,
          state: values.state ? values.state.toUpperCase() : null,
          phone: values.phone || null,
          study_goal: values.study_goal || null,
          bio: values.bio || null,
        } as never,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.me, updated)
      toast.success('Perfil atualizado.')
    },
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.')
    },
  })

  if (!user) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dados pessoais</CardTitle>
        <CardDescription>
          Usamos essas informações para personalizar a comunicação e o seu plano de estudo.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="space-y-4"
          noValidate
        >
          <div className="flex flex-wrap items-center gap-2 rounded-md bg-surface-muted p-3 text-sm">
            <span className="text-muted">{user.email}</span>
            <Badge variant={user.email_verified_at ? 'success' : 'warning'}>
              {user.email_verified_at ? 'E-mail confirmado' : 'E-mail não confirmado'}
            </Badge>
          </div>

          <Field label="Nome completo" htmlFor="full_name" error={errors.full_name?.message}>
            <Input id="full_name" invalid={Boolean(errors.full_name)} {...register('full_name')} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Cidade" htmlFor="city" error={errors.city?.message} className="sm:col-span-2">
              <Input id="city" placeholder="Brasília" {...register('city')} />
            </Field>
            <Field label="UF" htmlFor="state" error={errors.state?.message}>
              <Input id="state" maxLength={2} placeholder="DF" {...register('state')} />
            </Field>
          </div>

          <Field label="Telefone" htmlFor="phone" error={errors.phone?.message} hint="Opcional">
            <Input id="phone" placeholder="(61) 90000-0000" {...register('phone')} />
          </Field>

          <Field
            label="Objetivo"
            htmlFor="study_goal"
            error={errors.study_goal?.message}
            hint="Ex.: Agente de Polícia Federal — prova em 2026"
          >
            <Input id="study_goal" {...register('study_goal')} />
          </Field>

          <Field label="Sobre você" htmlFor="bio" error={errors.bio?.message} hint="Opcional">
            <Textarea id="bio" rows={3} {...register('bio')} />
          </Field>

          <div className="flex justify-end">
            <Button type="submit" loading={mutation.isPending} disabled={!isDirty}>
              Salvar alterações
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
