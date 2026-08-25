import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
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
import { catalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { flashcardsApi } from '@/lib/api/flashcards'
import type { CardGeneration } from '@/lib/api/types'

export function GenerateDialog({
  open,
  onOpenChange,
  onGenerated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerated: () => void
}) {
  const [material, setMaterial] = useState('')
  const [quantity, setQuantity] = useState(5)
  const [subject, setSubject] = useState('')
  const [document, setDocument] = useState('')
  const [result, setResult] = useState<CardGeneration | null>(null)

  const subjects = useQuery({
    queryKey: ['catalog', 'subjects', 'all'],
    queryFn: () => catalogApi.subjects({ page: 1, page_size: 100 }),
    enabled: open,
  })

  const generate = useMutation({
    mutationFn: () =>
      flashcardsApi.generate({
        material,
        quantity,
        subject_public_id: subject || null,
        source_document: document || null,
      }),
    onSuccess: (generated) => {
      setResult(generated)
      if (generated.created.length > 0) {
        toast.success(`${generated.created.length} cartão(ões) criado(s).`)
        onGenerated()
      }
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível gerar.', {
        description:
          error instanceof ApiError && error.code === 'ai_feature_disabled'
            ? 'Configure o modelo de “flashcard.generation” no painel de Inteligência.'
            : undefined,
      }),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Gerar cartões a partir de um material</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-muted">
            Cada cartão gerado precisa citar um trecho literal do material colado abaixo. O que
            não se sustentar no texto é <strong>descartado</strong> — não entra no baralho com
            aviso, porque um verso errado revisado por repetição vira memória errada.
          </p>

          <Field
            label="Material"
            htmlFor="gen-material"
            hint="Cole o trecho da lei, do edital ou da apostila. Mínimo de 80 caracteres."
          >
            <textarea
              id="gen-material"
              rows={10}
              className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
              value={material}
              onChange={(event) => setMaterial(event.target.value)}
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Quantidade" htmlFor="gen-quantity">
              <Input
                id="gen-quantity"
                type="number"
                min={1}
                max={10}
                value={quantity}
                onChange={(event) => setQuantity(Number(event.target.value))}
              />
            </Field>
            <Field label="Disciplina" htmlFor="gen-subject" hint="Opcional">
              <Select
                id="gen-subject"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
              >
                <option value="">Sem disciplina</option>
                {subjects.data?.items.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Origem" htmlFor="gen-document" hint="Ex.: LEP art. 52">
              <Input
                id="gen-document"
                value={document}
                onChange={(event) => setDocument(event.target.value)}
              />
            </Field>
          </div>

          {result && (
            <div className="space-y-2 rounded-md border border-border p-3 text-sm">
              <p>
                <strong>{result.created.length}</strong> cartão(ões) criado(s)
                {result.discarded.length > 0 && (
                  <>
                    {' · '}
                    <strong>{result.discarded.length}</strong> descartado(s)
                  </>
                )}
              </p>
              {result.discarded.length > 0 && (
                <div className="space-y-1">
                  <p className="flex items-center gap-2 text-xs text-warning">
                    <AlertTriangle className="size-3.5" aria-hidden />
                    Descartados por citação não localizada no material:
                  </p>
                  <ul className="space-y-1 text-xs text-muted">
                    {result.discarded.map((item) => (
                      <li key={item}>“{item}”</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.skipped_reason && (
                <p className="text-xs text-muted">{result.skipped_reason}</p>
              )}
              {result.model && <p className="text-xs text-subtle">Modelo: {result.model}</p>}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
          <Button
            loading={generate.isPending}
            disabled={material.trim().length < 80}
            onClick={() => generate.mutate()}
          >
            <Sparkles /> Gerar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
