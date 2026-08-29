import * as React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'

type GameCardTone = 'default' | 'purple' | 'blue' | 'gold' | 'success' | 'danger'

const toneClass: Record<GameCardTone, string> = {
  default: 'border-white/[0.08]',
  purple: 'border-game-purple/30 shadow-[0_0_28px_rgb(124_58_237/0.12)]',
  blue: 'border-game-blue/30 shadow-[0_0_28px_rgb(37_99_235/0.12)]',
  gold: 'border-game-gold/30 shadow-[0_0_28px_rgb(245_158_11/0.1)]',
  success: 'border-success/25 shadow-[0_0_28px_rgb(34_197_94/0.08)]',
  danger: 'border-danger/25 shadow-[0_0_28px_rgb(239_68_68/0.08)]',
}

export interface GameCardProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: GameCardTone
  interactive?: boolean
}

export function GameCard({
  className,
  tone = 'default',
  interactive,
  ...props
}: GameCardProps) {
  return (
    <div
      className={cn(
        'game-panel rounded-2xl',
        toneClass[tone],
        interactive &&
          'cursor-pointer transition-[transform,border-color,box-shadow] duration-200 hover:-translate-y-1 hover:border-game-purple/45 hover:shadow-[0_18px_48px_rgb(0_0_0/0.3),0_0_28px_rgb(124_58_237/0.18)]',
        className,
      )}
      {...props}
    />
  )
}

export function GlowCard(props: GameCardProps) {
  return <GameCard tone="purple" {...props} />
}

export function AnimatedGameCard({
  delay = 0,
  className,
  children,
}: {
  delay?: number
  className?: string
  children: React.ReactNode
}) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduceMotion ? 0 : 0.36,
        delay: reduceMotion ? 0 : delay,
        ease: [0.22, 1, 0.36, 1],
      }}
      className={cn('game-panel rounded-2xl', className)}
    >
      {children}
    </motion.div>
  )
}
