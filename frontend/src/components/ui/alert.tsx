import * as React from 'react'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

const styles = {
  info: { className: 'bg-info-soft text-info', Icon: Info },
  success: { className: 'bg-success-soft text-success', Icon: CheckCircle2 },
  warning: { className: 'bg-warning-soft text-warning', Icon: AlertTriangle },
  danger: { className: 'bg-danger-soft text-danger', Icon: XCircle },
} as const

export function Alert({
  tone = 'info',
  title,
  children,
  className,
}: {
  tone?: keyof typeof styles
  title?: string
  children?: React.ReactNode
  className?: string
}) {
  const { className: toneClass, Icon } = styles[tone]
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-md p-3 text-sm', toneClass, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="opacity-90">{children}</div>}
      </div>
    </div>
  )
}
