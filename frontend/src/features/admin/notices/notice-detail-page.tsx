import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCheck, RotateCcw, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { noticesApi } from '@/lib/api/notices'
import { noticeAnalysisApi } from '@/lib/api/notice-analysis'
import type { NoticeFact } from '@/lib/api/types'
import { AnalysisProgressPanel } from './analysis-progress'
import { RadiographyPanel } from './radiography-panel'

const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Rascunho',
  QUEUED: 'Na fila',
  PROCESSING: 'Processando',
  AWAITING_CONFIRMATION: 'Aguardando confirmação',
  CONFIRMED: 'Confirmado',
  FAILED: 'Falhou',
}

export function NoticeDetailPage() {
  const { publicId = '' } = useParams()
  const queryClient = useQueryClient()

  const notice = useQuery({
    queryKey: ['admin', 'notices', publicId],
    queryFn: () => noticesApi.get(publicId),
    enabled: Boolean(publicId),
  })

  const analyzed = notice.data?.status !== 'DRAFT'
  const radiography = useQuery({
    queryKey: ['admin', 'notices', publicId, 'radiography'],
    queryFn: () => noticeAnalysisApi.radiography(publicId),
    enabled: Boolean(publicId) && analyzed,
    retry: false,
  })

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'notices'] })
  }, [queryClient])

  const analyze = useMutation({
    mutationFn: () => noticeAnalysisApi.analyze(publicId),
    onSuccess: (result) => {
      toast.success(result.message)
      invalidate()
    },
    onError: (error: unknown) => {
      const message =
        error instanceof ApiError ? error.message : 'Não foi possível analisar o edital.'
      toast.error(message)
      invalidate()
    },
  })

  const confirm = useMutation({
    mutationFn: () => noticeAnalysisApi.confirm(publicId),
    onSuccess: () => {
      toast.success('Edital confirmado. O Raio-X passa a ficar visível para os candidatos.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível confirmar.'),
  })

  const reset = useMutation({
    mutationFn: () => noticeAnalysisApi.reset(publicId),
    onSuccess: () => {
      toast.success('Análise reiniciada.')
      invalidate()
    },
  })

  const reviewFact = useMutation({
    mutationFn: (input: { fact: NoticeFact; value: string }) =>
      noticeAnalysisApi.reviewFact(publicId, input.fact.id, input.value),
    onSuccess: () => {
      toast.success('Campo confirmado.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  if (notice.isLoading) return <SkeletonList rows={4} />
  if (notice.isError)
    return <ErrorState error={notice.error} onRetry={() => notice.refetch()} />
  if (!notice.data) return null

  const data = notice.data
  const hasFile = data.files.length > 0

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/admin">
          <ArrowLeft /> Administração
        </Link>
      </Button>

      <PageHeader
        title={data.title}
        description={`${data.files.length} arquivo(s) · ${STATUS_LABEL[data.status] ?? data.status}`}
        actions={
          <>
            <Button
              loading={analyze.isPending}
              disabled={!hasFile}
              onClick={() => analyze.mutate()}
            >
              <Sparkles /> {data.status === 'DRAFT' ? 'Analisar edital' : 'Reanalisar'}
            </Button>
            {data.status === 'AWAITING_CONFIRMATION' && (
              <Button
                variant="outline"
                loading={confirm.isPending}
                onClick={() => confirm.mutate()}
              >
                <CheckCheck /> Confirmar
              </Button>
            )}
            {data.status !== 'DRAFT' && (
              <Button variant="ghost" loading={reset.isPending} onClick={() => reset.mutate()}>
                <RotateCcw />
              </Button>
            )}
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={data.status === 'CONFIRMED' ? 'success' : 'outline'}>
          {STATUS_LABEL[data.status] ?? data.status}
        </Badge>
        {data.number && <Badge variant="neutral">nº {data.number}</Badge>}
      </div>

      {!hasFile && (
        <Alert tone="warning" title="Envie o PDF antes de analisar">
          A análise trabalha sobre o documento oficial: sem o arquivo não há o que conferir.
        </Alert>
      )}

      {data.status !== 'DRAFT' && (
        <AnalysisProgressPanel publicId={publicId} onFinished={invalidate} />
      )}

      {data.status === 'AWAITING_CONFIRMATION' && (
        <Alert tone="info" title="Revise antes de confirmar">
          Campos marcados como <strong>inferidos</strong> não têm citação conferida no PDF.
          Revise-os para que passem a constar como confirmados por uma pessoa.
        </Alert>
      )}

      {radiography.isLoading && analyzed && <SkeletonList rows={3} />}
      {radiography.data && (
        <RadiographyPanel
          data={radiography.data}
          reviewPending={reviewFact.isPending}
          onReviewFact={(fact, value) => reviewFact.mutate({ fact, value })}
        />
      )}
    </div>
  )
}
