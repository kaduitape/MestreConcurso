import { useState } from 'react'
import {
  AlertTriangle,
  CalendarClock,
  FileText,
  Layers,
  ListChecks,
  Quote,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Table, TableWrapper, Td, Th, Tr } from '@/components/ui/table'
import type { NoticeFact, Radiography } from '@/lib/api/types'
import { EvidenceBadge } from './evidence'
import { EVIDENCE, formatFactValue } from './evidence-meta'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
}

function formatCurrency(cents: number | null): string {
  if (cents === null || cents === undefined) return '—'
  return (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/**
 * Raio-X: números calculados no servidor, cada campo com o nível de prova e a
 * citação que o sustenta. Quando não há prova, o valor aparece marcado como tal.
 */
export function RadiographyPanel({
  data,
  onReviewFact,
  reviewPending,
}: {
  data: Radiography
  onReviewFact?: (fact: NoticeFact, value: string) => void
  reviewPending?: boolean
}) {
  const [reviewing, setReviewing] = useState<NoticeFact | null>(null)
  const [draft, setDraft] = useState('')

  const cards = [
    {
      label: 'Dias até a prova',
      value:
        data.days_until_exam === null
          ? '—'
          : data.days_until_exam >= 0
            ? String(data.days_until_exam)
            : 'prova realizada',
      icon: CalendarClock,
    },
    { label: 'Disciplinas', value: String(data.subjects_count), icon: Layers },
    { label: 'Assuntos', value: String(data.topics_count), icon: ListChecks },
    { label: 'Questões', value: data.questions_count?.toString() ?? '—', icon: ListChecks },
    { label: 'Vagas', value: data.vacancies?.toLocaleString('pt-BR') ?? '—', icon: Users },
    { label: 'Salário', value: formatCurrency(data.salary_cents), icon: FileText },
    { label: 'Páginas do PDF', value: data.page_count?.toString() ?? '—', icon: FileText },
    { label: 'Data da prova', value: formatDate(data.exam_date), icon: CalendarClock },
  ]

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <Card key={card.label}>
            <CardContent className="p-4">
              <p className="flex items-center gap-1.5 text-xs tracking-wide text-subtle uppercase">
                <card.icon className="size-3.5" aria-hidden /> {card.label}
              </p>
              <p className="mt-1 text-xl font-semibold tabular-nums">{card.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {data.attention_points.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-warning" aria-hidden /> Pontos de atenção
            </CardTitle>
            <CardDescription>
              Derivados do que foi (ou não foi) encontrado no documento.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.attention_points.map((point) => (
                <li key={point.kind} className="rounded-md bg-surface-muted p-3 text-sm">
                  <p className="font-medium">{point.title}</p>
                  <p className="text-muted">{point.detail}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Campos extraídos</CardTitle>
          <CardDescription>
            {EVIDENCE.OFFICIAL.label}: citação conferida no PDF · {EVIDENCE.INFERRED.label}:
            precisa de conferência humana antes de virar verdade.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TableWrapper>
            <Table>
              <thead>
                <tr>
                  <Th>Campo</Th>
                  <Th>Valor</Th>
                  <Th>Prova</Th>
                  <Th>Origem</Th>
                  {onReviewFact && <Th />}
                </tr>
              </thead>
              <tbody>
                {data.facts.map((fact) => (
                  <Tr key={fact.id}>
                    <Td className="font-medium">{fact.label}</Td>
                    <Td>{formatFactValue(fact.value, fact.field_path)}</Td>
                    <Td>
                      <div className="flex flex-col gap-1">
                        <EvidenceBadge level={fact.evidence_level} />
                        {fact.page_number && (
                          <span className="text-xs text-subtle">página {fact.page_number}</span>
                        )}
                      </div>
                    </Td>
                    <Td className="max-w-md">
                      {fact.quote ? (
                        <p className="flex gap-1.5 text-xs text-muted italic">
                          <Quote className="mt-0.5 size-3 shrink-0" aria-hidden />
                          <span className="line-clamp-2">{fact.quote}</span>
                        </p>
                      ) : (
                        <span className="text-xs text-subtle">sem citação</span>
                      )}
                      {fact.model_slug && (
                        <span className="mt-1 block text-[11px] text-subtle">
                          {fact.extracted_by === 'HUMAN'
                            ? 'revisado por uma pessoa'
                            : `${fact.model_slug} · prompt ${fact.prompt_version}`}
                        </span>
                      )}
                    </Td>
                    {onReviewFact && (
                      <Td className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setReviewing(fact)
                            setDraft(
                              fact.value === null || fact.value === undefined
                                ? ''
                                : String(fact.value),
                            )
                          }}
                        >
                          Revisar
                        </Button>
                      </Td>
                    )}
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrapper>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Disciplinas e conteúdo programático</CardTitle>
            <CardDescription>
              Ordenadas pelo que apareceu no edital. O peso só aparece quando o documento
              informa.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.subjects.length === 0 && (
              <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                Nenhuma disciplina extraída.
              </p>
            )}
            <ul className="space-y-3">
              {data.subjects.map((subject) => (
                <li key={subject.public_id} className="rounded-md border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{subject.name}</p>
                    <EvidenceBadge level={subject.evidence_level} />
                    {subject.weight !== null && (
                      <Badge variant="outline">peso {subject.weight}</Badge>
                    )}
                    {subject.questions_count !== null && (
                      <Badge variant="neutral">{subject.questions_count} questões</Badge>
                    )}
                  </div>
                  {subject.topics.length > 0 ? (
                    <ul className="mt-2 space-y-0.5 text-sm text-muted">
                      {subject.topics.slice(0, 8).map((topic) => (
                        <li key={topic}>• {topic}</li>
                      ))}
                      {subject.topics.length > 8 && (
                        <li className="text-xs text-subtle">
                          e mais {subject.topics.length - 8} assunto(s)
                        </li>
                      )}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-warning">
                      Conteúdo programático não extraído para esta disciplina.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Datas do edital</CardTitle>
            <CardDescription>
              Só entram datas legíveis no documento — nenhuma é deduzida.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.events.length === 0 && (
              <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                Nenhuma data extraída.
              </p>
            )}
            <ul className="space-y-2">
              {data.events.map((event) => (
                <li
                  key={`${event.kind}-${event.title}`}
                  className="flex items-start justify-between gap-3 rounded-md bg-surface-muted p-3"
                >
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                      {event.title}
                      {event.is_critical && <Badge variant="warning">crítica</Badge>}
                    </p>
                    <p className="text-xs text-muted">
                      {formatDate(event.date_start)}
                      {event.days_until !== null &&
                        event.days_until >= 0 &&
                        ` · em ${event.days_until} dias`}
                    </p>
                  </div>
                  <EvidenceBadge level={event.evidence_level} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Dialog open={Boolean(reviewing)} onOpenChange={(open) => !open && setReviewing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revisar “{reviewing?.label}”</DialogTitle>
            <DialogDescription>
              Ao salvar, o campo passa a constar como confirmado por uma pessoa e deixa de ser
              sobrescrito por novas análises.
            </DialogDescription>
          </DialogHeader>

          {reviewing?.quote && (
            <p className="mb-3 rounded-md bg-surface-muted p-3 text-xs text-muted italic">
              “{reviewing.quote}”{reviewing.page_number && ` — página ${reviewing.page_number}`}
            </p>
          )}

          <Field label="Valor correto" htmlFor="fact-value">
            <Input
              id="fact-value"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
          </Field>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setReviewing(null)}>
              Cancelar
            </Button>
            <Button
              loading={reviewPending}
              onClick={() => {
                if (reviewing && onReviewFact) onReviewFact(reviewing, draft)
                setReviewing(null)
              }}
            >
              Confirmar valor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
