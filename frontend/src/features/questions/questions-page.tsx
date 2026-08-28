import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History, ListChecks, Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { catalogApi } from '@/lib/api/catalog'
import { questionsApi } from '@/lib/api/questions'
import { queryKeys } from '@/lib/query-client'
import type { QuestionDifficulty } from '@/lib/api/types'
import { DIFFICULTY_LABEL } from './helpers'
import { QuestionCard } from './question-card'

const PAGE_SIZE = 10

export function QuestionsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [subject, setSubject] = useState('')
  const [difficulty, setDifficulty] = useState<QuestionDifficulty | ''>('')
  const debouncedSearch = useDebouncedValue(search, 400)

  const filters = {
    page,
    page_size: PAGE_SIZE,
    search: debouncedSearch || undefined,
    subject: subject || undefined,
    difficulty: difficulty || undefined,
  }

  const questions = useQuery({
    queryKey: queryKeys.questions(filters),
    queryFn: () => questionsApi.search(filters),
    placeholderData: keepPreviousData,
  })

  const subjects = useQuery({
    queryKey: ['catalog', 'subjects', 'all'],
    queryFn: () => catalogApi.subjects({ page: 1, page_size: 100 }),
  })

  const answer = useMutation({
    mutationFn: (input: { publicId: string; letter: string | null; seconds: number }) =>
      questionsApi.answer(input.publicId, {
        letter: input.letter,
        time_seconds: input.seconds,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['questions', 'history'] })
    },
  })

  const history = useQuery({
    queryKey: queryKeys.questionHistory({ page: 1 }),
    queryFn: () => questionsApi.history({ page: 1, page_size: 20 }),
  })

  function resetPage<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value)
      setPage(1)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Questões"
        description="Resolva questões do banco e veja, a cada resposta, por que a alternativa certa é a certa."
      />

      <Tabs defaultValue="resolver">
        <TabsList>
          <TabsTrigger value="resolver">Resolver</TabsTrigger>
          <TabsTrigger value="historico">Meu histórico</TabsTrigger>
        </TabsList>

        <TabsContent value="resolver" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
                aria-hidden
              />
              <Input
                className="pl-9"
                placeholder="Buscar no enunciado"
                value={search}
                onChange={(event) => resetPage(setSearch)(event.target.value)}
                aria-label="Buscar no enunciado"
              />
            </div>
            <Select
              value={subject}
              onChange={(event) => resetPage(setSubject)(event.target.value)}
              aria-label="Disciplina"
            >
              <option value="">Todas as disciplinas</option>
              {subjects.data?.items.map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select
              value={difficulty}
              onChange={(event) =>
                resetPage(setDifficulty)(event.target.value as QuestionDifficulty | '')
              }
              aria-label="Dificuldade"
            >
              <option value="">Qualquer dificuldade</option>
              {(Object.keys(DIFFICULTY_LABEL) as QuestionDifficulty[]).map((value) => (
                <option key={value} value={value}>
                  {DIFFICULTY_LABEL[value]}
                </option>
              ))}
            </Select>
          </div>

          {questions.isLoading && <SkeletonList rows={3} />}
          {questions.isError && (
            <ErrorState error={questions.error} onRetry={() => questions.refetch()} />
          )}

          {questions.data?.items.length === 0 && (
            <EmptyState
              icon={ListChecks}
              title="Nenhuma questão encontrada"
              description={
                debouncedSearch || subject || difficulty
                  ? 'Nenhuma questão publicada atende a esses filtros. Tente ampliar a busca.'
                  : 'O banco de questões ainda não tem questões publicadas para este filtro.'
              }
            />
          )}

          <div className="space-y-4">
            {questions.data?.items.map((question, index) => (
              <QuestionCard
                key={question.public_id}
                question={question}
                index={(page - 1) * PAGE_SIZE + index}
                onAnswer={(letter, seconds) =>
                  answer.mutateAsync({ publicId: question.public_id, letter, seconds })
                }
              />
            ))}
          </div>

          {questions.data && questions.data.pages > 1 && (
            <div className="flex items-center justify-between text-sm text-muted">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                Anterior
              </Button>
              <span>
                Página {questions.data.page} de {questions.data.pages} · {questions.data.total}{' '}
                questões
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= questions.data.pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Próxima
              </Button>
            </div>
          )}
        </TabsContent>

        <TabsContent value="historico" className="space-y-3">
          {history.isLoading && <SkeletonList rows={4} />}
          {history.isError && (
            <ErrorState error={history.error} onRetry={() => history.refetch()} />
          )}
          {history.data?.items.length === 0 && (
            <EmptyState
              icon={History}
              title="Você ainda não respondeu questões"
              description="Cada resposta registrada aqui alimenta o simulado dos erros e as estatísticas do seu desempenho."
            />
          )}
          <ul className="space-y-2">
            {history.data?.items.map((item) => (
              <li
                key={item.public_id}
                className="flex items-start gap-3 rounded-md border border-border p-3 text-sm"
              >
                <Badge
                  variant={item.is_blank ? 'warning' : item.is_correct ? 'success' : 'danger'}
                >
                  {item.is_blank ? 'Em branco' : item.is_correct ? 'Acerto' : 'Erro'}
                </Badge>
                <span className="min-w-0 flex-1">
                  <span className="block line-clamp-2">{item.question_statement}</span>
                  <span className="mt-1 block text-xs text-subtle">
                    {new Date(item.created_at).toLocaleString('pt-BR')}
                    {item.selected_letter && ` · marcou ${item.selected_letter}`}
                    {item.time_seconds > 0 && ` · ${item.time_seconds}s`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </TabsContent>
      </Tabs>
    </div>
  )
}
