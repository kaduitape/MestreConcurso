import * as React from 'react'
import { cn } from '@/lib/utils'

export function TableWrapper({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('overflow-x-auto rounded-lg border border-border bg-surface', className)}
      {...props}
    />
  )
}

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn('w-full text-left text-sm', className)} {...props} />
}

export function Th({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        'border-b border-border px-4 py-3 text-xs font-semibold tracking-wide text-subtle uppercase',
        className,
      )}
      {...props}
    />
  )
}

export function Td({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('border-b border-border/60 px-4 py-3 align-middle', className)} {...props} />
}

export function Tr({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn('transition hover:bg-surface-muted/60', className)} {...props} />
}
