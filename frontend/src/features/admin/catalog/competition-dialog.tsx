import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import { EDUCATION_LABEL, formatCurrency } from './helpers'

/** Cargos do concurso e as disciplinas cobradas em cada um, com peso e nº de questões. */
export function CompetitionDialog({
  publicId,
  onClose,
}: {
  publicId: string | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [positionName, setPositionName] = useState('')
  const [subjectByPosition, setSubjectByPosition] = useState<Record<string, string>>({})
  const [weightByPosition, setWeightByPosition] = useState<Record<string, string>>({})

  const competition = useQuery({
    queryKey: queryKeys.adminCompetition(publicId ?? ''),
    queryFn: () => adminCatalogApi.competition(publicId!),
    enabled: Boolean(publicId),
  })

  const subjects = useQuery({
    queryKey: queryKeys.adminSubjects({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.subjects({ page: 1, page_size: 100 }),
    enabled: Boolean(publicId),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
  }

  const addPosition = useMutation({
    mutationFn: () => adminCatalogApi.createPosition(publicId!, { name: positionName }),
    onSuccess: () => {
      setPositionName('')
      toast.success('Cargo adicionado.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível adicionar.'),
  })

  const removePosition = useMutation({
    mutationFn: (positionPublicId: string) => adminCatalogApi.deletePosition(positionPublicId),
    onSuccess: () => {
      toast.success('Cargo removido.')
      invalidate()
    },
  })

  const linkSubject = useMutation({
    mutationFn: (positionPublicId: string) =>
      adminCatalogApi.setPositionSubject(positionPublicId, {
        subject_public_id: subjectByPosition[positionPublicId]!,
        weight: weightByPosition[positionPublicId] || '1.00',
      }),
    onSuccess: () => {
      toast.success('Disciplina vinculada.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível vincular.'),
  })

  const unlinkSubject = useMutation({
    mutationFn: (input: { positionPublicId: string; subjectPublicId: string }) =>
      adminCatalogApi.removePositionSubject(input.positionPublicId, input.subjectPublicId),
    onSuccess: () => invalidate(),
  })

  return (
    <Dialog open={Boolean(publicId)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{competition.data?.name ?? 'Concurso'}</DialogTitle>
          <DialogDescription>
            {competition.data?.organization.short_name}
            {competition.data?.exam_board && ` · ${competition.data.exam_board.short_name}`}
            {competition.data?.salary_max_cents
              ? ` · até ${formatCurrency(competition.data.salary_max_cents)}`
              : ''}
          </DialogDescription>
        </DialogHeader>

        {competition.isLoading && <SkeletonList rows={2} />}

        <div className="max-h-[60vh] space-y-4 overflow-y-auto">
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              addPosition.mutate()
            }}
          >
            <Input
              placeholder="Nome do cargo (ex.: Agente de Polícia)"
              value={positionName}
              onChange={(event) => setPositionName(event.target.value)}
              aria-label="Nome do cargo"
            />
            <Button
              type="submit"
              loading={addPosition.isPending}
              disabled={positionName.trim().length < 2}
            >
              <Plus /> Cargo
            </Button>
          </form>

          {competition.data?.positions.length === 0 && (
            <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted">
              Nenhum cargo cadastrado ainda. O cargo é o que liga o candidato às disciplinas
              cobradas.
            </p>
          )}

          {competition.data?.positions.map((position) => (
            <div key={position.public_id} className="rounded-md border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{position.name}</p>
                  <p className="text-xs text-muted">
                    {position.education_level
                      ? EDUCATION_LABEL[position.education_level]
                      : 'escolaridade não informada'}
                    {position.vacancies ? ` · ${position.vacancies} vagas` : ''}
                    {position.salary_cents ? ` · ${formatCurrency(position.salary_cents)}` : ''}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-danger"
                  onClick={() => removePosition.mutate(position.public_id)}
                >
                  <Trash2 />
                </Button>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {position.subjects.map((item) => (
                  <span
                    key={item.subject.public_id}
                    className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2.5 py-1 text-xs"
                  >
                    {item.subject.name}
                    <Badge variant="outline">peso {item.weight}</Badge>
                    <button
                      type="button"
                      className="text-subtle hover:text-danger"
                      aria-label={`Remover ${item.subject.name}`}
                      onClick={() =>
                        unlinkSubject.mutate({
                          positionPublicId: position.public_id,
                          subjectPublicId: item.subject.public_id,
                        })
                      }
                    >
                      ×
                    </button>
                  </span>
                ))}
                {position.subjects.length === 0 && (
                  <span className="text-xs text-subtle">nenhuma disciplina vinculada</span>
                )}
              </div>

              <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto]">
                <Field label="" htmlFor={`subject-${position.public_id}`}>
                  <Select
                    id={`subject-${position.public_id}`}
                    aria-label={`Disciplina para ${position.name}`}
                    value={subjectByPosition[position.public_id] ?? ''}
                    onChange={(event) =>
                      setSubjectByPosition({
                        ...subjectByPosition,
                        [position.public_id]: event.target.value,
                      })
                    }
                  >
                    <option value="">selecione a disciplina</option>
                    {subjects.data?.items.map((subject) => (
                      <option key={subject.public_id} value={subject.public_id}>
                        {subject.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Input
                  className="w-24"
                  placeholder="peso"
                  aria-label={`Peso da disciplina em ${position.name}`}
                  value={weightByPosition[position.public_id] ?? ''}
                  onChange={(event) =>
                    setWeightByPosition({
                      ...weightByPosition,
                      [position.public_id]: event.target.value,
                    })
                  }
                />
                <Button
                  variant="outline"
                  disabled={!subjectByPosition[position.public_id]}
                  loading={
                    linkSubject.isPending && linkSubject.variables === position.public_id
                  }
                  onClick={() => linkSubject.mutate(position.public_id)}
                >
                  Vincular
                </Button>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
