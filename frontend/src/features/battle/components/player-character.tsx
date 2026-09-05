import { motion, useReducedMotion } from 'framer-motion'
import warrior from '@/assets/game/strategist-character.webp'
import { cn } from '@/lib/utils'

export type PlayerMood = 'idle' | 'attack' | 'hurt' | 'dead'

/**
 * O guerreiro. Reusa o personagem que o Estúdio de Treinamento já trouxe, em
 * vez de introduzir uma segunda arte para a mesma pessoa dentro do produto.
 *
 * O avanço é um `translate` rápido, sem animação de caminhada: quatro estados
 * bastam para a resposta ter consequência, e cada estado a mais seria peso a
 * carregar em celular modesto.
 */
export function PlayerCharacter({
  mood = 'idle',
  className,
}: {
  mood?: PlayerMood
  className?: string
}) {
  const reduce = useReducedMotion()

  const animation = reduce
    ? {}
    : mood === 'attack'
      ? { x: [0, 26, 34, 0], y: [0, -6, 0, 0] }
      : mood === 'hurt'
        ? { x: [0, -6, 5, -3, 0] }
        : mood === 'dead'
          ? { opacity: 0.4, scale: 0.96, rotate: -4 }
          : { y: [0, -3, 0] }

  return (
    <motion.img
      src={warrior}
      alt="Seu guerreiro"
      draggable={false}
      className={cn(
        'h-28 w-auto select-none object-contain sm:h-36',
        mood === 'hurt' && 'brightness-150',
        className,
      )}
      animate={animation}
      transition={{
        duration: mood === 'idle' ? 2.4 : mood === 'attack' ? 0.55 : 0.4,
        repeat: mood === 'idle' && !reduce ? Infinity : 0,
        ease: 'easeInOut',
      }}
      style={{ willChange: 'transform' }}
    />
  )
}
