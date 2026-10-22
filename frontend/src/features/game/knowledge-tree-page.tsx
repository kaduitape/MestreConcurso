/**
 * A árvore de conhecimento na tela.
 *
 * Quatro coisas esta tela não pode deixar passar:
 *
 * 1. **A árvore não é uma ordem de pré-requisitos.** O desenho de árvore sugere
 *    "só depois de passar por aqui"; o edital não declara pré-requisito nenhum.
 *    O aviso está escrito no topo, não escondido num rodapé.
 * 2. **Nenhum ramo tranca conteúdo.** Todo estado é descritivo. Um tópico "não
 *    iniciado" está tão disponível quanto um dominado, e a tela diz isso.
 * 3. **Sem amostra não há porcentagem.** Em vez da taxa, aparece quantas
 *    respostas ainda faltam para ela significar algo.
 * 4. **Lacuna da plataforma não se mistura com desempenho.** Tópico sem vínculo
 *    e tópico sem material têm cor e bloco próprios, fora da contagem do que
 *    foi medido.
 */
import { useQuery } from '@tanstack/react-query'
import {
  CircleHelp,
  CircleSlash,
  PackageOpen,
  RefreshCw,
  Sprout,
  Target,
  TreePine,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import type {
  KnowledgeNodeState,
  KnowledgeSubject,
  KnowledgeTopic,
  KnowledgeTreeSummary,
} from '@/lib/api/types'

/**
 * Classes literais: o Tailwind 4 só emite a cor que **vê escrita no código**.
 * `text-${x}` montado em tempo de execução sai sem cor.
 */
const STATE: Record<
  KnowledgeNodeState,
  { label: string; icon: LucideIcon; tone: string; dot: string }
> = {
  MASTERED: {
    label: 'dominado',
    icon: Target,
    tone: 'text-success',
    dot: 'bg-success',
  },
  NEEDS_REVIEW: {
    label: 'pede revisão',
    icon: RefreshCw,
    tone: 'text-game-orange',
    dot: 'bg-game-orange',
  },
  MEASURED: {
    label: 'medido',
    icon: Target,
    tone: 'text-game-gold',
    dot: 'bg-game-gold',
  },
  IN_PROGRESS: {
    label: 'em andamento',
    icon: Sprout,
    tone: 'text-game-purple-light',
    dot: 'bg-game-purple',
  },
  NOT_STARTED: {
    label: 'não iniciado',
    icon: Sprout,
    tone: 'text-muted',
    dot: 'bg-white/20',
  },
  NOT_LINKED: {
    label: 'sem vínculo',
    icon: CircleHelp,
    tone: 'text-game-cyan',
    dot: 'bg-game-cyan',
  },
  NO_MATERIAL: {
    label: 'sem material',
    icon: PackageOpen,
    tone: 'text-game-cyan',
    dot: 'bg-game-cyan',
  },
}

/** Estados em que a plataforma não mediu nada — lacuna nossa, não do candidato. */
const UNMEASURED: KnowledgeNodeState[] = ['NOT_LINKED', 'NO_MATERIAL']

function pct(valor: number) {
  return `${Math.round(valor * 100)}%`
}

function plural(quantidade: number, singular: string, plural_: string) {
  return `${quantidade} ${quantidade === 1 ? singular : plural_}`
}

function TopicRow({ topic }: { topic: KnowledgeTopic }) {
  const visual = STATE[topic.state]
  const Icon = visual.icon
  const lacuna = UNMEASURED.includes(topic.state)

  return (
    <li className="flex items-start gap-3 border-b border-white/[0.04] py-2.5 last:border-0">
      <span className={`mt-1.5 size-2 shrink-0 rounded-full ${visual.dot}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
          {topic.label}
          <span className={`flex items-center gap-1 text-xs font-medium ${visual.tone}`}>
            <Icon className="size-3.5" aria-hidden />
            {visual.label}
          </span>
          {topic.accuracy !== null && (
            <Badge variant="outline">{pct(topic.accuracy)} de acerto</Badge>
          )}
          {topic.descendants > 0 && (
            // O ramo soma os subtópicos do catálogo: dizer isso evita a
            // impressão de que o número veio só do rótulo que está na tela.
            <Badge variant="outline">
              + {plural(topic.descendants, 'subtópico', 'subtópicos')}
            </Badge>
          )}
        </p>
        <p className="mt-0.5 text-xs text-muted">{topic.reason}</p>
        {!lacuna && (
          <p className="mt-1 text-[0.68rem] text-slate-500">
            {plural(topic.evidence.questions_available, 'questão', 'questões')} ·{' '}
            {plural(topic.evidence.lessons_available, 'aula', 'aulas')}
            {topic.evidence.lessons_done > 0 && ` (${topic.evidence.lessons_done} concluída)`} ·{' '}
            {plural(topic.evidence.mind_maps_available, 'mapa', 'mapas')} ·{' '}
            {plural(topic.evidence.cards, 'cartão', 'cartões')}
          </p>
        )}
        {topic.page_number !== null && (
          <p className="mt-0.5 text-[0.68rem] text-slate-500">
            Edital, página {topic.page_number}
          </p>
        )}
      </div>
    </li>
  )
}

function SubjectBranch({ subject }: { subject: KnowledgeSubject }) {
  const visual = STATE[subject.state]
  const medidos = subject.topics.filter((item) => !UNMEASURED.includes(item.state))
  const lacunas = subject.topics.filter((item) => UNMEASURED.includes(item.state))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <TreePine className="size-4 text-game-gold" aria-hidden />
          {subject.label}
          <span className={`text-xs font-medium ${visual.tone}`}>{visual.label}</span>
          {subject.accuracy !== null && (
            <Badge variant="outline">{pct(subject.accuracy)} de acerto</Badge>
          )}
          {/* Procedência do que o edital disse: conferido no PDF ou deduzido. */}
          <Badge variant={subject.evidence_level === 'OFFICIAL' ? 'success' : 'warning'}>
            {subject.evidence_level === 'OFFICIAL' ? 'oficial' : 'deduzido do edital'}
          </Badge>
        </CardTitle>
        <CardDescription>
          {subject.weight && `Peso ${subject.weight} no edital. `}
          {subject.questions_count !== null && `${subject.questions_count} questões na prova. `}
          {subject.reason}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {medidos.length > 0 && (
          <ul>
            {medidos.map((item) => (
              <TopicRow key={`${item.label}-${item.topic_id ?? 'x'}`} topic={item} />
            ))}
          </ul>
        )}

        {lacunas.length > 0 && (
          <div className="rounded-lg border border-dashed border-game-cyan/40 p-3">
            <p className="flex items-center gap-2 text-xs font-semibold text-game-cyan">
              <CircleSlash className="size-3.5" aria-hidden />
              {plural(lacunas.length, 'tópico que a plataforma', 'tópicos que a plataforma')} ainda
              não consegue medir
            </p>
            <p className="mt-0.5 text-[0.68rem] text-slate-500">
              Isto é lacuna nossa, não sua: não entra na sua taxa de acerto nem na fila do que
              estudar. O conteúdo continua aberto para estudo por fora da medição.
            </p>
            <ul className="mt-1">
              {lacunas.map((item) => (
                <TopicRow key={`${item.label}-lacuna`} topic={item} />
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Summary({ summary }: { summary: KnowledgeTreeSummary }) {
  const linhas: { label: string; valor: number; tone: string }[] = [
    { label: 'dominados', valor: summary.mastered, tone: 'text-success' },
    { label: 'pedem revisão', valor: summary.needs_review, tone: 'text-game-orange' },
    { label: 'em andamento', valor: summary.in_progress, tone: 'text-game-purple-light' },
    { label: 'não iniciados', valor: summary.not_started, tone: 'text-muted' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>O edital inteiro</CardTitle>
        <CardDescription>
          {plural(summary.subjects, 'disciplina', 'disciplinas')} e{' '}
          {plural(summary.topics, 'tópico', 'tópicos')} no conteúdo programático.{' '}
          {summary.measurable < summary.topics ? (
            <>
              A plataforma consegue medir {summary.measurable} deles — o resto está listado como
              lacuna nossa, com o motivo.
            </>
          ) : (
            <>Todos eles têm vínculo e material para serem medidos.</>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {linhas.map((item) => (
            <div key={item.label} className="rounded-lg border border-white/10 p-3">
              <dt className="text-xs text-muted">{item.label}</dt>
              <dd className={`text-xl font-black ${item.tone}`}>{item.valor}</dd>
            </div>
          ))}
        </dl>
        {(summary.not_linked > 0 || summary.no_material > 0) && (
          <p className="mt-3 text-xs text-game-cyan">
            Fora da conta acima:{' '}
            {summary.not_linked > 0 &&
              `${plural(summary.not_linked, 'tópico sem vínculo', 'tópicos sem vínculo')} com o catálogo`}
            {summary.not_linked > 0 && summary.no_material > 0 && ' e '}
            {summary.no_material > 0 &&
              `${plural(summary.no_material, 'tópico sem material', 'tópicos sem material')} cadastrado`}
            .
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function KnowledgeTreePage() {
  const tree = useQuery({
    queryKey: queryKeys.gameKnowledgeTree,
    queryFn: () => gameApi.knowledgeTree(),
  })

  if (tree.isLoading) return <SkeletonList rows={4} />
  if (tree.isError) return <ErrorState error={tree.error} onRetry={() => tree.refetch()} />

  const data = tree.data!

  return (
    <div className="space-y-6">
      <PageHeader
        title="Árvore de conhecimento"
        description={
          data.notice_title
            ? `Conteúdo programático de ${data.notice_title}.`
            : 'O conteúdo programático do seu edital, ramo por ramo.'
        }
      />

      {data.subjects.length === 0 ? (
        <EmptyState
          icon={TreePine}
          title="Ainda não há árvore para desenhar"
          description={data.unavailable_reason ?? 'Escolha seu concurso principal.'}
        />
      ) : (
        <>
          <Alert tone="info" title="A árvore é a hierarquia do edital, não uma ordem de estudo">
            Os ramos são disciplina → tópico, na ordem em que o edital escreveu. O edital{' '}
            <strong>não declara pré-requisito</strong>, e a plataforma não inventa um: nenhum ramo
            precisa de outro antes. Nenhum estado aqui tranca conteúdo — todos descrevem o que
            já foi medido, e todo tópico está aberto para estudo agora.
          </Alert>

          <Summary summary={data.summary} />

          {data.attention.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Por onde começar hoje</CardTitle>
                <CardDescription>
                  Primeiro o que esfriou depois de dominado, depois o pior acerto medido. Tópico
                  que a plataforma não consegue medir não entra aqui — a providência dele é nossa.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ol className="list-inside list-decimal space-y-1 text-sm text-slate-300">
                  {data.attention.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}

          {data.subjects.map((subject) => (
            <SubjectBranch key={`${subject.label}-${subject.subject_id ?? 'x'}`} subject={subject} />
          ))}
        </>
      )}
    </div>
  )
}
