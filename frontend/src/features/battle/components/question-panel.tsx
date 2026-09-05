import { ProvenanceBadge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Question, QuestionOrigin } from '@/lib/api/types'

const ORIGIN_BADGE: Record<QuestionOrigin, 'OFICIAL' | 'IA' | 'HISTORICO'> = {
  OFFICIAL: 'OFICIAL',
  AI_GENERATED: 'IA',
  EDITORIAL: 'HISTORICO',
}

/**
 * O enunciado. É a parte da tela que **não** é jogo.
 *
 * Nada aqui se move: sem entrada animada, sem transição de opacidade no texto.
 * A questão é o motivo de a pessoa estar na plataforma; o combate acontece em
 * volta dela. A procedência aparece junto porque questão gerada por IA e
 * questão oficial não podem se confundir nem no meio de uma batalha.
 */
export function QuestionPanel({
  question,
  className,
}: {
  question: Question
  className?: string
}) {
  return (
    <section
      className={cn(
        'rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 sm:p-5',
        className,
      )}
      aria-label="Enunciado da questão"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-subtle">
        <ProvenanceBadge kind={ORIGIN_BADGE[question.origin] ?? 'HISTORICO'} />
        {question.subject_name && <span>{question.subject_name}</span>}
        {question.year !== null && <span className="tabular-nums">{question.year}</span>}
      </div>

      <p className="max-h-[42vh] overflow-y-auto whitespace-pre-line text-[0.95rem] leading-relaxed">
        {question.statement}
      </p>
    </section>
  )
}
