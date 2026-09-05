import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ImageOff, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { battleArtApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import type { BattleAssetSlot } from '@/lib/api/types'

const KIND_LABEL: Record<BattleAssetSlot['kind'], string> = {
  PLAYER: 'Guerreiro',
  MONSTER: 'Monstros',
  SCENERY: 'Cenários',
}

const KIND_ORDER: BattleAssetSlot['kind'][] = ['PLAYER', 'MONSTER', 'SCENERY']

/** Formatos aceitos — a validação real acontece no servidor, pelos bytes. */
const ACCEPT = 'image/png,image/jpeg,image/webp,image/gif'

function sizeLabel(bytes: number | null): string {
  if (!bytes) return ''
  return bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function SlotCard({
  slot,
  onUpload,
  onRemove,
  busy,
}: {
  slot: BattleAssetSlot
  onUpload: (file: File) => void
  onRemove: () => void
  busy: boolean
}) {
  const input = useRef<HTMLInputElement>(null)

  return (
    <li className="flex gap-3 rounded-lg border border-border p-3">
      <div
        className={cn(
          'flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-md',
          'border border-border bg-surface-muted',
        )}
      >
        {slot.image_url ? (
          <img
            src={slot.image_url}
            alt={slot.label}
            className="size-full object-contain"
            loading="lazy"
          />
        ) : (
          <ImageOff className="size-6 text-subtle" aria-hidden />
        )}
      </div>

      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-medium">{slot.label}</p>
        {slot.image_url ? (
          <p className="truncate text-xs text-muted">
            {slot.original_filename ?? 'imagem'} · {sizeLabel(slot.size_bytes)}
          </p>
        ) : (
          // Lugar vazio diz o que a tela desenha no lugar. Sem isso, o painel
          // pareceria uma lista de pendências sem consequência.
          <p className="text-xs text-subtle">{slot.fallback}</p>
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            className="hidden"
            aria-label={`Arquivo de ${slot.label}`}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) onUpload(file)
              event.target.value = ''
            }}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            <Upload /> {slot.image_url ? 'Substituir' : 'Enviar arte'}
          </Button>
          {slot.public_id && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={onRemove}>
              <Trash2 /> Remover
            </Button>
          )}
        </div>
      </div>
    </li>
  )
}

/**
 * Cadastro da arte da Batalha RPG.
 *
 * A silhueta em SVG é o padrão, não o destino: ela garante que a batalha
 * funcione no dia um, sem download e sem depender de ninguém desenhar nada.
 * Aqui a arte de verdade entra — e sai, se não prestar — sem deploy.
 *
 * O painel lista **todos** os lugares, inclusive os vazios, com o que a tela
 * desenha enquanto estiverem vazios. Uma lista só do que já foi enviado
 * esconderia exatamente o que falta fazer.
 */
export function BattleArtSection() {
  const queryClient = useQueryClient()
  const [busyKey, setBusyKey] = useState<string | null>(null)

  const slots = useQuery({
    queryKey: queryKeys.battleArt,
    queryFn: () => battleArtApi.list(),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.battleArt })
    // A batalha aberta passa a mostrar a arte nova na próxima leitura.
    queryClient.invalidateQueries({ queryKey: ['game', 'battle'] })
  }

  const upload = useMutation({
    mutationFn: (input: { kind: string; slug: string; file: File }) =>
      battleArtApi.upload(input.kind, input.slug, input.file),
    onSuccess: () => {
      toast.success('Arte enviada. Vale a partir da próxima questão.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível enviar a arte.',
      ),
    onSettled: () => setBusyKey(null),
  })

  const remove = useMutation({
    mutationFn: (publicId: string) => battleArtApi.remove(publicId),
    onSuccess: () => {
      toast.success('Arte removida. A silhueta volta a aparecer.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível remover.'),
    onSettled: () => setBusyKey(null),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Batalha RPG — arte</CardTitle>
        <CardDescription>
          Monstros, guerreiro e cenários. Cada lugar sem arte usa a silhueta em SVG, e a troca
          vale sem deploy. PNG, JPEG, WebP ou GIF; o conteúdo do arquivo é conferido no
          servidor.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {slots.isLoading && <SkeletonList rows={4} />}

        {KIND_ORDER.map((kind) => {
          const group = (slots.data ?? []).filter((item) => item.kind === kind)
          if (group.length === 0) return null
          return (
            <section key={kind} className="space-y-2">
              <h3 className="text-sm font-semibold">{KIND_LABEL[kind]}</h3>
              <ul className="grid gap-2 md:grid-cols-2">
                {group.map((slot) => {
                  const key = `${slot.kind}/${slot.slug}`
                  return (
                    <SlotCard
                      key={key}
                      slot={slot}
                      busy={busyKey === key}
                      onUpload={(file) => {
                        setBusyKey(key)
                        upload.mutate({ kind: slot.kind, slug: slot.slug, file })
                      }}
                      onRemove={() => {
                        setBusyKey(key)
                        remove.mutate(slot.public_id!)
                      }}
                    />
                  )
                })}
              </ul>
            </section>
          )
        })}
      </CardContent>
    </Card>
  )
}
