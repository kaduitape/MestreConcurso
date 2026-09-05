import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { BattleMonster } from '@/lib/api/types'

/**
 * Silhuetas de monstro em SVG inline.
 *
 * SVG em vez de imagem por três razões práticas: não há download (nada a esperar
 * antes da primeira questão), escala sem borrar em qualquer tela, e a cor sai
 * dos tokens do tema em vez de estar queimada no arquivo. Arte em WebP pode
 * substituir isto depois sem tocar no resto — o componente só precisa do
 * `shape` que o servidor manda.
 *
 * O desenho é sóbrio de propósito: fantasia medieval, não mascote fofo.
 */

const SHAPES: Record<string, string> = {
  // Corpo largo, ombros altos.
  brute: 'M32 84 L24 52 Q20 34 32 26 Q42 18 50 26 Q62 34 58 52 L50 84 Z',
  // Vulto alongado, base esgarçada.
  wisp: 'M41 84 Q26 70 28 46 Q30 22 41 16 Q52 22 54 46 Q56 70 41 84 Z',
  // Blocos de pedra empilhados.
  hulk: 'M22 84 L22 46 L30 30 L52 30 L60 46 L60 84 Z',
  // Espiral que desce.
  coil: 'M41 84 Q22 74 30 56 Q38 40 26 32 Q34 20 48 26 Q62 34 54 52 Q46 70 58 80 Z',
  // Asas fechadas sobre o corpo.
  winged: 'M41 84 L26 62 Q18 44 30 30 Q41 20 52 30 Q64 44 56 62 Z',
}

const EYES: Record<number, { cx: number; cy: number }[]> = {
  0: [
    { cx: 35, cy: 42 },
    { cx: 47, cy: 42 },
  ],
  1: [
    { cx: 34, cy: 40 },
    { cx: 48, cy: 44 },
  ],
  2: [{ cx: 41, cy: 42 }],
  3: [
    { cx: 33, cy: 44 },
    { cx: 41, cy: 38 },
    { cx: 49, cy: 44 },
  ],
}

export type MonsterMood = 'idle' | 'attack' | 'hurt' | 'dead'

export function Monster({
  monster,
  size = 'lg',
  mood = 'idle',
  className,
}: {
  monster: BattleMonster
  size?: 'sm' | 'lg'
  mood?: MonsterMood
  className?: string
}) {
  const reduce = useReducedMotion()
  const path = SHAPES[monster.shape] ?? SHAPES.brute
  const eyes = EYES[monster.variant % 4] ?? EYES[0]

  // Só transform e opacity: são as duas propriedades que o navegador anima na
  // placa de vídeo, sem recalcular layout a cada quadro.
  const animation =
    reduce || mood === 'idle'
      ? { y: reduce ? 0 : [0, -3, 0] }
      : mood === 'attack'
        ? { y: [0, -6, 0], scale: [1, 1.12, 1] }
        : mood === 'hurt'
          ? { x: [0, -5, 6, -3, 0] }
          : { scale: [1, 0.95], opacity: [1, 0] }

  const duration = mood === 'idle' ? 2.2 : mood === 'dead' ? 0.6 : 0.4

  return (
    <motion.svg
      viewBox="0 0 82 92"
      className={cn(
        size === 'lg' ? 'h-24 w-auto sm:h-28' : 'h-9 w-9',
        mood === 'dead' && 'pointer-events-none',
        className,
      )}
      role="img"
      aria-label={
        monster.letter ? `${monster.name}, alternativa ${monster.letter}` : monster.name
      }
      animate={animation}
      transition={{
        duration,
        repeat: mood === 'idle' && !reduce ? Infinity : 0,
        ease: 'easeInOut',
      }}
      style={{ willChange: 'transform' }}
    >
      <path
        d={path}
        className={cn('transition-[filter]', mood === 'hurt' && 'brightness-150')}
        fill={`var(--color-${monster.color_token})`}
        stroke={`var(--color-${monster.accent_token})`}
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {eyes.map((eye) => (
        <circle
          key={`${eye.cx}-${eye.cy}`}
          cx={eye.cx}
          cy={eye.cy}
          r={size === 'lg' ? 3 : 3.5}
          fill="var(--color-game-bg)"
        />
      ))}
    </motion.svg>
  )
}

/** O avatar circular do modelo compacto: o monstro pequeno, ao lado do texto. */
export function MonsterAvatar({
  monster,
  mood = 'idle',
  className,
}: {
  monster: BattleMonster
  mood?: MonsterMood
  className?: string
}) {
  const reduce = useReducedMotion()
  return (
    <motion.span
      className={cn(
        'flex size-11 shrink-0 items-center justify-center rounded-full border',
        'border-white/10 bg-white/[0.04]',
        className,
      )}
      // No modelo compacto, só o avatar se mexe. O texto fica parado, para a
      // leitura não sair do lugar debaixo dos olhos de quem responde.
      animate={
        reduce
          ? {}
          : mood === 'attack'
            ? { scale: [1, 1.25, 1], x: [0, 6, 0] }
            : mood === 'hurt'
              ? { x: [0, -4, 4, 0] }
              : mood === 'dead'
                ? { scale: 0.9, opacity: 0.35 }
                : {}
      }
      transition={{ duration: mood === 'dead' ? 0.5 : 0.35 }}
      style={{ willChange: 'transform' }}
    >
      <Monster monster={monster} size="sm" mood="idle" />
    </motion.span>
  )
}
