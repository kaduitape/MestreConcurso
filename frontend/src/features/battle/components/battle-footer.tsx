import { Flame, Heart, Star } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BattleHud, BattleStatus } from '@/lib/api/types'

/**
 * As cores escritas por extenso, em par.
 *
 * O Tailwind 4 só emite a classe que ele **vê escrita no código**. Derivar
 * `bg-…` de `text-…` com `replace` em tempo de execução deixaria a barra sem cor
 * na folha publicada — foi assim que os monstros saíram pretos uma vez.
 */
const METER_TONE = {
  hp: { icon: 'text-danger', bar: 'bg-danger' },
  focus: { icon: 'text-game-cyan', bar: 'bg-game-cyan' },
  xp: { icon: 'text-game-gold', bar: 'bg-game-gold' },
} as const

function Meter({
  label,
  value,
  ratio,
  tone,
  icon: Icon,
}: {
  label: string
  value: string
  ratio: number
  tone: keyof typeof METER_TONE
  icon: typeof Heart
}) {
  const colors = METER_TONE[tone]
  return (
    <div className="flex items-center gap-2">
      <Icon className={cn('size-4 shrink-0', colors.icon)} aria-hidden />
      <div className="h-2 w-full min-w-16 overflow-hidden rounded-full bg-black/50 ring-1 ring-white/10">
        <div
          className={cn('h-full rounded-full', colors.bar)}
          style={{ width: `${Math.round(Math.min(1, Math.max(0, ratio)) * 100)}%` }}
        />
      </div>
      <span className="shrink-0 font-mono text-[0.7rem] tabular-nums text-muted">{value}</span>
      <span className="sr-only">{label}</span>
    </div>
  )
}

/**
 * O rodapé do guerreiro: nível, vida, foco do dia e XP.
 *
 * Todos os números já eram medidos em outro lugar do produto — nível e XP saem
 * do razão contábil da gamificação, o foco sai da soma real das sessões de
 * estudo de hoje.
 *
 * O alvo do foco é **o que o próprio candidato reservou para hoje no plano**.
 * Sem plano não há alvo, e aí **não há barra**: uma barra sem denominador seria
 * um enfeite fingindo medir alguma coisa. No lugar dela fica o motivo, escrito.
 */
export function BattleFooter({
  hud,
  status,
  className,
}: {
  hud: BattleHud
  status: BattleStatus
  className?: string
}) {
  const hasFocusTarget = hud.focus_target_minutes !== null && hud.focus_target_minutes > 0

  return (
    <div className={cn('battle-plate w-full flex-col items-stretch gap-2 py-2.5', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-game-gold">Nível {hud.level}</span>
        <span className="font-mono text-[0.7rem] tracking-normal text-subtle normal-case">
          {hud.xp_for_next === null
            ? `${hud.xp_total} XP · nível máximo`
            : `${hud.xp_into_level}/${hud.xp_for_next} XP para o próximo nível`}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <Meter
          label="Vida do guerreiro"
          icon={Heart}
          tone="hp"
          ratio={status.player_hp_ratio}
          value={`${status.player_hp}/${status.player_max_hp}`}
        />

        {hasFocusTarget ? (
          <Meter
            label="Foco de hoje"
            icon={Flame}
            tone="focus"
            ratio={hud.focus_minutes / hud.focus_target_minutes!}
            value={`${hud.focus_minutes}/${hud.focus_target_minutes} min`}
          />
        ) : (
          <p
            className="text-[0.68rem] leading-tight tracking-normal text-subtle normal-case"
            title={hud.focus_reason ?? undefined}
          >
            {hud.focus_minutes} min de foco hoje · sem alvo no plano
          </p>
        )}

        <Meter
          label="Progresso de nível"
          icon={Star}
          tone="xp"
          ratio={hud.xp_ratio}
          value={`${hud.xp_total} XP`}
        />
      </div>
    </div>
  )
}

/**
 * Os estandartes laterais.
 *
 * Puro enfeite, e por isso escondidos de leitores de tela e sumindo abaixo de
 * `xl`: numa tela estreita eles roubariam largura do enunciado, que é a única
 * coisa nesta página que não pode ceder espaço.
 */
export function BattleBanner({ words, className }: { words: string[]; className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        'hidden w-24 shrink-0 flex-col items-center gap-1 self-start xl:flex',
        'rounded-b-[2.5rem] border border-t-0 border-game-gold/25 bg-gradient-to-b',
        'from-game-purple/25 to-transparent px-3 pt-4 pb-10',
        className,
      )}
    >
      {words.map((word) => (
        <span
          key={word}
          className="text-[0.62rem] font-black tracking-[0.14em] text-slate-300/70 uppercase"
        >
          {word}
        </span>
      ))}
    </div>
  )
}
