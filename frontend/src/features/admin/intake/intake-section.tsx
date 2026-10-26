/**
 * Cadastrar um concurso: subindo o PDF do edital ou colando o endereço dele.
 *
 * O cadastro acontece sozinho. A obrigação desta tela é que **"cadastrado"
 * nunca seja lido como "completo"** — porque o automático preenche só o que o
 * edital sustenta por citação conferida, e o que ele não sustenta fica em
 * branco. Daí as cinco regras daqui:
 *
 * 1. **As duas contas aparecem juntas.** Quantos campos entraram com citação
 *    conferida, e o que ficou faltando — item por item, com o motivo.
 * 2. **Cada campo mostra de onde veio.** Nível de evidência, citação literal e
 *    página. Campo sem citação conferida aparece **em branco**, com o aviso de
 *    que alguém precisa digitar — nunca preenchido com o que a IA deduziu.
 * 3. **O automático parando é resultado, não erro.** Nome não conferido, ano
 *    sem data de origem, possível duplicata: a tela diz o motivo e devolve o
 *    formulário de revisão, inteiro.
 * 4. **Recusar escolher o PDF também é resultado.** Quando dois documentos
 *    empatam, os candidatos aparecem com a pontuação e o motivo de cada um.
 * 5. **Descartar exige motivo.**
 */
