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

interface Silhouette {
  /** O corpo — a forma que o olho reconhece de longe. */
  body: string
  /** Chifres, asas, rachaduras: o que separa um monstro de uma mancha. */
  extras: string[]
  /** Centro da cabeça, de onde os olhos são posicionados. */
  head: [number, number]
}

const SHAPES: Record<string, Silhouette> = {
  // Bruto: ombros largos, braços pesados, chifres curtos.
  brute: {
    body:
      'M41 13 C33 13 28 19 28 27 L28 33 L20 37 L14 55 L21 58 L26 43 L26 61 L29 88 ' +
      'L37 88 L38 70 L44 70 L45 88 L53 88 L56 61 L56 43 L61 58 L68 55 L62 37 L54 33 ' +
      'L54 27 C54 19 49 13 41 13 Z',
    extras: ['M29 19 L20 7 L32 14 Z', 'M53 19 L62 7 L50 14 Z'],
    head: [41, 27],
  },
  // Espectro: capuz e manto esgarçado, sem pernas.
  wisp: {
    body:
      'M41 10 C31 10 25 19 26 30 L21 60 Q25 76 20 89 L27 79 L31 89 L36 79 L41 89 ' +
      'L46 79 L51 89 L55 79 L62 89 Q57 76 61 60 L56 30 C57 19 51 10 41 10 Z',
    extras: [],
    head: [41, 29],
  },
  // Golem: cabeça de pedra sobre ombros largos.
  hulk: {
    body: 'M22 88 L22 60 L14 54 L17 40 L30 34 L52 34 L65 40 L68 54 L60 60 L60 88 Z',
    extras: ['M32 9 L50 9 L52 27 L48 27 L48 35 L34 35 L34 27 L30 27 Z'],
    head: [41, 19],
  },
  // Serpente: capelo aberto sobre o corpo enrolado.
  coil: {
    body: 'M41 15 Q25 20 23 35 Q22 45 30 50 L52 50 Q60 45 59 35 Q57 20 41 15 Z',
    extras: [
      'M34 50 L48 50 L50 63 Q50 73 40 79 Q32 83 34 89 L23 89 Q21 78 30 70 Q38 64 36 57 Z',
    ],
    head: [41, 34],
  },
  // Gárgula: corpo agachado entre duas asas abertas.
  winged: {
    body: 'M41 89 L33 77 Q29 65 33 53 Q35 43 41 41 Q47 43 49 53 Q53 65 49 77 Z',
    extras: [
      'M34 52 L11 31 L16 51 L7 47 L18 68 L33 70 Z',
      'M48 52 L71 31 L66 51 L75 47 L64 68 L49 70 Z',
      'M35 44 L31 33 L39 40 Z',
      'M47 44 L51 33 L43 40 Z',
    ],
    head: [41, 52],
  },
}

/** Variações de olhar, em deslocamento a partir do centro da cabeça. */
const EYES: Record<number, [number, number][]> = {
  0: [
    [-6, 0],
    [6, 0],
  ],
  1: [
    [-7, -2],
    [6, 2],
  ],
  2: [[0, 0]],
  3: [
    [-8, 2],
    [0, -5],
    [8, 2],
  ],
}

/**
 * Cor por token, em classe utilitária e não em `var()` montado em tempo de
 * execução.
 *
 * O Tailwind 4 só emite a variável de tema que ele vê escrita no código. Um
 * `fill={`var(--color-${token})`}` não é visto por ele — a variável some da
 * folha publicada e o monstro sai preto. Escrever a classe inteira resolve, e
 * o mapa deixa explícito qual token o servidor pode mandar.
 */
const FILL: Record<string, string> = {
  'game-purple': 'fill-game-purple',
  'game-blue': 'fill-game-blue',
  'game-cyan': 'fill-game-cyan',
  'game-gold': 'fill-game-gold',
  'game-orange': 'fill-game-orange',
  success: 'fill-success',
  danger: 'fill-danger',
}

const STROKE: Record<string, string> = {
  'game-purple': 'stroke-game-purple',
  'game-purple-light': 'stroke-game-purple-light',
  'game-blue': 'stroke-game-blue',
  'game-cyan': 'stroke-game-cyan',
  'game-gold': 'stroke-game-gold',
  'game-orange': 'stroke-game-orange',
  success: 'stroke-success',
  danger: 'stroke-danger',
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
  // Arte cadastrada no painel entra no lugar da silhueta, com os mesmos quatro
  // estados de animação. A silhueta é o padrão, nunca o destino.
  if (monster.image_url) {
    return <MonsterArt monster={monster} size={size} mood={mood} className={className} />
  }
  return <MonsterSilhouette monster={monster} size={size} mood={mood} className={className} />
}

/** O mesmo movimento da silhueta, aplicado a uma imagem. */
function useMonsterMotion(mood: MonsterMood) {
  const reduce = useReducedMotion()
  const animation =
    reduce || mood === 'idle'
      ? { y: reduce ? 0 : [0, -3, 0] }
      : mood === 'attack'
        ? { y: [0, -6, 0], scale: [1, 1.12, 1] }
        : mood === 'hurt'
          ? { x: [0, -5, 6, -3, 0] }
          : { scale: [1, 0.95], opacity: [1, 0] }
  return {
    animate: animation,
    transition: {
      duration: mood === 'idle' ? 2.2 : mood === 'dead' ? 0.6 : 0.4,
      repeat: mood === 'idle' && !reduce ? Infinity : 0,
      ease: 'easeInOut' as const,
    },
  }
}

function MonsterArt({
  monster,
  size,
  mood,
  className,
}: {
  monster: BattleMonster
  size: 'sm' | 'lg'
  mood: MonsterMood
  className?: string
}) {
  const motionProps = useMonsterMotion(mood)
  return (
    <motion.img
      src={monster.image_url ?? undefined}
      alt={monster.letter ? `${monster.name}, alternativa ${monster.letter}` : monster.name}
      draggable={false}
      className={cn(
        'select-none object-contain',
        size === 'lg' ? 'h-24 w-auto sm:h-28' : 'h-9 w-9',
        mood === 'hurt' && 'brightness-150',
        mood === 'dead' && 'pointer-events-none opacity-40 grayscale',
        className,
      )}
      {...motionProps}
      style={{ willChange: 'transform' }}
    />
  )
}

function MonsterSilhouette({
  monster,
  size,
  mood,
  className,
}: {
  monster: BattleMonster
  size: 'sm' | 'lg'
  mood: MonsterMood
  className?: string
}) {
  const reduce = useReducedMotion()
  const shape = SHAPES[monster.shape] ?? SHAPES.brute
  const [headX, headY] = shape.head
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
      <g
        className={cn(
          'transition-[filter]',
          FILL[monster.color_token] ?? 'fill-game-purple',
          STROKE[monster.accent_token] ?? 'stroke-game-cyan',
          mood === 'hurt' && 'brightness-150',
        )}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      >
        {shape.extras.map((extra) => (
          <path key={extra} d={extra} />
        ))}
        <path d={shape.body} />
      </g>
      {eyes.map(([dx, dy]) => (
        <circle
          key={`${dx}-${dy}`}
          cx={headX + dx}
          cy={headY + dy}
          r={size === 'lg' ? 3 : 3.5}
          className="fill-game-bg"
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
