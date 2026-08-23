import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="aurora grid min-h-dvh place-items-center px-6">
      <div className="max-w-md space-y-4 text-center">
        <span className="mx-auto grid size-12 place-items-center rounded-full bg-surface-muted text-muted">
          <Compass className="size-5" aria-hidden />
        </span>
        <h1 className="text-2xl font-semibold tracking-tight">Página não encontrada</h1>
        <p className="text-sm text-muted">
          O endereço acessado não existe ou ainda faz parte de uma fase não entregue.
        </p>
        <Button asChild>
          <Link to="/hoje">Voltar para o início</Link>
        </Button>
      </div>
    </div>
  )
}
