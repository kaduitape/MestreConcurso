/**
 * Curadoria do baralho oficial de flashcards.
 *
 * Três coisas esta tela não pode deixar passar:
 *
 * 1. **Rascunho não parece publicado.** Enquanto o baralho é rascunho, nenhum
 *    candidato o vê, e o selo diz isso com todas as letras — publicar é ação
 *    separada, nunca efeito colateral de salvar um cartão.
 * 2. **Cartão gerado por IA aparece marcado como tal**, mesmo dentro de um
 *    baralho oficial. "Oficial" diz quem publicou; "gerado por IA" diz quem
 *    escreveu. São informações diferentes, e as duas ficam à vista.
 * 3. **O descarte é mostrado.** Cartão sem citação literal no material não
 *    entra, e esconder isso faria a geração parecer melhor do que foi.
 */
import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, BookOpen, CheckCircle2, EyeOff, Plus, RotateCcw, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { adminDecksApi } from '@/lib/api/decks'
import { queryKeys } from '@/lib/query-client'
import type { DeckSourceKind, DeckStatus, OfficialDeck } from '@/lib/api/types'
import { ORIGIN_LABEL } from '@/features/flashcards/helpers'

/** Classes e rótulos literais: o Tailwind 4 só emite a cor que vê escrita. */
const STATUS: Record<DeckStatus, { label: string; variant: 'outline' | 'success' | 'warning' }> = {
  DRAFT: { label: 'rascunho — ninguém vê', variant: 'outline' },
  PUBLISHED: { label: 'publicado', variant: 'success' },
  ARCHIVED: { label: 'arquivado', variant: 'warning' },
}

const SOURCE_LABEL: Record<DeckSourceKind, string> = {
  EDITORIAL: 'escrito pela equipe',
  LESSON: 'gerado de aula publicada',
  NOTICE: 'gerado de trecho do edital',
  MATERIAL: 'gerado de material colado',
}

