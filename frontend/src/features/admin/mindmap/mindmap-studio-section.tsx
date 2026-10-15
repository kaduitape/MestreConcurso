/**
 * Estúdio de mapas mentais: a IA propõe, uma pessoa revisa, e só então publica.
 *
 * O editor é de texto porque o mapa é texto. Nada aqui chama gerador de imagem:
 * um "art. 37" que vira "ait. 3Z" numa figura ensina coisa falsa a quem decora.
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Map as MapIcon, Sparkles, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { mindmapApi } from '@/lib/api/mindmap'
import { queryKeys } from '@/lib/query-client'
import type { MindMap, MindMapContent, MindMapInput, MindMapTone } from '@/lib/api/types'
import { MindMapBoard } from '@/features/mindmap/mindmap-board'

const emptyForm: MindMapInput = {
  subject: '',
  topic: '',
  level: 'INTERMEDIARIO',
  max_panels: 6,
  source_content: '',
}

const statusLabel: Record<MindMap['status'], string> = {
  DRAFT: 'Rascunho',
  GENERATING: 'Gerando',
  READY: 'Pronto para revisão',
  PUBLISHED: 'Publicado',
  ARCHIVED: 'Arquivado',
}

const TONES: { value: MindMapTone; label: string }[] = [
  { value: 'NEUTRO', label: 'Neutro' },
  { value: 'CORRETO', label: 'Correto' },
  { value: 'INCORRETO', label: 'Incorreto' },
  { value: 'ALERTA', label: 'Pegadinha' },
]

const selectClass =
  'h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground shadow-xs transition focus:border-primary focus:outline-2 focus:outline-offset-1 focus:outline-primary'

function contentOf(item: MindMap): MindMapContent {
  const content = item.content ?? {}
  return { ...content, panels: content.panels ?? [], review_notes: content.review_notes ?? [] }
}

export function MindMapStudioSection() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<MindMapInput>(emptyForm)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<MindMapContent | null>(null)
  const [title, setTitle] = useState('')

  const params = { page: 1, page_size: 30 }
  const maps = useQuery({
    queryKey: queryKeys.adminMindmaps(params),
    queryFn: () => mindmapApi.adminList(params),
  })
  const selected = useQuery({
    queryKey: queryKeys.adminMindmap(selectedId ?? ''),
    queryFn: () => mindmapApi.adminMap(selectedId!),
    enabled: Boolean(selectedId),
  })
  const panelSpecs = useQuery({
    queryKey: queryKeys.mindmapPanels,
    queryFn: () => mindmapApi.panels(),
  })

  // O rascunho local acompanha o mapa aberto: a revisão é editada aqui e só
  // vai para o servidor quando a pessoa salvar.
  useEffect(() => {
    if (selected.data) {
      setDraft(contentOf(selected.data))
      setTitle(selected.data.title)
    }
  }, [selected.data])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'mindmaps'] })
  const fail = (fallback: string) => (error: unknown) =>
    toast.error(error instanceof ApiError ? error.message : fallback)

  const create = useMutation({
    mutationFn: () =>
      mindmapApi.create({ ...form, source_content: form.source_content?.trim() || null }),
    onSuccess: (item) => {
      setSelectedId(item.public_id)
      invalidate()
      toast.success('Rascunho criado. Agora gere o mapa com IA.')
    },
    onError: fail('Não foi possível criar o rascunho.'),
  })

  const generate = useMutation({
    mutationFn: (publicId: string) => mindmapApi.generate(publicId),
    onSuccess: (item) => {
      queryClient.setQueryData(queryKeys.adminMindmap(item.public_id), item)
      invalidate()
      toast.success(`${item.content.panels?.length ?? 0} painéis gerados para revisão.`)
    },
    onError: fail('Não foi possível gerar o mapa. Verifique a configuração da IA.'),
  })

  const save = useMutation({
    mutationFn: (publicId: string) =>
      mindmapApi.saveContent(publicId, { title, content: draft ?? {} }),
    onSuccess: (item) => {
      queryClient.setQueryData(queryKeys.adminMindmap(item.public_id), item)
      invalidate()
      toast.success('Revisão salva.')
    },
    onError: fail('Não foi possível salvar a revisão.'),
  })

  const publish = useMutation({
    mutationFn: (publicId: string) => mindmapApi.publish(publicId),
    onSuccess: (item) => {
      queryClient.setQueryData(queryKeys.adminMindmap(item.public_id), item)
      invalidate()
      toast.success('Mapa publicado para quem estuda.')
    },
    onError: fail('Não foi possível publicar o mapa.'),
  })

  const map = selected.data
  const panels = draft?.panels ?? []

  const updatePanels = (next: MindMapContent['panels']) =>
    setDraft((current) => (current ? { ...current, panels: next } : current))

  const editItem = (panelIndex: number, itemIndex: number, patch: Record<string, unknown>) =>
    updatePanels(
      panels.map((panel, index) =>
        index !== panelIndex
          ? panel
          : {
              ...panel,
              items: panel.items.map((item, position) =>
                position === itemIndex ? { ...item, ...patch } : item,
              ),
            },
      ),
    )

  const removeItem = (panelIndex: number, itemIndex: number) =>
    updatePanels(
      panels.map((panel, index) =>
        index !== panelIndex
          ? panel
          : { ...panel, items: panel.items.filter((_, position) => position !== itemIndex) },
      ),
    )

  const removePanel = (panelIndex: number) =>
    updatePanels(panels.filter((_, index) => index !== panelIndex))

  const notes = useMemo(() => draft?.review_notes ?? [], [draft])

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Estúdio de mapas mentais">
        A IA estrutura painéis, itens e cores; a plataforma desenha a moldura. Nada é publicado
        automaticamente — mapa mental é material de memorização, então confira cada linha antes
        de liberar.
      </Alert>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles /> Criar mapa mental
            </CardTitle>
            <CardDescription>
              Quanto mais fiel o material colado, menos a IA precisa supor.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault()
                create.mutate()
              }}
            >
              <Field label="Matéria" htmlFor="mindmap-subject">
                <Input
                  id="mindmap-subject"
                  required
                  value={form.subject}
                  onChange={(event) => setForm({ ...form, subject: event.target.value })}
                  placeholder="Direito Administrativo"
                />
              </Field>
              <Field label="Assunto" htmlFor="mindmap-topic">
                <Input
                  id="mindmap-topic"
                  required
                  value={form.topic}
                  onChange={(event) => setForm({ ...form, topic: event.target.value })}
                  placeholder="Princípios da Administração Pública"
                />
              </Field>
              <Field label="Nível" htmlFor="mindmap-level">
                <select
                  id="mindmap-level"
                  className={selectClass}
                  value={form.level}
                  onChange={(event) => setForm({ ...form, level: event.target.value })}
                >
                  <option value="BASICO">Básico</option>
                  <option value="INTERMEDIARIO">Intermediário</option>
                  <option value="AVANCADO">Avançado</option>
                </select>
              </Field>
              <Field label="Máximo de painéis" htmlFor="mindmap-panels">
                <select
                  id="mindmap-panels"
                  className={selectClass}
                  value={form.max_panels}
                  onChange={(event) =>
                    setForm({ ...form, max_panels: Number(event.target.value) })
                  }
                >
                  {[4, 5, 6, 7, 8].map((value) => (
                    <option key={value} value={value}>
                      {value} painéis
                    </option>
                  ))}
                </select>
              </Field>
              <div className="sm:col-span-2">
                <Field
                  label="Material de estudo (apostila, edital, resumo)"
                  htmlFor="mindmap-content"
                >
                  <Textarea
                    id="mindmap-content"
                    rows={6}
                    value={form.source_content ?? ''}
                    onChange={(event) =>
                      setForm({ ...form, source_content: event.target.value })
                    }
                    placeholder="Cole aqui o trecho da apostila ou do edital. Sem material, a IA fica restrita ao consenso técnico da matéria."
                  />
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? 'Criando…' : 'Criar rascunho'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapIcon /> Mapas do estúdio
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {maps.isLoading && <SkeletonList rows={3} />}
            {maps.data?.items.length === 0 && (
              <p className="text-sm text-muted">Nenhum mapa criado ainda.</p>
            )}
            {maps.data?.items.map((item) => (
              <button
                key={item.public_id}
                type="button"
                onClick={() => setSelectedId(item.public_id)}
                className={`w-full rounded-lg border p-3 text-left transition ${
                  selectedId === item.public_id
                    ? 'border-game-gold/60 bg-game-gold/10'
                    : 'border-border hover:border-game-gold/35'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-white">{item.title}</span>
                  <Badge variant={item.status === 'PUBLISHED' ? 'success' : 'neutral'}>
                    {statusLabel[item.status]}
                  </Badge>
                </div>
                <p className="mt-1 truncate text-xs text-muted">{item.subject}</p>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      {map && draft && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>{map.topic}</CardTitle>
                <CardDescription>
                  {map.subject} · {statusLabel[map.status]}
                  {map.model_slug ? ` · ${map.model_slug}` : ''}
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={() => generate.mutate(map.public_id)}
                  disabled={generate.isPending}
                >
                  <Sparkles className="size-4" />
                  {map.content.panels?.length ? 'Gerar de novo' : 'Gerar com IA'}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => save.mutate(map.public_id)}
                  disabled={save.isPending}
                >
                  Salvar revisão
                </Button>
                <Button
                  onClick={() => publish.mutate(map.public_id)}
                  disabled={publish.isPending || !panels.length}
                >
                  <Check className="size-4" /> Publicar
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {map.generation_error && (
              <Alert tone="danger" title="A última geração falhou">
                {map.generation_error}
              </Alert>
            )}
            {notes.length > 0 && (
              // A dúvida da IA não some: ela é o ponto de partida da revisão.
              <Alert tone="warning" title="A IA pediu conferência">
                <ul className="list-disc space-y-1 pl-5">
                  {notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </Alert>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Título do mapa" htmlFor="mindmap-title">
                <Input
                  id="mindmap-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </Field>
              <Field label="Texto do centro" htmlFor="mindmap-center">
                <Input
                  id="mindmap-center"
                  value={draft.center_label ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, center_label: event.target.value })
                  }
                />
              </Field>
            </div>

            {panels.length === 0 && (
              <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">
                Nenhum painel ainda. Gere o mapa com IA para começar a revisão.
              </p>
            )}

            <div className="space-y-4">
              {panels.map((panel, panelIndex) => (
                <div key={panel.kind} className="rounded-lg border border-border p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-white">{panel.title}</p>
                      <p className="game-label text-[0.6rem] text-muted">
                        {panel.label}
                        {panelSpecs.data && (
                          <span className="ml-2 normal-case tracking-normal">
                            {
                              panelSpecs.data.find((spec) => spec.kind === panel.kind)
                                ?.guidance
                            }
                          </span>
                        )}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removePanel(panelIndex)}
                      aria-label={`Remover painel ${panel.title}`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  <div className="mt-3 space-y-2">
                    {panel.items.map((item, itemIndex) => (
                      <div key={itemIndex} className="flex flex-wrap items-start gap-2">
                        <Textarea
                          rows={2}
                          className="min-w-0 flex-1"
                          aria-label={`Item ${itemIndex + 1} de ${panel.title}`}
                          value={item.text}
                          onChange={(event) =>
                            editItem(panelIndex, itemIndex, { text: event.target.value })
                          }
                        />
                        <select
                          className={`${selectClass} w-36`}
                          aria-label={`Tom do item ${itemIndex + 1} de ${panel.title}`}
                          value={item.tone}
                          onChange={(event) =>
                            editItem(panelIndex, itemIndex, { tone: event.target.value })
                          }
                        >
                          {TONES.map((tone) => (
                            <option key={tone.value} value={tone.value}>
                              {tone.label}
                            </option>
                          ))}
                        </select>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeItem(panelIndex, itemIndex)}
                          aria-label={`Remover item ${itemIndex + 1} de ${panel.title}`}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {panels.length > 0 && (
              <div>
                <p className="game-label mb-2 text-game-gold">Como o candidato vai ver</p>
                <MindMapBoard content={draft} />
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
