import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BookOpenText, Check, CirclePlay, FilePenLine, Sparkles, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { trainingApi } from '@/lib/api/training'
import { ApiError } from '@/lib/api/client'
import type { Training, TrainingInput, TrainingScene, TrainingScript } from '@/lib/api/types'
import { queryKeys } from '@/lib/query-client'

const STEPS = [
  'Estruturando conteúdo',
  'Criando narrativa pedagógica',
  'Identificando conceitos importantes',
  'Montando cenas e diálogos',
  'Criando pergunta de revisão',
]

const emptyForm: TrainingInput = {
  subject: '',
  topic: '',
  character_name: 'Mestre Arcanus',
  additional_prompt: '',
  level: 'INTERMEDIARIO',
  style: 'HISTORIA',
  target_duration_minutes: 10,
  board_name: '',
  research_before_generate: false,
}

const statusLabel: Record<Training['status'], string> = {
  DRAFT: 'Rascunho',
  GENERATING: 'Gerando',
  READY: 'Pronto para revisão',
  PUBLISHED: 'Publicado',
  ARCHIVED: 'Arquivado',
}

const selectClass =
  'h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground shadow-xs transition focus:border-primary focus:outline-2 focus:outline-offset-1 focus:outline-primary'

function scriptOf(lesson: Training): TrainingScript {
  return {
    ...lesson.script,
    objectives: lesson.script.objectives ?? [],
    scenes: lesson.script.scenes ?? [],
  }
}

