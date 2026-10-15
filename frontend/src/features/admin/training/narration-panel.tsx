import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AudioLines, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api/client'
import { trainingApi } from '@/lib/api/training'
import { queryKeys } from '@/lib/query-client'
import type { Training } from '@/lib/api/types'

/**
 * Narração da aula, no estúdio.
 *
 * Gera só os trechos que faltam: o áudio é identificado pelo texto, pela
 * direção de cena, pela voz e pelo modelo — reabrir a tela não gasta nada, e
 * reescrever uma vírgula gera só aquele trecho.
 *
 * Sem provedor de voz configurado o painel **diz o motivo** em vez de esconder
 * o botão. Quem administra precisa saber o que falta, não descobrir sozinho.
 */
export function NarrationPanel({ lesson }: { lesson: Training }) {
  const queryClient = useQueryClient()

  const narration = useQuery({
    queryKey: queryKeys.adminTrainingNarration(lesson.public_id),
    queryFn: () => trainingApi.adminNarration(lesson.public_id),
  })
  const voices = useQuery({
    queryKey: queryKeys.trainingVoices,
    queryFn: () => trainingApi.voices(),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.adminTrainingNarration(lesson.public_id),
    })
    queryClient.invalidateQueries({ queryKey: queryKeys.trainingNarration(lesson.public_id) })
  }

  const generate = useMutation({
    mutationFn: (force: boolean) => trainingApi.generateNarration(lesson.public_id, force),
    onSuccess: (result) => {
      toast.success(`Narração pronta: ${result.ready} de ${result.total} trechos.`)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível gerar a narração.',
      ),
  })

  const setVoice = useMutation({
    mutationFn: (voice: string) => trainingApi.setVoice(lesson.public_id, voice || null),
    onSuccess: () => {
      toast.success('Voz salva. Gere a narração para ouvi-la nesta voz.')
      queryClient.invalidateQueries({
        queryKey: queryKeys.adminTrainingLesson(lesson.public_id),
      })
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar a voz.'),
  })

  const data = narration.data
  const blocked = data?.unavailable_reason

  return (
    <section className="space-y-3 rounded-lg border border-border p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <AudioLines className="size-4 text-primary" aria-hidden />
          Narração
        </h3>
        {data && !blocked && (
          <span className="font-mono text-xs tabular-nums text-muted">
            {data.ready}/{data.total} trechos
          </span>
        )}
      </header>

      {blocked ? (
        // O motivo em vez do botão: esconder o recurso faria parecer que ele
        // não existe, quando o que falta é uma configuração.
        <Alert tone="warning">{blocked}</Alert>
      ) : (
        <>
          <p className="text-xs text-muted">
            A direção de cena sai do próprio roteiro — tipo da cena, emoção do personagem e
            termos em destaque. O áudio fica gravado: só o que mudou é gerado de novo.
          </p>

          {voices.data && voices.data.length > 0 && (
            <label className="flex flex-wrap items-center gap-2 text-xs">
              Voz desta aula
              <select
                className="rounded-md border border-border bg-surface px-2 py-1.5 text-xs"
                aria-label="Voz desta aula"
                value={lesson.narration_voice ?? ''}
                disabled={setVoice.isPending}
                onChange={(event) => setVoice.mutate(event.target.value)}
              >
                <option value="">
                  Padrão da plataforma{data?.voice ? ` (${data.voice})` : ''}
                </option>
                {voices.data.map((voice) => (
                  <option key={voice.slug} value={voice.slug}>
                    {voice.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              loading={generate.isPending && !generate.variables}
              disabled={generate.isPending}
              onClick={() => generate.mutate(false)}
            >
              <AudioLines /> {data?.is_complete ? 'Gerar o que faltar' : 'Gerar narração'}
            </Button>
            {data && data.ready > 0 && (
              <Button
                size="sm"
                variant="ghost"
                loading={generate.isPending && generate.variables === true}
                disabled={generate.isPending}
                onClick={() => generate.mutate(true)}
              >
                <RefreshCw /> Refazer tudo
              </Button>
            )}
          </div>

          {data?.is_complete && (
            <p className="text-xs text-success">
              Aula narrada na voz {data.voice}. O player usa esse áudio no lugar da voz do
              navegador.
            </p>
          )}
        </>
      )}
    </section>
  )
}