import { useRef, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CircleAlert,
  FileSearch,
  FileUp,
  Link2,
  ListChecks,
  PencilLine,
  Scale,
  ThumbsDown,
  TriangleAlert,
  Wand2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { ApiError } from '@/lib/api/client'
import { intakeApi } from '@/lib/api/intake'
import { queryKeys } from '@/lib/query-client'
import { EvidenceBadge } from '../notices/evidence'
import { formatFactValue } from '../notices/evidence-meta'
import type { CompetitionIntake, IntakeField, IntakeGap, IntakeStatus } from '@/lib/api/types'

/**
 * Classes literais: o Tailwind 4 só emite a cor que vê escrita no código.
 */
const STATUS: Record<
  IntakeStatus,
  { label: string; variant: 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info' }
> = {
  FETCHING: { label: 'buscando o endereço', variant: 'info' },
  AWAITING_CHOICE: { label: 'esperando que alguém aponte o PDF', variant: 'warning' },
  ANALYZING: { label: 'analisando o edital', variant: 'info' },
  AWAITING_REVIEW: { label: 'ficha pronta, esperando revisão', variant: 'primary' },
  APPLIED: { label: 'cadastrado', variant: 'success' },
  REJECTED: { label: 'descartado', variant: 'neutral' },
  FAILED: { label: 'falhou', variant: 'danger' },
}

/** Os campos do formulário de aplicação, na ordem em que a ficha os mostra. */
const TARGET_LABEL: Record<string, string> = {
  education_level: 'Escolaridade',
  vacancies_total: 'Vagas',
  salary_max_cents: 'Salário (em centavos)',
  registration_start: 'Início das inscrições (AAAA-MM-DD)',
  registration_end: 'Fim das inscrições (AAAA-MM-DD)',
  exam_date: 'Data da prova (AAAA-MM-DD)',
}

/**
 * Os campos do cargo. Sem `name`, nenhum cargo é criado — e a grade de
 * disciplinas, que mora no cargo, também não. A grade em si não é digitada:
 * ela sai das disciplinas do edital que casam por nome idêntico com o
 * catálogo, e o que não casa aparece na lista de lacunas.
 */
const POSITION_LABEL: Record<string, string> = {
  name: 'Cargo',
  education_level: 'Escolaridade do cargo',
  vacancies: 'Vagas do cargo',
  salary_cents: 'Salário do cargo (em centavos)',
  questions_count: 'Questões da prova',
  exam_duration_minutes: 'Duração da prova (minutos)',
}

function nomeDoArquivo(url: string): string {
  return url.split('/').pop() || url
}

function FieldRow({ field }: { field: IntakeField }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">{field.label}</p>
          <p className="text-[0.68rem] text-subtle">{field.field_path}</p>
        </div>
        <EvidenceBadge level={field.evidence_level} />
      </div>

      <p className="mt-2 text-sm text-foreground">
        {field.applicable ? (
          formatFactValue(field.value, field.field_path)
        ) : (
          <span className="inline-flex items-center gap-1 text-warning">
            <PencilLine className="size-3.5" aria-hidden />
            em branco — alguém precisa digitar
          </span>
        )}
      </p>

      {field.quote && (
        <blockquote className="mt-2 border-l-2 border-border-strong pl-2 text-xs text-muted italic">
          “{field.quote}”
          {field.page_number !== null && (
            <span className="not-italic"> — página {field.page_number}</span>
          )}
        </blockquote>
      )}
      {!field.applicable && !field.quote && (
        <p className="mt-2 text-xs text-subtle">
          A citação não foi localizada no PDF, então o valor não é aplicado sozinho.
        </p>
      )}
      {field.target === null && field.position_target === null && (
        <p className="mt-2 text-[0.68rem] text-subtle">
          Fica guardado no edital; não entra na ficha do concurso.
        </p>
      )}
      {field.target === null && field.position_target !== null && (
        <p className="mt-2 text-[0.68rem] text-subtle">Entra na ficha do cargo.</p>
      )}
    </div>
  )
}

/**
 * O que o cadastro automático não preencheu.
 *
 * Este bloco é o que impede a tela de mentir por omissão: sem ele, "cadastrado"
 * passaria a ideia de ficha completa, e alguém publicaria um concurso sem banca
 * e sem grade achando que estava pronto.
 */
function GapList({ gaps }: { gaps: IntakeGap[] }) {
  if (gaps.length === 0) return null
  return (
    <div className="rounded-lg border border-warning-soft bg-warning-soft/30 p-3">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-warning">
        <TriangleAlert className="size-4" aria-hidden />
        {gaps.length === 1
          ? '1 coisa ficou faltando'
          : `${gaps.length} coisas ficaram faltando`}
      </p>
      <ul className="mt-2 space-y-1.5">
        {gaps.map((gap, index) => (
          <li key={`${gap.code}-${index}`} className="text-sm text-foreground">
            {gap.label}
            {gap.detail && <span className="block text-xs text-muted">{gap.detail}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

function CandidateList({ intake }: { intake: CompetitionIntake }) {
  const queryClient = useQueryClient()
  const escolher = useMutation({
    mutationFn: (url: string) => intakeApi.choose(intake.public_id, url, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'intakes'] })
      toast.success('PDF apontado. A análise do edital começou.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível analisar.'),
  })

  return (
    <div className="space-y-2">
      {intake.candidates.map((candidate) => (
        <div
          key={candidate.url}
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-2.5"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-foreground">
              {candidate.text || nomeDoArquivo(candidate.url)}
            </p>
            <p className="truncate text-[0.68rem] text-subtle">{candidate.explanation}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="outline">
              <Scale className="size-3" aria-hidden /> {candidate.score}
            </Badge>
            {intake.status === 'AWAITING_CHOICE' && (
              <Button
                size="sm"
                variant="secondary"
                disabled={escolher.isPending}
                onClick={() => escolher.mutate(candidate.url)}
              >
                É este
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function ApplyForm({ intake }: { intake: CompetitionIntake }) {
  const queryClient = useQueryClient()
  const campos = intake.proposal.fields
  const porCaminho = new Map(campos.map((item) => [item.field_path, item]))

  const valorInicial = (path: string): string => {
    const campo = porCaminho.get(path)
    if (!campo || !campo.applicable || campo.value === null || campo.value === undefined)
      return ''
    return String(campo.value)
  }

  const orgaoAchado = intake.matches.organization ?? null
  const bancaAchada = intake.matches.exam_board ?? null

  const [nome, setNome] = useState(valorInicial('competition.name'))
  const [ano, setAno] = useState(String(new Date().getFullYear()))
  const [orgaoNome, setOrgaoNome] = useState(
    orgaoAchado ? '' : valorInicial('organization.name'),
  )
  const [orgaoSigla, setOrgaoSigla] = useState('')
  const [extras, setExtras] = useState<Record<string, string>>(() => {
    const inicial: Record<string, string> = {}
    for (const campo of campos) {
      if (campo.target && campo.target in TARGET_LABEL) {
        inicial[campo.target] = valorInicial(campo.field_path)
      }
    }
    return inicial
  })
  const [cargo, setCargo] = useState<Record<string, string>>(() => {
    const inicial: Record<string, string> = {}
    for (const campo of campos) {
      if (campo.position_target && campo.position_target in POSITION_LABEL) {
        inicial[campo.position_target] = valorInicial(campo.field_path)
      }
    }
    return inicial
  })
  const [motivo, setMotivo] = useState('')
  const [descartando, setDescartando] = useState(false)

  const aplicar = useMutation({
    mutationFn: () =>
      intakeApi.apply(intake.public_id, {
        name: nome,
        year: Number(ano),
        organization_public_id: orgaoAchado?.public_id ?? null,
        organization_name: orgaoAchado ? null : orgaoNome,
        organization_short_name: orgaoAchado ? null : orgaoSigla,
        exam_board_public_id: bancaAchada?.public_id ?? null,
        fields: Object.fromEntries(
          Object.entries(extras).filter(([, valor]) => valor.trim() !== ''),
        ),
        position: Object.fromEntries(
          Object.entries(cargo).filter(([, valor]) => valor.trim() !== ''),
        ),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'intakes'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
      toast.success('Concurso cadastrado. Ele entra como rascunho, não publicado.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível cadastrar.'),
  })

  const descartar = useMutation({
    mutationFn: () => intakeApi.reject(intake.public_id, motivo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'intakes'] })
      toast.success('Proposta descartada.')
      setDescartando(false)
      setMotivo('')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível descartar.'),
  })

  const parecidos = intake.matches.competitions ?? []

  return (
    <div className="space-y-3">
      {parecidos.length > 0 && (
        <Alert tone="warning" title="Já existe concurso com nome parecido">
          <ul className="list-disc pl-4">
            {parecidos.map((item) => (
              <li key={item.public_id}>
                {item.name} ({item.year})
              </li>
            ))}
          </ul>
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nome do concurso" htmlFor={`nome-${intake.public_id}`}>
          <Input
            id={`nome-${intake.public_id}`}
            value={nome}
            onChange={(event) => setNome(event.target.value)}
          />
        </Field>
        <Field label="Ano" htmlFor={`ano-${intake.public_id}`}>
          <Input
            id={`ano-${intake.public_id}`}
            value={ano}
            inputMode="numeric"
            onChange={(event) => setAno(event.target.value)}
          />
        </Field>

        {orgaoAchado ? (
          <div className="sm:col-span-2">
            <Alert tone="info" title="Órgão reaproveitado do catálogo">
              {orgaoAchado.name}
            </Alert>
          </div>
        ) : (
          <>
            <Field label="Órgão (nome)" htmlFor={`orgao-${intake.public_id}`}>
              <Input
                id={`orgao-${intake.public_id}`}
                value={orgaoNome}
                onChange={(event) => setOrgaoNome(event.target.value)}
              />
            </Field>
            <Field label="Órgão (sigla)" htmlFor={`sigla-${intake.public_id}`}>
              <Input
                id={`sigla-${intake.public_id}`}
                value={orgaoSigla}
                onChange={(event) => setOrgaoSigla(event.target.value)}
              />
            </Field>
          </>
        )}

        {Object.entries(TARGET_LABEL).map(([target, label]) => (
          <Field key={target} label={label} htmlFor={`${target}-${intake.public_id}`}>
            <Input
              id={`${target}-${intake.public_id}`}
              value={extras[target] ?? ''}
              onChange={(event) =>
                setExtras((atual) => ({ ...atual, [target]: event.target.value }))
              }
            />
          </Field>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(POSITION_LABEL).map(([target, label]) => (
          <Field key={target} label={label} htmlFor={`cargo-${target}-${intake.public_id}`}>
            <Input
              id={`cargo-${target}-${intake.public_id}`}
              value={cargo[target] ?? ''}
              onChange={(event) =>
                setCargo((atual) => ({ ...atual, [target]: event.target.value }))
              }
            />
          </Field>
        ))}
      </div>
      <p className="text-xs text-subtle">
        Este formulário cadastra <strong>um</strong> cargo — o que você conferiu. Edital com
        vários cargos cadastra todos pelo caminho automático; os outros ficam na ficha do edital
        e podem ser cadastrados em Concursos. Sem nome de cargo, nenhum cargo é criado — e sem
        cargo não há grade de disciplinas. A grade não é digitada aqui: ela sai das disciplinas
        do edital que têm nome idêntico a uma disciplina do catálogo.
      </p>

      {bancaAchada && (
        <p className="text-xs text-muted">
          Banca reaproveitada do catálogo: <strong>{bancaAchada.name}</strong>
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => aplicar.mutate()} disabled={aplicar.isPending}>
          <ListChecks /> Cadastrar concurso
        </Button>
        <Button variant="ghost" onClick={() => setDescartando((atual) => !atual)}>
          <ThumbsDown /> Descartar
        </Button>
      </div>

      {descartando && (
        <div className="flex flex-wrap items-end gap-2">
          <Field
            label="Por que descartar?"
            htmlFor={`motivo-${intake.public_id}`}
            className="min-w-56 flex-1"
          >
            <Input
              id={`motivo-${intake.public_id}`}
              value={motivo}
              onChange={(event) => setMotivo(event.target.value)}
            />
          </Field>
          <Button
            variant="danger"
            disabled={motivo.trim().length < 3 || descartar.isPending}
            onClick={() => descartar.mutate()}
          >
            Confirmar descarte
          </Button>
        </div>
      )}
    </div>
  )
}

function IntakeCard({ intake }: { intake: CompetitionIntake }) {
  const estado = STATUS[intake.status]
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <CardTitle className="truncate text-base">
              {intake.source_url ?? intake.source_name ?? 'edital enviado'}
            </CardTitle>
            <CardDescription>
              {intake.source_kind === 'UPLOAD' ? (
                <span className="inline-flex items-center gap-1">
                  <FileUp className="size-3.5" aria-hidden />
                  {intake.choice_reason ?? 'arquivo enviado'}
                </span>
              ) : intake.chosen_url ? (
                <span className="inline-flex items-center gap-1">
                  <Link2 className="size-3.5" aria-hidden />
                  {nomeDoArquivo(intake.chosen_url)}
                  {intake.choice_reason && ` — ${intake.choice_reason}`}
                </span>
              ) : (
                'nenhum PDF escolhido ainda'
              )}
            </CardDescription>
          </div>
          <Badge variant={estado.variant}>{estado.label}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {intake.status === 'FAILED' && intake.detail && (
          <Alert tone="danger" title="Não deu para seguir">
            {intake.detail}
          </Alert>
        )}

        {intake.status === 'AWAITING_CHOICE' && (
          <Alert tone="warning" title="O serviço não escolheu o PDF">
            {intake.detail ?? 'Mais de um documento é plausível como edital de abertura.'}{' '}
            Analisar o documento errado cadastraria o concurso a partir dele, então a escolha
            fica com você.
          </Alert>
        )}

        {intake.candidates.length > 0 && <CandidateList intake={intake} />}

        {intake.status === 'AWAITING_REVIEW' && intake.detail && (
          <Alert tone="info" title="O cadastro automático parou aqui">
            {intake.detail}. A ficha está montada abaixo — confira e cadastre.
          </Alert>
        )}

        {intake.status === 'AWAITING_REVIEW' && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <Badge variant="success">
                {intake.proposal.applicable} com citação conferida
              </Badge>
              {intake.proposal.needs_typing > 0 && (
                <Badge variant="warning">
                  {intake.proposal.needs_typing} esperando que alguém digite
                </Badge>
              )}
              {intake.notice_public_id && (
                <span>edital {intake.notice_public_id} guardado com o PDF</span>
              )}
            </div>

            <div className="space-y-2">
              {intake.proposal.fields.map((field) => (
                <FieldRow key={field.field_path} field={field} />
              ))}
            </div>

            <ApplyForm intake={intake} />
          </>
        )}

        {intake.status === 'APPLIED' && intake.competition_public_id && (
          <>
            <Alert
              tone={intake.gaps.length > 0 ? 'warning' : 'success'}
              title={
                intake.gaps.length > 0
                  ? 'Concurso cadastrado, com partes em branco'
                  : 'Concurso cadastrado'
              }
            >
              {intake.auto_applied
                ? 'Saiu do edital sozinho: só os campos com citação conferida foram preenchidos.'
                : 'Cadastrado com os valores revisados.'}{' '}
              Entrou como rascunho, não publicado — a ficha ainda passa pela esteira editorial.
            </Alert>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <Badge variant="success">
                {intake.proposal.applicable} campos com citação conferida
              </Badge>
              {intake.auto_applied && (
                <Badge variant="info">
                  <Wand2 className="size-3" aria-hidden /> cadastrado automaticamente
                </Badge>
              )}
            </div>
            <GapList gaps={intake.gaps} />
            <div className="space-y-2">
              {intake.proposal.fields.map((field) => (
                <FieldRow key={field.field_path} field={field} />
              ))}
            </div>
          </>
        )}

        {intake.status === 'REJECTED' && intake.detail && (
          <p className="text-sm text-muted">Descartado: {intake.detail}</p>
        )}
      </CardContent>
    </Card>
  )
}

export function IntakeSection() {
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [automatico, setAutomatico] = useState(true)
  const arquivo = useRef<HTMLInputElement>(null)
  const params = { page: 1, page_size: 20 }

  const intakes = useQuery({
    queryKey: queryKeys.adminIntakes(params),
    queryFn: () => intakeApi.list(params),
    placeholderData: keepPreviousData,
  })

  /** O mesmo aviso nas duas entradas: o resultado é o mesmo nas duas. */
  const avisar = (criado: CompetitionIntake) => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'intakes'] })
    queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
    if (criado.status === 'FAILED') {
      toast.error(criado.detail ?? 'Não deu para ler o edital.')
    } else if (criado.status === 'AWAITING_CHOICE') {
      toast.warning('Mais de um PDF é plausível: aponte qual é o edital.')
    } else if (criado.status === 'APPLIED') {
      toast.success(
        criado.gaps.length > 0
          ? `Concurso cadastrado — ${criado.gaps.length} ponto(s) ficaram em branco.`
          : 'Concurso cadastrado com tudo que o edital sustenta.',
      )
    } else {
      toast.success('Ficha montada. Confira campo por campo antes de cadastrar.')
    }
  }

  const iniciar = useMutation({
    mutationFn: () => intakeApi.start(url, automatico),
    onSuccess: (criado) => {
      setUrl('')
      avisar(criado)
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível buscar.'),
  })

  const subir = useMutation({
    mutationFn: (file: File) => intakeApi.upload(file, automatico),
    onSuccess: avisar,
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível ler o arquivo.',
      ),
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cadastrar concurso a partir do edital</CardTitle>
          <CardDescription>
            Suba o PDF do edital, ou cole o endereço da página do concurso. O serviço lê o
            documento, confere cada dado contra a citação que o sustenta e cadastra o concurso,
            o cargo e a grade de disciplinas. O que o edital não sustentar fica em branco e
            aparece nomeado — cadastrado não quer dizer completo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button disabled={subir.isPending} onClick={() => arquivo.current?.click()}>
              <FileUp /> {subir.isPending ? 'Lendo o edital…' : 'Subir o PDF do edital'}
            </Button>
            <input
              ref={arquivo}
              type="file"
              accept="application/pdf"
              className="hidden"
              aria-label="Arquivo PDF do edital"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) subir.mutate(file)
                event.target.value = ''
              }}
            />
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <Field
              label="…ou o endereço da página do concurso"
              htmlFor="intake-url"
              className="min-w-64 flex-1"
            >
              <Input
                id="intake-url"
                placeholder="https://orgao.gov.br/concursos/agente"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
            </Field>
            <Button
              variant="secondary"
              disabled={url.trim().length < 10 || iniciar.isPending}
              onClick={() => iniciar.mutate()}
            >
              <FileSearch /> {iniciar.isPending ? 'Lendo o edital…' : 'Ler o endereço'}
            </Button>
          </div>

          <label className="flex items-start gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-primary"
              checked={automatico}
              onChange={(event) => setAutomatico(event.target.checked)}
            />
            <span>
              Cadastrar automaticamente o que o edital sustentar
              <span className="block text-xs text-subtle">
                Desligado, o serviço monta a ficha e espera a sua revisão — é o caminho de quem
                quer conferir antes de o concurso existir no catálogo.
              </span>
            </span>
          </label>

          <p className="flex items-start gap-1.5 text-xs text-subtle">
            <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Ler um edital inteiro leva algum tempo e consome o orçamento de IA. O PDF é tratado
            como documento não confiável: nada dentro dele é obedecido como instrução.
          </p>
        </CardContent>
      </Card>

      {intakes.isLoading && <SkeletonList rows={2} />}
      {intakes.isError && (
        <ErrorState error={intakes.error} onRetry={() => intakes.refetch()} />
      )}

      {intakes.data?.items.length === 0 && (
        <EmptyState
          icon={FileSearch}
          title="Nenhum edital lido ainda"
          description="Suba o PDF de um edital, ou cole o endereço da página do concurso."
        />
      )}

      <div className="space-y-4">
        {intakes.data?.items.map((intake) => (
          <IntakeCard key={intake.public_id} intake={intake} />
        ))}
      </div>
    </div>
  )
}
