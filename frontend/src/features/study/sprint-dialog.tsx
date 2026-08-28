import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Zap } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ApiError } from '@/lib/api/client'
import { studyApi } from '@/lib/api/study'
import { cn } from '@/lib/utils'
import { formatMinutes } from './helpers'

const OPTIONS = [15, 30, 45, 60]

/** "Tenho X minutos": monta um estudo pronto para o tempo disponível agora. */
export function SprintDialog() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [minutes, setMinutes] = useState(30)

  const create = useMutation({
    mutationFn: () => studyApi.sprint(minutes),
    onSuccess: (tasks) => {
      const total = tasks.reduce((sum, task) => sum + task.planned_minutes, 0)
      toast.success(`Sprint de ${formatMinutes(total)} adicionado à sua missão de hoje.`)
      queryClient.invalidateQueries({ queryKey: ['study'] })
      setOpen(false)
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar o sprint.'),
  })

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Zap /> Tenho pouco tempo
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Quanto tempo você tem agora?</DialogTitle>
            <DialogDescription>
              O sprint é montado para caber no tempo informado: quanto mais curto, mais
              revisão e menos conteúdo novo.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-4 gap-2">
            {OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setMinutes(option)}
                className={cn(
                  'rounded-md border px-3 py-4 text-center transition',
                  minutes === option
                    ? 'border-primary bg-primary-soft text-primary'
                    : 'border-border hover:bg-surface-muted',
                )}
              >
                <span className="block text-lg font-semibold">{option}</span>
                <span className="text-xs text-muted">minutos</span>
              </button>
            ))}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button loading={create.isPending} onClick={() => create.mutate()}>
              <Zap /> Montar sprint
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