function DeckRow({ deck }: { deck: OfficialDeck }) {
  const queryClient = useQueryClient()
  const [aberto, setAberto] = useState(false)
  const [material, setMaterial] = useState('')
  const [quantidade, setQuantidade] = useState(8)
  const [frente, setFrente] = useState('')
  const [verso, setVerso] = useState('')
  const [descartados, setDescartados] = useState<string[]>([])
  const estado = STATUS[deck.status]
  const campo = (nome: string) => `deck-${deck.public_id}-${nome}`

  const detalhe = useQuery({
    queryKey: queryKeys.adminDeck(deck.public_id),
    queryFn: () => adminDecksApi.get(deck.public_id),
    enabled: aberto,
  })

  const invalidar = () => queryClient.invalidateQueries({ queryKey: ['admin', 'decks'] })
  const falhou = (error: unknown, padrao: string) =>
    toast.error(error instanceof ApiError ? error.message : padrao)

  const gerar = useMutation({
    mutationFn: () => adminDecksApi.generate(deck.public_id, { material, quantity: quantidade }),
    onSuccess: (resultado) => {
      invalidar()
      setMaterial('')
      setDescartados(resultado.discarded)
      toast.success(
        `${resultado.created.length} cartão(ões) criado(s)` +
          (resultado.discarded.length
            ? `, ${resultado.discarded.length} descartado(s) sem citação literal.`
            : '.'),
      )
    },
    onError: (error: unknown) => falhou(error, 'Não foi possível gerar.'),
  })

  const escrever = useMutation({
    mutationFn: () => adminDecksApi.addCard(deck.public_id, { front: frente, back: verso }),
    onSuccess: () => {
      invalidar()
      setFrente('')
      setVerso('')
      toast.success('Cartão escrito no baralho.')
    },
    onError: (error: unknown) => falhou(error, 'Não foi possível salvar o cartão.'),
  })

  const revisar = useMutation({
    mutationFn: (input: { card: string; isActive: boolean }) =>
      adminDecksApi.reviewCard(deck.public_id, input.card, input.isActive),
    onSuccess: (_resultado, input) => {
      invalidar()
      toast.success(
        input.isActive
          ? 'Cartão de volta à circulação.'
          : 'Cartão fora de circulação. O histórico de quem já o revisou continua gravado.',
      )
    },
    onError: (error: unknown) => falhou(error, 'Não foi possível atualizar o cartão.'),
  })

  const publicar = useMutation({
    mutationFn: () => adminDecksApi.publish(deck.public_id),
    onSuccess: () => {
      invalidar()
      toast.success('Baralho publicado. Quem assinar passa a receber os cartões.')
    },
    onError: (error: unknown) => falhou(error, 'Não foi possível publicar o baralho.'),
  })

  const arquivar = useMutation({
    mutationFn: () => adminDecksApi.archive(deck.public_id),
    onSuccess: () => {
      invalidar()
      toast.success('Baralho arquivado. Nenhum cartão foi apagado.')
    },
    onError: (error: unknown) => falhou(error, 'Não foi possível arquivar.'),
  })

  const reabrir = useMutation({
    mutationFn: () => adminDecksApi.reopen(deck.public_id),
    onSuccess: () => {
      invalidar()
      toast.success('Baralho de volta ao rascunho.')
    },
    onError: (error: unknown) => falhou(error, 'Não foi possível reabrir.'),
  })

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-white">{deck.title}</p>
          <p className="mt-0.5 text-[0.68rem] text-slate-500">
            {deck.subject_name ?? 'sem disciplina'} · {deck.topic_name ?? 'sem tópico'} ·{' '}
            {SOURCE_LABEL[deck.source_kind] ?? deck.source_kind}
          </p>
        </div>
        <Badge variant={estado.variant}>{estado.label}</Badge>
      </div>

      <p className="mt-2 text-xs text-slate-300">
        {deck.active_cards} cartão(ões) em circulação
        {deck.inactive_cards > 0 && `, ${deck.inactive_cards} fora de circulação`}
        {deck.ai_cards > 0 && ` · ${deck.ai_cards} gerado(s) por IA`} · {deck.subscribers}{' '}
        candidato(s) assinando
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline" onClick={() => setAberto((v) => !v)}>
          <BookOpen /> {aberto ? 'Fechar cartões' : 'Ver cartões'}
        </Button>
        {deck.status === 'DRAFT' && (
          <Button
            type="button"
            size="sm"
            loading={publicar.isPending}
            onClick={() => publicar.mutate()}
          >
            <CheckCircle2 /> Publicar
          </Button>
        )}
        {deck.status === 'PUBLISHED' && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            loading={arquivar.isPending}
            onClick={() => arquivar.mutate()}
          >
            <Archive /> Arquivar
          </Button>
        )}
        {deck.status === 'ARCHIVED' && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            loading={reabrir.isPending}
            onClick={() => reabrir.mutate()}
          >
            <RotateCcw /> Reabrir como rascunho
          </Button>
        )}
      </div>

      {aberto && (
        <div className="mt-3 space-y-4 border-t border-border pt-3">
          {deck.status !== 'ARCHIVED' && (
            <>
              <form
                className="grid gap-2 sm:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  escrever.mutate()
                }}
              >
                <Field label="Frente" htmlFor={campo('frente')}>
                  <Input
                    id={campo('frente')}
                    value={frente}
                    onChange={(event) => setFrente(event.target.value)}
                    placeholder="A pergunta do cartão"
                  />
                </Field>
                <Field label="Verso" htmlFor={campo('verso')}>
                  <Input
                    id={campo('verso')}
                    value={verso}
                    onChange={(event) => setVerso(event.target.value)}
                    placeholder="A resposta"
                  />
                </Field>
                <div className="sm:col-span-2">
                  <Button
                    type="submit"
                    size="sm"
                    loading={escrever.isPending}
                    disabled={frente.trim().length < 3 || verso.trim().length < 1}
                  >
                    <Plus /> Escrever cartão
                  </Button>
                </div>
              </form>

              <form
                className="space-y-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  gerar.mutate()
                }}
              >
                <Field
                  label="Gerar por IA a partir de um material"
                  htmlFor={campo('material')}
                  hint="Cada cartão precisa citar o material literalmente. O que não cita é descartado."
                >
                  <textarea
                    id={campo('material')}
                    rows={5}
                    className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
                    value={material}
                    onChange={(event) => setMaterial(event.target.value)}
                  />
                </Field>
                <div className="flex flex-wrap items-end gap-2">
                  <Field label="Quantos" htmlFor={campo('quantos')}>
                    <Input
                      id={campo('quantos')}
                      type="number"
                      min={1}
                      max={10}
                      className="w-24"
                      value={quantidade}
                      onChange={(event) => setQuantidade(Number(event.target.value))}
                    />
                  </Field>
                  <Button
                    type="submit"
                    size="sm"
                    loading={gerar.isPending}
                    disabled={material.trim().length < 80}
                  >
                    <Sparkles /> Gerar cartões
                  </Button>
                </div>
              </form>

              {descartados.length > 0 && (
                <Alert tone="warning">
                  {descartados.length} cartão(ões) descartado(s) por não citar o material
                  literalmente: {descartados.join(' · ')}
                </Alert>
              )}
            </>
          )}

          {detalhe.isPending && <SkeletonList rows={3} />}
          {detalhe.isError && <ErrorState error={detalhe.error} onRetry={() => detalhe.refetch()} />}
          {detalhe.data?.cards.length === 0 && (
            <p className="text-xs text-slate-500">
              Nenhum cartão ainda. Baralho sem cartão ativo não é publicado.
            </p>
          )}
          <div className="space-y-2">
            {detalhe.data?.cards.map((card) => (
              <div
                key={card.public_id}
                className="rounded-md border border-border/70 p-2 text-xs text-slate-300"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="min-w-0 flex-1 font-semibold text-white">{card.front}</p>
                  <div className="flex shrink-0 flex-wrap items-center gap-1">
                    <Badge variant={card.origin === 'AI' ? 'info' : 'outline'}>
                      {ORIGIN_LABEL[card.origin] ?? card.origin}
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      loading={revisar.isPending}
                      onClick={() =>
                        revisar.mutate({ card: card.public_id, isActive: !card.is_active })
                      }
                    >
                      {card.is_active ? <EyeOff /> : <RotateCcw />}
                      {card.is_active ? 'Tirar de circulação' : 'Devolver'}
                    </Button>
                  </div>
                </div>
                <p className="mt-1">{card.back}</p>
                {card.source_quote && (
                  <p className="mt-1 text-[0.68rem] text-slate-500">
                    Citação conferida no material: “{card.source_quote}”
                  </p>
                )}
                {!card.is_active && (
                  <p className="mt-1 text-[0.68rem] text-warning">
                    Fora de circulação: não entra na fila de ninguém.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function DecksSection() {
  const queryClient = useQueryClient()
  const [filtro, setFiltro] = useState<DeckStatus | ''>('')
  const [subject, setSubject] = useState('')
  const [topic, setTopic] = useState('')

  const decks = useQuery({
    queryKey: queryKeys.adminDecks({ status: filtro || 'all' }),
    queryFn: () => adminDecksApi.list({ page: 1, page_size: 50, deck_status: filtro || undefined }),
    placeholderData: keepPreviousData,
  })

  const subjects = useQuery({
    queryKey: queryKeys.adminSubjects({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.subjects({ page: 1, page_size: 100 }),
  })

  const topics = useQuery({
    queryKey: queryKeys.adminTopics(subject),
    queryFn: () => adminCatalogApi.topics(subject),
    enabled: Boolean(subject),
  })

  const criar = useMutation({
    mutationFn: () => adminDecksApi.create({ topic_public_id: topic }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'decks'] })
      setTopic('')
      toast.success('Baralho criado em rascunho.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar o baralho.'),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Baralhos oficiais</CardTitle>
        <CardDescription>
          Um baralho por tópico do catálogo. Ele nasce rascunho, invisível para quem estuda, e só
          chega a candidato depois de publicado — e só a quem assinar.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert tone="info">
          Cartão gerado por IA só entra se citar o material literalmente, e continua marcado como
          gerado por IA depois de publicado. A publicação passa pelo portão de auditoria de
          conteúdo.
        </Alert>

        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            criar.mutate()
          }}
        >
          <Field label="Disciplina" htmlFor="deck-subject">
            <Select
              id="deck-subject"
              className="w-56"
              value={subject}
              onChange={(event) => {
                setSubject(event.target.value)
                setTopic('')
              }}
            >
              <option value="">Escolha</option>
              {subjects.data?.items.map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Tópico" htmlFor="deck-topic">
            <Select
              id="deck-topic"
              className="w-64"
              value={topic}
              disabled={!subject || topics.isPending}
              onChange={(event) => setTopic(event.target.value)}
            >
              <option value="">Escolha</option>
              {topics.data?.map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>
          <Button type="submit" size="sm" loading={criar.isPending} disabled={!topic}>
            <Plus /> Criar baralho
          </Button>
          <Field label="Mostrar" htmlFor="deck-filter">
            <Select
              id="deck-filter"
              className="w-44"
              value={filtro}
              onChange={(event) => setFiltro(event.target.value as DeckStatus | '')}
            >
              <option value="">Todos</option>
              <option value="DRAFT">Rascunhos</option>
              <option value="PUBLISHED">Publicados</option>
              <option value="ARCHIVED">Arquivados</option>
            </Select>
          </Field>
        </form>

        {decks.isPending && <SkeletonList rows={3} />}
        {decks.isError && <ErrorState error={decks.error} onRetry={() => decks.refetch()} />}
        {decks.data?.items.length === 0 && (
          <EmptyState
            icon={BookOpen}
            title="Nenhum baralho oficial ainda"
            description="Escolha um tópico do catálogo para começar um baralho em rascunho."
          />
        )}
        <div className="space-y-2">
          {decks.data?.items.map((deck) => <DeckRow key={deck.public_id} deck={deck} />)}
        </div>
      </CardContent>
    </Card>
  )
}
