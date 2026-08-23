import { AlertOctagon, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError
      ? error.message
      : 'Algo saiu errado ao carregar estas informações.'
  const requestId = error instanceof ApiError ? error.requestId : null

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-danger/40 bg-danger-soft/40 px-6 py-10 text-center">
      <AlertOctagon className="size-5 text-danger" aria-hidden />
      <div className="space-y-1">
        <p className="font-medium text-foreground">{message}</p>
        {requestId && <p className="text-xs text-subtle">Referência: {requestId}</p>}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw /> Tentar novamente
        </Button>
      )}
    </div>
  )
}
