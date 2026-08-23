import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { adminApi } from '@/lib/api/admin'
import { queryKeys } from '@/lib/query-client'
import { ApiError } from '@/lib/api/client'
import type { User } from '@/lib/api/types'

export function UserEditDialog({ user, onClose }: { user: User | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState('')
  const [roles, setRoles] = useState<string[]>([])

  const rolesQuery = useQuery({
    queryKey: queryKeys.adminRoles,
    queryFn: adminApi.roles,
    enabled: Boolean(user),
  })

  useEffect(() => {
    if (user) {
      setStatus(user.status)
      setRoles(user.roles.map((role) => role.slug))
    }
  }, [user])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['admin'] })
  }

  const save = useMutation({
    mutationFn: async () => {
      if (!user) return
      if (status !== user.status) {
        await adminApi.updateUser(user.public_id, { status })
      }
      const current = user.roles.map((role) => role.slug).sort()
      if (JSON.stringify(current) !== JSON.stringify([...roles].sort())) {
        await adminApi.assignRoles(user.public_id, roles)
      }
    },
    onSuccess: () => {
      toast.success('Usuário atualizado.')
      invalidate()
      onClose()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  return (
    <Dialog open={Boolean(user)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Gerenciar acesso</DialogTitle>
          <DialogDescription>
            {user?.full_name} · {user?.email}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Field label="Status da conta" htmlFor="status">
            <select
              id="status"
              className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="ACTIVE">Ativo</option>
              <option value="PENDING">Aguardando confirmação</option>
              <option value="SUSPENDED">Suspenso</option>
            </select>
          </Field>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Papéis</legend>
            {rolesQuery.data?.map((role) => (
              <label key={role.slug} className="flex items-start gap-2.5 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-[var(--primary)]"
                  checked={roles.includes(role.slug)}
                  onChange={(event) =>
                    setRoles((current) =>
                      event.target.checked
                        ? [...current, role.slug]
                        : current.filter((item) => item !== role.slug),
                    )
                  }
                />
                <span>
                  <span className="font-medium">{role.name}</span>
                  <span className="block text-xs text-muted">{role.description}</span>
                </span>
              </label>
            ))}
          </fieldset>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button loading={save.isPending} onClick={() => save.mutate()}>
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
