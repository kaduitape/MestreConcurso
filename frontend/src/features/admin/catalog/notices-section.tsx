import { useRef, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileText, Plus, Sparkles, Trash2, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import { noticesApi } from '@/lib/api/notices'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'

const KIND_LABEL: Record<string, string> = {
  MAIN: 'Edital principal',
  RECTIFICATION: 'Retificação',
  ADDENDUM: 'Anexo',
  RESULT: 'Resultado',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function NoticesSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [uploadTarget, setUploadTarget] = useState<string | null>(null)
  const [form, setForm] = useState({
    title: '',
    competition_public_id: '',
    kind: 'MAIN',
    number: '',
  })
  const fileInput = useRef<HTMLInputElement>(null)

  const params = { page, page_size: 20 }
  const notices = useQuery({
    queryKey: queryKeys.adminNotices(params),
    queryFn: () => noticesApi.list(params),
    placeholderData: keepPreviousData,
  })
  const competitions = useQuery({
    queryKey: queryKeys.adminCompetitions({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.competitions({ page: 1, page_size: 100 }),
    enabled: open,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'notices'] })

  const create = useMutation({
    mutationFn: () =>
      noticesApi.create({
        title: form.title,
        competition_public_id: form.competition_public_id || null,
        kind: form.kind as 'MAIN',
        number: form.number || null,
      }),
    onSuccess: () => {
      toast.success('Edital cadastrado. Envie o PDF para concluir.')
      setOpen(false)
      setForm({ title: '', competition_public_id: '', kind: 'MAIN', number: '' })
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  const upload = useMutation({
    mutationFn: (input: { publicId: string; file: File }) =>
      noticesApi.uploadFile(input.publicId, input.file),
    onSuccess: () => {
      toast.success('PDF armazenado com verificação de conteúdo.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Falha no envio.'),
  })

  const removeNotice = useMutation({
    mutationFn: (publicId: string) => noticesApi.remove(publicId),
    onSuccess: () => {
      toast.success('Edital removido.')
      invalidate()
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setOpen(true)}>
          <Plus /> Novo edital
        </Button>
      </div>

      {notices.isLoading && <SkeletonList rows={3} />}
      {notices.isError && (
        <ErrorState error={notices.error} onRetry={() => notices.refetch()} />
      )}

      {notices.data?.items.length === 0 && (
        <EmptyState
          icon={FileText}
          title="Nenhum edital cadastrado"
          description="Cadastre o edital e envie o PDF oficial. A leitura automática do documento entra na Fase 3."
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus /> Cadastrar edital
            </Button>
          }
        />
      )}

      <input
        ref={fileInput}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file && uploadTarget) upload.mutate({ publicId: uploadTarget, file })
          event.target.value = ''
        }}
      />

      <ul className="space-y-3">
        {notices.data?.items.map((notice) => (
          <li key={notice.public_id} className="rounded-lg border border-border bg-surface p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 font-medium">
                  {notice.title}
                  <Badge variant="outline">{KIND_LABEL[notice.kind] ?? notice.kind}</Badge>
                  <Badge variant="neutral">{notice.status}</Badge>
                </p>
                <p className="text-xs text-muted">
                  {notice.number ? `nº ${notice.number} · ` : ''}
                  cadastrado em {new Date(notice.created_at).toLocaleDateString('pt-BR')}
                </p>
              </div>
              <div className="flex gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link to={`/admin/editais/${notice.public_id}`}>
                    <Sparkles /> Analisar
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  loading={upload.isPending && uploadTarget === notice.public_id}
                  onClick={() => {
                    setUploadTarget(notice.public_id)
                    fileInput.current?.click()
                  }}
                >
                  <Upload /> Enviar PDF
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-danger"
                  onClick={() => removeNotice.mutate(notice.public_id)}
                >
                  <Trash2 />
                </Button>
              </div>
            </div>

            {notice.files.length > 0 && (
              <ul className="mt-3 space-y-1">
                {notice.files.map((file) => (
                  <li
                    key={file.public_id}
                    className="flex items-center gap-2 rounded-md bg-surface-muted px-3 py-2 text-sm"
                  >
                    <FileText className="size-4 text-muted" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{file.original_name}</span>
                    <span className="text-xs text-subtle">{formatSize(file.size_bytes)}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        noticesApi.downloadFile(file.public_id, file.original_name)
                      }
                    >
                      <Download />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      {notices.data && notices.data.pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <span>
            {notices.data.total} edital(is) · página {notices.data.page} de {notices.data.pages}
          </span>
          <div className="flex gap-2">
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
              disabled={page >= notices.data.pages}
              onClick={() => setPage((value) => value + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo edital</DialogTitle>
            <DialogDescription>
              Somente PDF, com verificação do conteúdo real do arquivo.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Título" htmlFor="notice-title">
              <Input
                id="notice-title"
                placeholder="Edital nº 1/2026 — Agente de Polícia"
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
              />
            </Field>
            <Field label="Concurso" htmlFor="notice-competition" hint="Opcional">
              <Select
                id="notice-competition"
                value={form.competition_public_id}
                onChange={(event) =>
                  setForm({ ...form, competition_public_id: event.target.value })
                }
              >
                <option value="">sem vínculo</option>
                {competitions.data?.items.map((competition) => (
                  <option key={competition.public_id} value={competition.public_id}>
                    {competition.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Tipo" htmlFor="notice-kind">
                <Select
                  id="notice-kind"
                  value={form.kind}
                  onChange={(event) => setForm({ ...form, kind: event.target.value })}
                >
                  {Object.entries(KIND_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Número" htmlFor="notice-number" hint="Opcional">
                <Input
                  id="notice-number"
                  placeholder="1/2026"
                  value={form.number}
                  onChange={(event) => setForm({ ...form, number: event.target.value })}
                />
              </Field>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              loading={create.isPending}
              disabled={form.title.trim().length < 3}
              onClick={() => create.mutate()}
            >
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
