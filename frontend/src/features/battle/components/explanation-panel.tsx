import { cn } from '@/lib/utils'
import type { BattleAnswerResult } from '@/lib/api/types'

/**
 * A explicação da questão, depois do golpe.
 *
 * Aparece só quando pedida. A batalha dá o resultado em um segundo; a
 * explicação é leitura, e leitura interrompida por animação não é lida. Por
 * isso este painel é estático: entra e fica.
 */
export function ExplanationPanel({
  result,
  className,
}: {
  result: BattleAnswerResult
  className?: string
}) {
  const hasContent = result.explanation || result.correct_feedback || result.selected_feedback

  return (
    <section
      className={cn(
        'space-y-3 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4 text-sm',
        className,
      )}
      aria-label="Explicação da questão"
    >
      <p className="text-xs font-semibold tracking-wide text-subtle uppercase">
        Por que a resposta é {result.correct_letter ?? '—'}
      </p>

      {result.correct_feedback && (
        <p className="leading-relaxed whitespace-pre-line">{result.correct_feedback}</p>
      )}

      {!result.is_correct && result.selected_feedback && (
        <p className="leading-relaxed whitespace-pre-line text-muted">
          <span className="font-semibold text-danger">Sua escolha: </span>
          {result.selected_feedback}
        </p>
      )}

      {result.explanation && (
        <p className="leading-relaxed whitespace-pre-line text-muted">{result.explanation}</p>
      )}

      {!hasContent && (
        <p className="text-muted">
          Esta questão ainda não tem explicação cadastrada. Nada foi gerado para preencher o
          espaço.
        </p>
      )}
    </section>
  )
}
