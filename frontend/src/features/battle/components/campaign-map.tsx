import { Check, Map, Swords } from 'lucide-react'
import { GameButton } from '@/components/game/game-button'
import { EmptyState } from '@/components/feedback/empty-state'
import { cn } from '@/lib/utils'
import type { BattleCampaign } from '@/lib/api/types'

/**
 * O mapa da campanha.
 *
 * Os estágios **não são conteúdo inventado**: são as disciplinas que o Priority
 * Score já apontou como mais frágeis, na ordem em que ele as apontou. Sem
 * Priority Score não há mapa — e a tela diz isso, em vez de desenhar uma
 * fantasia de progresso.
 *
 * Nenhum estágio tranca outro. Quem quiser começar pelo terceiro começa: matéria
 * de estudo não fica atrás de progresso de jogo.
 */
export function CampaignMap({
  campaign,
  onFight,
  pending,
}: {
  campaign: BattleCampaign
  onFight: (subjectPublicId: string) => void
  pending: string | null
}) {
  if (campaign.empty_reason) {
    return (
      <EmptyState icon={Map} title="Sem campanha ainda" description={campaign.empty_reason} />
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        {campaign.cleared} de {campaign.total} estágios vencidos. A ordem é a do seu Priority
        Score — a campanha começa onde você está pior.
      </p>

      <ol className="space-y-2">
        {campaign.stages.map((stage) => (
          <li
            key={stage.subject_public_id}
            className={cn(
              'flex flex-wrap items-center gap-3 rounded-xl border p-3',
              stage.cleared
                ? 'border-success/30 bg-success-soft/[0.06]'
                : 'border-white/10 bg-white/[0.02]',
            )}
          >
            <span
              className={cn(
                'flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-black',
                stage.cleared ? 'bg-success text-white' : 'bg-white/10 text-slate-200',
              )}
              aria-hidden
            >
              {stage.cleared ? <Check className="size-4" /> : stage.order}
            </span>

            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{stage.label}</span>
              <span className="block text-xs text-subtle">
                {stage.battles === 0
                  ? 'Nenhuma batalha aqui ainda.'
                  : `${stage.battles} batalha(s) de chefe encerradas.`}
                {stage.blocked_reason ? ` ${stage.blocked_reason}` : ''}
              </span>
            </span>

            <GameButton
              size="sm"
              variant={stage.cleared ? 'ghost' : 'primary'}
              disabled={stage.is_locked}
              loading={pending === stage.subject_public_id}
              onClick={() => onFight(stage.subject_public_id)}
            >
              <Swords className="size-4" aria-hidden />
              {stage.cleared ? 'Enfrentar de novo' : 'Enfrentar'}
            </GameButton>
          </li>
        ))}
      </ol>
    </div>
  )
}
