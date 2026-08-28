import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brain, Loader2, MessageSquarePlus, Send, Sparkles, Video } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { tutorApi, vocabularyApi } from '@/lib/api/tutor'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import type { AskResult, ChatMode, TutorStage, TutorVideo } from '@/lib/api/types'
import { MessageBubble } from './message-bubble'

const SUGGESTIONS = [
  'O que o meu edital diz sobre a data da prova?',
  'Como está o meu desempenho por disciplina?',
  'O que eu deveria estudar agora?',
]

export function TutorPage() {
  const queryClient = useQueryClient()
  const [active, setActive] = useState<string | null>(null)
  const [mode, setMode] = useState<ChatMode>('TUTOR')
  const [question, setQuestion] = useState('')
  const [stages, setStages] = useState<TutorStage[]>([])
  const [running, setRunning] = useState(false)
  const [videos, setVideos] = useState<TutorVideo[]>([])
  const [terms, setTerms] = useState<{ term: string; definition: string }[]>([])
  const cancelRef = useRef<(() => void) | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const conversations = useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => tutorApi.conversations(),
  })

  const conversation = useQuery({
    queryKey: queryKeys.conversation(active ?? ''),
    queryFn: () => tutorApi.conversation(active!),
    enabled: Boolean(active),
  })

  useEffect(() => {
    if (!active && conversations.data?.length) setActive(conversations.data[0].public_id)
  }, [active, conversations.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation.data?.messages.length, stages.length])

  useEffect(() => () => cancelRef.current?.(), [])

  const createConversation = useMutation({
    mutationFn: () => tutorApi.createConversation({ mode }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations })
      setActive(created.public_id)
      setStages([])
      setVideos([])
      setTerms([])
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível abrir a conversa.',
      ),
  })

  const saveTerm = useMutation({
    mutationFn: (input: { term: string; definition: string }) =>
      vocabularyApi.add({ term: input.term, definition: input.definition }),
    onSuccess: (entry) => {
      toast.success(`“${entry.term}” guardado no seu vocabulário.`)
      setTerms((current) => current.filter((item) => item.term !== entry.term))
      queryClient.invalidateQueries({ queryKey: ['vocabulary'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível guardar.'),
  })

  function send() {
    const text = question.trim()
    if (!text || !active || running) return

    setQuestion('')
    setStages([])
    setVideos([])
    setTerms([])
    setRunning(true)

    cancelRef.current = tutorApi.askStream(active, text, {
      onStage: (stage) => setStages((current) => [...current, stage]),
      onAnswer: (result: AskResult) => {
        setVideos(result.videos)
        setTerms(result.suggested_terms)
        setRunning(false)
        queryClient.invalidateQueries({ queryKey: queryKeys.conversation(active) })
        queryClient.invalidateQueries({ queryKey: queryKeys.conversations })
      },
      onError: (error) => {
        setRunning(false)
        const message =
          typeof error === 'object' && error !== null && 'message' in error
            ? String((error as { message: unknown }).message)
            : 'A conversa foi interrompida.'
        toast.error(message)
      },
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mestre IA"
        description="Responde com base no seu material — e diz quando não tem base para responder."
        actions={
          <div className="flex items-center gap-2">
            <Select
              value={mode}
              onChange={(event) => setMode(event.target.value as ChatMode)}
              aria-label="Modo"
              className="w-auto"
            >
              <option value="TUTOR">Tutor</option>
              <option value="TEACHER">Modo Professor</option>
            </Select>
            <Button
              loading={createConversation.isPending}
              onClick={() => createConversation.mutate()}
            >
              <MessageSquarePlus /> Nova conversa
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[260px_1fr_280px]">
        <Card className="hidden lg:block">
          <CardHeader>
            <CardTitle className="text-base">Conversas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {conversations.isLoading && <SkeletonList rows={3} />}
            {conversations.data?.length === 0 && (
              <p className="text-sm text-muted">Nenhuma conversa ainda.</p>
            )}
            {conversations.data?.map((item) => (
              <button
                key={item.public_id}
                type="button"
                onClick={() => setActive(item.public_id)}
                className={cn(
                  'w-full rounded-md p-2 text-left text-sm transition',
                  active === item.public_id
                    ? 'bg-primary-soft/50 text-primary'
                    : 'hover:bg-surface-muted',
                )}
              >
                <span className="block truncate">{item.title}</span>
                <span className="text-xs text-subtle">
                  {item.mode === 'TEACHER' ? 'Modo Professor' : 'Tutor'} · {item.message_count}{' '}
                  mensagem(ns)
                </span>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="flex min-h-[60vh] flex-col gap-4">
          <div className="flex-1 space-y-4">
            {!active && (
              <EmptyState
                icon={Brain}
                title="Comece uma conversa"
                description="O Mestre responde a partir do edital analisado e dos seus números. Sem base no seu material, ele diz isso em vez de inventar."
                action={
                  <Button onClick={() => createConversation.mutate()}>
                    <MessageSquarePlus /> Nova conversa
                  </Button>
                }
              />
            )}

            {conversation.isLoading && active && <SkeletonList rows={3} />}

            {conversation.data?.messages.length === 0 && (
              <div className="space-y-3 rounded-lg border border-dashed border-border p-6">
                <p className="text-sm font-medium">Sugestões para começar</p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((item) => (
                    <Button
                      key={item}
                      variant="outline"
                      size="sm"
                      onClick={() => setQuestion(item)}
                    >
                      {item}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {conversation.data?.messages.map((message) => (
              <MessageBubble key={message.public_id} message={message} />
            ))}

            {running && (
              <div className="space-y-2 rounded-lg border border-border bg-surface p-4">
                {stages.map((stage) => (
                  <p key={stage.key} className="flex items-center gap-2 text-sm">
                    {stage.key === 'done' ? (
                      <Sparkles className="size-4 text-success" aria-hidden />
                    ) : (
                      <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
                    )}
                    <span>{stage.label}</span>
                    {stage.detail && (
                      <span className="text-xs text-subtle">— {stage.detail}</span>
                    )}
                  </p>
                ))}
                {stages.length === 0 && (
                  <p className="flex items-center gap-2 text-sm text-muted">
                    <Loader2 className="size-4 animate-spin" aria-hidden /> Conectando…
                  </p>
                )}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <form
            className="flex items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              send()
            }}
          >
            <textarea
              rows={2}
              placeholder="Pergunte ao Mestre…"
              aria-label="Pergunta"
              disabled={!active || running}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  send()
                }
              }}
              className="flex-1 resize-none rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-60"
            />
            <Button type="submit" disabled={!active || running || !question.trim()}>
              <Send /> Enviar
            </Button>
          </form>
        </div>

        <div className="space-y-4">
          {terms.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Termos desta resposta</CardTitle>
                <CardDescription>
                  Guarde no seu vocabulário para revisar depois.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {terms.map((item) => (
                  <div key={item.term} className="rounded-md border border-border p-2 text-sm">
                    <p className="font-medium">{item.term}</p>
                    <p className="mt-0.5 text-xs text-muted">{item.definition}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      loading={saveTerm.isPending}
                      onClick={() => saveTerm.mutate(item)}
                    >
                      Guardar
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {videos.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Video className="size-4" aria-hidden /> Vídeos de apoio
                </CardTitle>
                <CardDescription>
                  Só aparecem aqui vídeos conferidos por uma pessoa da equipe.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {videos.map((video) => (
                  <a
                    key={video.public_id}
                    href={video.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-md border border-border p-2 text-sm transition hover:bg-surface-muted"
                  >
                    <span className="block font-medium">{video.title}</span>
                    <span className="mt-1 flex items-center gap-2 text-xs text-subtle">
                      {video.channel}
                      <Badge variant="success">conferido</Badge>
                    </span>
                  </a>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
