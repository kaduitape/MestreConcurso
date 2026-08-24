import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ExternalLink, Plus, Trash2, Video } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { videosApi } from '@/lib/api/tutor'
import { queryKeys } from '@/lib/query-client'

export function VideosSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ title: '', url: '', channel: '', subject: '' })

  const params = { page, page_size: 20 }
  const videos = useQuery({
    queryKey: queryKeys.adminVideos(params),
    queryFn: () => videosApi.list(params),
    placeholderData: keepPreviousData,
  })

  const subjects = useQuery({
    queryKey: queryKeys.adminSubjects({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.subjects({ page: 1, page_size: 100 }),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'videos'] })

  const create = useMutation({
    mutationFn: () =>
      videosApi.create({
        title: form.title,
        url: form.url,
        channel: form.channel || null,
        subject_public_id: form.subject || null,
      }),
    onSuccess: () => {
      toast.success('Vídeo cadastrado.', {
        description: 'Ele só será sugerido pelo Mestre depois de conferido.',
      })
      setForm({ title: '', url: '', channel: '', subject: '' })
      setOpen(false)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível cadastrar.'),
  })

  const verify = useMutation({
    mutationFn: (publicId: string) => videosApi.verify(publicId),
    onSuccess: () => {
      toast.success('Vídeo conferido — o Mestre já pode sugeri-lo.')
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (publicId: string) => videosApi.remove(publicId),
    onSuccess: () => {
      toast.success('Vídeo removido.')
      invalidate()
    },
  })

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1">
          <CardTitle>Vídeos de apoio</CardTitle>
          <CardDescription>
            A plataforma não descobre vídeos sozinha nem inventa links. O Mestre só sugere o que
            estiver aqui <strong>e conferido por uma pessoa</strong>.
          </CardDescription>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus /> Novo vídeo
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {videos.isLoading && <SkeletonList rows={3} />}

        {videos.data?.items.length === 0 && (
          <EmptyState
            icon={Video}
            title="Nenhum vídeo cadastrado"
            description="Cadastre vídeos por disciplina e confira cada um antes de liberá-lo para o Mestre."
          />
        )}

        <ul className="space-y-2">
          {videos.data?.items.map((video) => (
            <li
              key={video.public_id}
              className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3 text-sm"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{video.title}</span>
                <span className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-subtle">
                  {video.channel && <span>{video.channel}</span>}
                  {video.subject_name && <Badge variant="outline">{video.subject_name}</Badge>}
                  <a
                    href={video.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    abrir <ExternalLink className="size-3" aria-hidden />
                  </a>
                </span>
              </span>

              {video.is_verified ? (
                <Badge variant="success">
                  <CheckCircle2 className="size-3" aria-hidden /> conferido
                </Badge>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  loading={verify.isPending}
                  onClick={() => verify.mutate(video.public_id)}
                >
                  Conferir
                </Button>
              )}
              <button
                type="button"
                aria-label={`Remover ${video.title}`}
                className="text-subtle hover:text-danger"
                onClick={() => remove.mutate(video.public_id)}
              >
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>

        {videos.data && videos.data.pages > 1 && (
          <div className="flex justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= videos.data.pages}
              onClick={() => setPage((value) => value + 1)}
            >
              Próxima
            </Button>
          </div>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo vídeo</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Título" htmlFor="video-title">
              <Input
                id="video-title"
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
              />
            </Field>
            <Field label="URL" htmlFor="video-url">
              <Input
                id="video-url"
                placeholder="https://…"
                value={form.url}
                onChange={(event) => setForm({ ...form, url: event.target.value })}
              />
            </Field>
            <Field label="Canal" htmlFor="video-channel" hint="Opcional">
              <Input
                id="video-channel"
                value={form.channel}
                onChange={(event) => setForm({ ...form, channel: event.target.value })}
              />
            </Field>
            <Field label="Disciplina" htmlFor="video-subject" hint="Opcional">
              <Select
                id="video-subject"
                value={form.subject}
                onChange={(event) => setForm({ ...form, subject: event.target.value })}
              >
                <option value="">Sem disciplina</option>
                {subjects.data?.items.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <p className="text-xs text-muted">
              O vídeo entra desativado para sugestão. Confira o conteúdo e marque como conferido
              para que o Mestre possa recomendá-lo.
            </p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              loading={create.isPending}
              disabled={form.title.trim().length < 3 || form.url.trim().length < 8}
              onClick={() => create.mutate()}
            >
              Cadastrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