export function TrainingStudioSection() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<TrainingInput>(emptyForm)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const lessons = useQuery({
    queryKey: queryKeys.adminTraining({ page: 1, page_size: 30 }),
    queryFn: () => trainingApi.adminList({ page: 1, page_size: 30 }),
  })
  const selected = useQuery({
    queryKey: queryKeys.adminTrainingLesson(selectedId ?? ''),
    queryFn: () => trainingApi.adminTraining(selectedId!),
    enabled: Boolean(selectedId),
  })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'training'] })

  const create = useMutation({
    mutationFn: () => trainingApi.create(form),
    onSuccess: (lesson) => {
      setSelectedId(lesson.public_id)
      invalidate()
      toast.success('Rascunho criado. Agora gere o roteiro com IA.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar o rascunho.'),
  })
  const generate = useMutation({
    mutationFn: (publicId: string) => trainingApi.generate(publicId),
    onSuccess: (lesson) => {
      queryClient.setQueryData(queryKeys.adminTrainingLesson(lesson.public_id), lesson)
      invalidate()
      toast.success(`${lesson.script.scenes.length} cenas foram geradas para revisão.`)
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível gerar o roteiro. Verifique a configuração da IA.',
      ),
  })

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Estúdio de Treinamento">
        A IA gera um roteiro em cenas editáveis. Nada é publicado automaticamente: revise diálogo,
        destaques e pergunta antes de liberar para os candidatos.
      </Alert>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Sparkles /> Criar treinamento</CardTitle>
            <CardDescription>Transforme um tema de concurso em uma missão de aprendizagem.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault()
                create.mutate()
              }}
            >
              <Field label="Matéria" htmlFor="training-subject">
                <Input id="training-subject" required value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} placeholder="Língua Portuguesa" />
              </Field>
              <Field label="Assunto" htmlFor="training-topic">
                <Input id="training-topic" required value={form.topic} onChange={(event) => setForm({ ...form, topic: event.target.value })} placeholder="Crase" />
              </Field>
              <Field label="Personagem" htmlFor="training-character">
                <Input id="training-character" required value={form.character_name} onChange={(event) => setForm({ ...form, character_name: event.target.value })} />
              </Field>
              <Field label="Banca (opcional)" htmlFor="training-board">
                <Input id="training-board" value={form.board_name} onChange={(event) => setForm({ ...form, board_name: event.target.value })} placeholder="FGV" />
              </Field>
              <Field label="Nível" htmlFor="training-level">
                <select id="training-level" className={selectClass} value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value as TrainingInput['level'] })}>
                  <option value="BASICO">Básico</option><option value="INTERMEDIARIO">Intermediário</option><option value="AVANCADO">Avançado</option><option value="ESPECIALISTA">Especialista</option>
                </select>
              </Field>
              <Field label="Estilo" htmlFor="training-style">
                <select id="training-style" className={selectClass} value={form.style} onChange={(event) => setForm({ ...form, style: event.target.value as TrainingInput['style'] })}>
                  <option value="AULA">Aula normal</option><option value="HISTORIA">História fantástica</option><option value="MISSAO">Missão</option><option value="BATALHA">Batalha</option><option value="INVESTIGACAO">Investigação</option><option value="MILITAR">Treinamento militar</option><option value="DESAFIO">Desafio</option><option value="REVISAO">Revisão rápida</option>
                </select>
              </Field>
              <Field label="Duração" htmlFor="training-duration">
                <select id="training-duration" className={selectClass} value={form.target_duration_minutes} onChange={(event) => setForm({ ...form, target_duration_minutes: Number(event.target.value) })}>
                  <option value={5}>5 minutos</option><option value={10}>10 minutos</option><option value={15}>15 minutos</option><option value={20}>20 minutos</option>
                </select>
              </Field>
              <Field className="sm:col-span-2" label="Observações para a IA" htmlFor="training-prompt" hint="Ex.: explique de modo simples e destaque pegadinhas da FGV.">
                <Textarea id="training-prompt" value={form.additional_prompt} onChange={(event) => setForm({ ...form, additional_prompt: event.target.value })} />
              </Field>
              <div className="sm:col-span-2"><Button type="submit" loading={create.isPending}><Sparkles /> Criar rascunho</Button></div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Meus treinamentos</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {lessons.isLoading && <SkeletonList rows={3} />}
            {lessons.data?.items.length === 0 && <p className="text-sm text-muted">Nenhum treinamento criado ainda.</p>}
            {lessons.data?.items.map((lesson) => (
              <button type="button" key={lesson.public_id} onClick={() => setSelectedId(lesson.public_id)} className="w-full rounded-md border border-border p-3 text-left transition hover:bg-surface-muted">
                <div className="flex items-start justify-between gap-2"><strong className="text-sm">{lesson.title}</strong><Badge variant={lesson.status === 'PUBLISHED' ? 'success' : 'neutral'}>{statusLabel[lesson.status]}</Badge></div>
                <p className="mt-1 text-xs text-muted">{lesson.subject} · {lesson.character_name}</p>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      {selected.isLoading && <SkeletonList rows={5} />}
      {selected.data && <TrainingEditor lesson={selected.data} generating={generate.isPending} onGenerate={() => generate.mutate(selected.data!.public_id)} onSaved={invalidate} />}
    </div>
  )
}

function TrainingEditor({ lesson, generating, onGenerate, onSaved }: { lesson: Training; generating: boolean; onGenerate: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const metrics = useQuery({
    queryKey: ['admin', 'training', lesson.public_id, 'metrics'],
    queryFn: () => trainingApi.metrics(lesson.public_id),
    enabled: lesson.status === 'PUBLISHED',
  })
  const [title, setTitle] = useState(lesson.title)
  const [script, setScript] = useState<TrainingScript>(scriptOf(lesson))
  useEffect(() => { setTitle(lesson.title); setScript(scriptOf(lesson)) }, [lesson])
  const scenes = script.scenes ?? []
  const pipeline = useMemo(() => STEPS, [])
  const updateScene = (index: number, patch: Partial<TrainingScene>) => setScript((current) => ({ ...current, scenes: current.scenes.map((scene, sceneIndex) => sceneIndex === index ? { ...scene, ...patch } : scene) }))
  const save = useMutation({
    mutationFn: () => trainingApi.saveScript(lesson.public_id, { title, script: script as unknown as Record<string, unknown> }),
    onSuccess: (result) => { queryClient.setQueryData(queryKeys.adminTrainingLesson(result.public_id), result); onSaved(); toast.success('Cenas salvas.') },
    onError: (error: unknown) => toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar as cenas.'),
  })
  const publish = useMutation({
    mutationFn: () => trainingApi.publish(lesson.public_id),
    onSuccess: (result) => { queryClient.setQueryData(queryKeys.adminTrainingLesson(result.public_id), result); onSaved(); toast.success('Treinamento publicado.') },
    onError: (error: unknown) => toast.error(error instanceof ApiError ? error.message : 'Não foi possível publicar.'),
  })

  return <Card>
    <CardHeader>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle className="flex items-center gap-2"><FilePenLine /> Editor do treinamento</CardTitle><CardDescription>{lesson.status === 'DRAFT' ? 'Gere o roteiro para abrir as cenas.' : `${scenes.length} cena(s) editáveis`}</CardDescription></div><Badge variant={lesson.status === 'PUBLISHED' ? 'success' : 'neutral'}>{statusLabel[lesson.status]}</Badge></div>
    </CardHeader>
    <CardContent className="space-y-5">
      {lesson.generation_error && <Alert tone="danger" title="A geração falhou">{lesson.generation_error}</Alert>}
      {generating && <div className="rounded-md border border-primary/30 bg-primary/5 p-4"><p className="font-medium">Gerando treinamento com IA…</p><ol className="mt-3 grid gap-2 text-sm text-muted sm:grid-cols-2">{pipeline.map((step) => <li key={step} className="flex items-center gap-2"><Check className="size-4 animate-pulse text-primary" />{step}</li>)}</ol></div>}
      <div className="flex flex-wrap gap-2"><Button loading={generating} onClick={onGenerate}><Sparkles /> {scenes.length ? 'Gerar novo roteiro' : 'Gerar treinamento com IA'}</Button>{scenes.length > 0 && <><Button variant="outline" loading={save.isPending} onClick={() => save.mutate()}><Upload /> Salvar cenas</Button><Button variant="outline" asChild><Link to={`/dia-de-treinamento/${lesson.public_id}`} target="_blank"><CirclePlay /> Visualizar</Link></Button><Button loading={publish.isPending} onClick={() => publish.mutate()} disabled={lesson.status === 'PUBLISHED'}><BookOpenText /> {lesson.status === 'PUBLISHED' ? 'Publicado' : 'Publicar'}</Button></>}</div>
      {lesson.status === 'PUBLISHED' && metrics.data && <div className="grid gap-3 rounded-md border border-border bg-surface-muted/40 p-4 sm:grid-cols-4"><div><p className="text-xs text-muted">Inícios</p><strong>{metrics.data.starts}</strong></div><div><p className="text-xs text-muted">Conclusões</p><strong>{metrics.data.completions}</strong></div><div><p className="text-xs text-muted">Taxa de conclusão</p><strong>{Math.round(metrics.data.completion_rate * 100)}%</strong></div><div><p className="text-xs text-muted">Foco médio</p><strong>{Math.round(metrics.data.average_focus_seconds / 60)} min</strong></div></div>}
      {scenes.length > 0 && <><Field label="Título" htmlFor="training-title"><Input id="training-title" value={title} onChange={(event) => setTitle(event.target.value)} /></Field><div className="space-y-4">{scenes.map((scene, index) => <div key={scene.id ?? index} className="rounded-md border border-border p-4"><div className="mb-3 flex items-center justify-between"><strong>Cena {index + 1}</strong><Badge variant="neutral">{scene.type}</Badge></div><div className="grid gap-3 lg:grid-cols-2"><Field label="Fala / diálogo" htmlFor={`dialogue-${index}`}><Textarea id={`dialogue-${index}`} value={scene.dialogue ?? ''} onChange={(event) => updateScene(index, { dialogue: event.target.value, narration: event.target.value })} /></Field><Field label="Texto na tela" htmlFor={`screen-text-${index}`}><Textarea id={`screen-text-${index}`} value={scene.screen_text ?? ''} onChange={(event) => updateScene(index, { screen_text: event.target.value })} /></Field><Field label="Palavras-chave (separadas por vírgula)" htmlFor={`keywords-${index}`}><Input id={`keywords-${index}`} value={(scene.keywords ?? []).join(', ')} onChange={(event) => updateScene(index, { keywords: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })} /></Field><Field label="Duração (segundos)" htmlFor={`duration-${index}`}><Input id={`duration-${index}`} type="number" min="3" max="90" value={scene.duration ?? 12} onChange={(event) => updateScene(index, { duration: Number(event.target.value) || 12 })} /></Field></div></div>)}</div></>}
    </CardContent>
  </Card>
}
