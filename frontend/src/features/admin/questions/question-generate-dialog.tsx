/**
 * Geração de questões inéditas a partir de material conferido.
 *
 * Três coisas esta tela não pode deixar passar:
 *
 * 1. **O que foi descartado aparece, com o motivo.** Mostrar só o que entrou
 *    faria a geração parecer melhor do que foi — e o motivo é o que diz se o
 *    problema está no material ou no modelo.
 * 2. **"Gabarito conferido" não é "gabarito certo".** A citação prova que
 *    existe respaldo no material, não que a leitura dele foi correta. A tela
 *    diz isso, porque é o que justifica a revisão humana obrigatória.
 * 3. **Nada é publicado aqui.** Toda questão nasce rascunho, marcada como
 *    gerada por IA, sem banca e sem ano.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { ApiError } from '@/lib/api/client'
import { adminQuestionsApi } from '@/lib/api/questions'
import type { QuestionGeneration, Subject, Topic } from '@/lib/api/types'

/** Rótulos literais: o motivo não pode chegar à tela como código cru. */
const REASON_LABEL: Record<string, string> = {
  STATEMENT_TOO_SHORT: 'enunciado curto demais',
  ALTERNATIVE_COUNT: 'número de alternativas fora do padrão de prova',
  LETTERS_OUT_OF_ORDER: 'letras fora de ordem',
  ALTERNATIVE_EMPTY: 'alternativa sem texto',
  ALTERNATIVE_REPEATED: 'alternativas repetidas',
  FORBIDDEN_ALTERNATIVE: '“todas”/“nenhuma das anteriores”',
  NO_SINGLE_ANSWER: 'gabarito ausente ou duplo',
  QUOTE_NOT_IN_MATERIAL: 'citação do gabarito não existe no material',
  QUOTE_TOO_SHORT: 'citação curta demais',
  EXPLANATION_MISSING: 'gabarito sem justificativa',
  WRONG_WITHOUT_FEEDBACK: 'alternativa errada sem explicação',
  FABRICATED_PROVENANCE: 'enunciado se apresentando como questão de banca',
  ANSWER_IN_STATEMENT: 'enunciado entregando a resposta',
}

export function QuestionGenerateDialog({
  open,
  onOpenChange,
  subjects,
  topics,
  onSubjectChange,
  onGenerated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjects: Subject[]
  topics: Topic[]
  onSubjectChange: (subjectPublicId: string) => void
  onGenerated: () => void
}) {
  const [material, setMaterial] = useState('')
  const [quantity, setQuantity] = useState(5)
  const [subject, setSubject] = useState('')
  const [topic, setTopic] = useState('')
  const [sourceNote, setSourceNote] = useState('')
  const [result, setResult] = useState<QuestionGeneration | null>(null)

  const run = useMutation({
    mutationFn: () =>
      adminQuestionsApi.generate({
        material,
        quantity,
        subject_public_id: subject || null,
        topic_public_id: topic || null,
        source_note: sourceNote || null,
      }),
    onSuccess: (generation) => {
      setResult(generation)
      onGenerated()
      toast.success(
        `${generation.created.length} questão(ões) em rascunho.` +
          (generation.discarded.length
            ? ` ${generation.discarded.length} descartada(s) na conferência.`
            : ''),
      )
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível gerar.', {
        description:
          error instanceof ApiError && error.code === 'ai_feature_disabled'
            ? 'Configure o modelo de “question.generation” na aba Inteligência.'
            : undefined,
      }),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Gerar questões a partir de um material</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <Alert tone="warning" title="A conferência de origem não diz que o gabarito está certo">
            O que a plataforma confere sozinha é a <strong>forma</strong> e a{' '}
            <strong>citação</strong>: gabarito único, alternativas válidas e um trecho copiado
            literalmente do material sustentando a resposta. Se a leitura desse trecho está
            correta, só uma pessoa julga — por isso toda questão nasce rascunho e precisa da sua
            conferência antes de publicar.
          </Alert>

          <Field
            label="Material"
            htmlFor="qgen-material"
            hint="Cole o texto já conferido (aula publicada, lei, apostila). Mínimo de 200 caracteres."
          >
            <textarea
              id="qgen-material"
              rows={8}
              className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
              value={material}
              onChange={(event) => setMaterial(event.target.value)}
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Quantidade" htmlFor="qgen-quantity">
              <Input
                id="qgen-quantity"
                type="number"
                min={1}
                max={10}
                value={quantity}
                onChange={(event) => setQuantity(Number(event.target.value))}
              />
            </Field>
            <Field label="Procedência do material" htmlFor="qgen-source">
              <Input
                id="qgen-source"
                value={sourceNote}
                placeholder="De onde o texto veio"
                onChange={(event) => setSourceNote(event.target.value)}
              />
            </Field>
            <Field label="Disciplina" htmlFor="qgen-subject">
              <Select
                id="qgen-subject"
                value={subject}
                onChange={(event) => {
                  setSubject(event.target.value)
                  setTopic('')
                  onSubjectChange(event.target.value)
                }}
              >
                <option value="">Sem disciplina</option>
                {subjects.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Tópico" htmlFor="qgen-topic">
              <Select
                id="qgen-topic"
                value={topic}
                disabled={!subject}
                onChange={(event) => setTopic(event.target.value)}
              >
                <option value="">Sem tópico</option>
                {topics.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          {result && (
            <div className="space-y-2 rounded-lg border border-border p-3 text-xs">
              <p className="text-sm font-semibold text-white">
                {result.created.length} em rascunho · {result.discarded.length} descartada(s)
                {result.duplicated > 0 && ` · ${result.duplicated} já existia(m) no banco`}
              </p>
              {result.model && (
                <p className="text-subtle">
                  Modelo {result.model} · prompt {result.prompt_version}
                </p>
              )}
              {result.skipped_reason && (
                <Alert tone="info">{result.skipped_reason}</Alert>
              )}
              {result.created.map((question) => (
                <div key={question.public_id} className="rounded-md border border-border/70 p-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="min-w-0 flex-1 text-white">{question.statement}</p>
                    <span className="flex shrink-0 gap-1">
                      <Badge variant="info">gerada por IA</Badge>
                      <Badge variant="neutral">rascunho</Badge>
                    </span>
                  </div>
                </div>
              ))}
              {result.discarded.length > 0 && (
                <div className="space-y-1">
                  <p className="font-semibold text-warning">
                    Descartadas na conferência de origem
                  </p>
                  {result.discarded.map((item) => (
                    <p key={item.statement} className="text-slate-400">
                      “{item.statement}” — {item.reason}
                    </p>
                  ))}
                  <p className="text-subtle">
                    {Object.entries(result.reasons)
                      .map(([reason, total]) => `${REASON_LABEL[reason] ?? reason}: ${total}`)
                      .join(' · ')}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
          <Button
            loading={run.isPending}
            disabled={material.trim().length < 200}
            onClick={() => run.mutate()}
          >
            Gerar questões
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
