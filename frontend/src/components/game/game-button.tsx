import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const gameButtonVariants = cva(
  'group relative inline-flex min-h-11 items-center justify-center gap-2 overflow-hidden rounded-xl px-5 text-sm font-extrabold tracking-[0.04em] text-white uppercase transition-[transform,filter,box-shadow,border-color] duration-200 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-game-purple-light before:pointer-events-none before:absolute before:inset-y-0 before:-left-1/3 before:w-1/4 before:skew-x-[-20deg] before:bg-white/15 before:opacity-0 before:blur-sm before:transition-[left,opacity] before:duration-700 group-hover:before:left-[120%] group-hover:before:opacity-100 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary:
          'bg-gradient-to-br from-game-purple to-game-blue shadow-[0_10px_30px_rgb(124_58_237/0.3)] hover:-translate-y-0.5 hover:brightness-110 hover:shadow-[0_14px_36px_rgb(124_58_237/0.42)]',
        action:
          'bg-gradient-to-br from-game-blue to-game-cyan shadow-[0_10px_26px_rgb(37_99_235/0.24)] hover:-translate-y-0.5 hover:brightness-110',
        success:
          'bg-gradient-to-br from-emerald-600 to-success shadow-[0_10px_26px_rgb(34_197_94/0.2)] hover:-translate-y-0.5 hover:brightness-110',
        warning:
          'bg-gradient-to-br from-game-gold to-game-orange shadow-[0_10px_26px_rgb(245_158_11/0.22)] hover:-translate-y-0.5 hover:brightness-110',
        danger: 'bg-danger hover:-translate-y-0.5 hover:brightness-110',
        ghost:
          'border border-white/10 bg-white/[0.04] text-slate-200 hover:-translate-y-0.5 hover:border-game-purple/40 hover:bg-white/[0.07]',
      },
      size: {
        sm: 'min-h-10 rounded-lg px-3 text-xs',
        md: 'min-h-11 px-5',
        lg: 'min-h-14 px-7 text-base',
        hero: 'min-h-16 w-full px-8 text-base sm:text-lg',
        icon: 'size-11 min-h-11 px-0',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

export interface GameButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof gameButtonVariants> {
  asChild?: boolean
  loading?: boolean
}

export function GameButton({
  asChild,
  loading,
  disabled,
  variant,
  size,
  className,
  children,
  ...props
}: GameButtonProps) {
  const sharedProps = {
    className: cn(gameButtonVariants({ variant, size }), className),
    ...props,
  }

  if (asChild) {
    return <Slot {...sharedProps}>{children}</Slot>
  }

  return (
    <button {...sharedProps} disabled={disabled || loading}>
      {loading && <Loader2 className="animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { gameButtonVariants }
