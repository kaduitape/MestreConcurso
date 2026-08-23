import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Table, TableWrapper, Td, Th, Tr } from '@/components/ui/table'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'

const SPHERES = [
  ['FEDERAL', 'Federal'],
  ['ESTADUAL', 'Estadual'],
  ['DISTRITAL', 'Distrital'],
  ['MUNICIPAL', 'Municipal'],
] as const

export function OrganizationsSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', short_name: '', sphere: 'FEDERAL', uf: '' })

  const params = { page, page_size: 20 }
  const query = useQuery({
    queryKey: queryKeys.adminOrganizations(params),
    queryFn: () => adminCatalogApi.organizations(params),
    placeholderData: keepPreviousData,
  })

  const create = useMutation({
    mutationFn: () =>
      adminCatalogApi.createOrganization({
        name: form.name,
        short_name: form.short_name,
        sphere: form.sphere,
        uf: form.uf ? form.uf.toUpperCase() : null,
      }),
    onSuccess: () => {
      toast.success('Órgão cadastrado.')
      setOpen(false)
      setForm({ name: '', short_name: '', sphere: 'FEDERAL', uf: '' })
      queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>
          <Plus /> Novo órgão
        </Button>
      </div>

      {query.isLoading && <SkeletonList rows={3} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data?.items.length === 0 && (
        <EmptyState
          icon={Building2}
          title="Nenhum órgão cadastrado"
          description="Os órgãos são os contratantes dos concursos (PF, PCDF, TRT…)."
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus /> Cadastrar órgão
            </Button>
          }
        />
      )}

      {query.data && query.data.items.length > 0 && (
        <>
          <TableWrapper>
            <Table>
              <thead>
                <tr>
                  <Th>Órgão</Th>
                  <Th>Esfera</Th>
                  <Th>UF</Th>
                  <Th>Identificador</Th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((organization) => (
                  <Tr key={organization.public_id}>
                    <Td>
                      <p className="font-medium">{organization.short_name}</p>
                      <p className="text-xs text-muted">{organization.name}</p>
                    </Td>
                    <Td>
                      <Badge variant="outline">
                        {SPHERES.find(([value]) => value === organization.sphere)?.[1] ??
                          organization.sphere}
                      </Badge>
                    </Td>
                    <Td className="text-sm text-muted">{organization.uf ?? '—'}</Td>
                    <Td className="font-mono text-xs text-muted">{organization.slug}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrapper>

          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              {query.data.total} órgão(s) · página {query.data.page} de {query.data.pages}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= query.data.pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Próxima
              </Button>
            </div>
          </div>
        </>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo órgão</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Sigla" htmlFor="org-short">
              <Input
                id="org-short"
                placeholder="PCDF"
                value={form.short_name}
                onChange={(event) => setForm({ ...form, short_name: event.target.value })}
              />
            </Field>
            <Field label="Nome completo" htmlFor="org-name">
              <Input
                id="org-name"
                placeholder="Polícia Civil do Distrito Federal"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Esfera" htmlFor="org-sphere" className="sm:col-span-2">
                <Select
                  id="org-sphere"
                  value={form.sphere}
                  onChange={(event) => setForm({ ...form, sphere: event.target.value })}
                >
                  {SPHERES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="UF" htmlFor="org-uf">
                <Input
                  id="org-uf"
                  maxLength={2}
                  placeholder="DF"
                  value={form.uf}
                  onChange={(event) => setForm({ ...form, uf: event.target.value })}
                />
              </Field>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              loading={create.isPending}
              disabled={form.name.trim().length < 2 || form.short_name.trim().length < 2}
              onClick={() => create.mutate()}
            >
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
