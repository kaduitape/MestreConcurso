import * as React from 'react'
import { cn } from '@/lib/utils'

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground shadow-xs transition placeholder:text-subtle',
        'focus:border-primary focus:outline-2 focus:outline-offset-1 focus:outline-primary',
        'disabled:cursor-not-allowed disabled:opacity-60',
        invalid && 'border-danger focus:outline-danger',
        className,
      )}
      {...props}
    />
  )
})

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        'min-h-24 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm shadow-xs transition placeholder:text-subtle focus:border-primary focus:outline-2 focus:outline-offset-1 focus:outline-primary',
        className,
      )}
      {...props}
    />
  )
})
