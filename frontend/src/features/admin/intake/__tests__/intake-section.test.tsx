/**
 * A tela tem quatro obrigações acima das outras: **"cadastrado" não pode
 * parecer "completo"**, **campo sem citação conferida chega em branco**,
 * **recusar escolher o PDF é resultado e não erro**, e **descartar exige
 * motivo**.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompetitionIntake, IntakeField } from '@/lib/api/types'

const { intakeApi } = vi.hoisted(() => ({
  intakeApi: {
    list: vi.fn(),
    start: vi.fn(),
    upload: vi.fn(),
    get: vi.fn(),
    choose: vi.fn(),
    apply: vi.fn(),
    reject: vi.fn(),
  },
}))
vi.mock('@/lib/api/intake', () => ({ intakeApi }))

const { adminCatalogApi } = vi.hoisted(() => ({
  adminCatalogApi: { competitionSchedule: vi.fn() },
}))
vi.mock('@/lib/api/catalog', () => ({ adminCatalogApi }))

const { IntakeSection } = await import('../intake-section')

function campo(overrides: Partial<IntakeField> = {}): IntakeField {
  return {
    field_path: 'position.salary_cents',
    label: 'Remuneração inicial',
    value: 815700,
    evidence_level: 'OFFICIAL',
    quote: 'A remuneração inicial do cargo é de R$ 8.157,00.',
    page_number: 1,
    target: 'salary_max_cents',
    position_target: 'salary_cents',
    applicable: true,
    ...overrides,
  }
}

function intake(overrides: Partial<CompetitionIntake> = {}): CompetitionIntake {
  return {
    public_id: 'I1',
    source_kind: 'URL',
    source_url: 'https://orgao.gov.br/concursos/agente',
    source_name: null,
    status: 'AWAITING_REVIEW',
    chosen_url: 'https://orgao.gov.br/arquivos/edital-de-abertura-01-2026.pdf',
    choice_reason: "+5: o link diz 'edital de abertura'",
    detail: null,
    candidates: [
      {
        url: 'https://orgao.gov.br/arquivos/edital-de-abertura-01-2026.pdf',
        text: 'Edital de Abertura nº 1/2026',
        score: 5,
        explanation: "+5: o link diz 'edital de abertura'",
      },
      {
        url: 'https://orgao.gov.br/arquivos/anexo-ii.pdf',
        text: 'Anexo II',
        score: -3,
        explanation: '-3: é anexo',
      },
    ],
    proposal: {
      fields: [
        campo(),
        campo({
          field_path: 'exam.min_score_rule',
          label: 'Nota mínima',
          value: 'Acerto de 50% em cada disciplina',
          evidence_level: 'INFERRED',
          quote: null,
          page_number: null,
          target: null,
          position_target: null,
          applicable: false,
        }),
      ],
      applicable: 1,
      needs_typing: 1,
    },
    matches: {},
    auto_applied: false,
    gaps: [],
    notice_public_id: 'N1',
    competition_public_id: null,
    applied_at: null,
    created_at: '2026-10-24T10:00:00Z',
    ...overrides,
  }
}

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <IntakeSection />
    </QueryClientProvider>,
  )
}

function page(items: CompetitionIntake[]) {
  return { items, total: items.length, page: 1, page_size: 20, pages: 1 }
}

describe('IntakeSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    intakeApi.list.mockResolvedValue(page([intake()]))
    intakeApi.start.mockResolvedValue(intake())
    intakeApi.upload.mockResolvedValue(intake())
    intakeApi.choose.mockResolvedValue(intake())
    intakeApi.reject.mockResolvedValue(intake({ status: 'REJECTED' }))
    adminCatalogApi.competitionSchedule.mockResolvedValue([])
  })

  it('diz que cadastrado não quer dizer completo', async () => {
    renderSection()
    expect(await screen.findByText(/cadastrado não quer dizer completo/)).toBeInTheDocument()
    expect(screen.getByText(/documento não confiável/)).toBeInTheDocument()
  })

  it('mostra o valor com a citação e a página quando a evidência é oficial', async () => {
    renderSection()
    expect(await screen.findByText('Remuneração inicial')).toBeInTheDocument()
    expect(screen.getByText('R$ 8.157,00')).toBeInTheDocument()
    expect(screen.getByText(/A remuneração inicial do cargo/)).toBeInTheDocument()
    expect(screen.getByText(/página 1/)).toBeInTheDocument()
    expect(screen.getByText('Oficial')).toBeInTheDocument()
  })

  it('deixa em branco — e diz isso — o campo que a IA só deduziu', async () => {
    renderSection()
    await screen.findByText('Nota mínima')

    // O valor inferido NÃO aparece como se fosse dado do edital.
    expect(screen.queryByText('Acerto de 50% em cada disciplina')).not.toBeInTheDocument()
    expect(screen.getByText(/alguém precisa digitar/)).toBeInTheDocument()
    expect(screen.getByText('Inferido')).toBeInTheDocument()
    expect(screen.getByText(/1 esperando que alguém digite/)).toBeInTheDocument()
  })

  it('não oferece botão de escolher PDF quando a escolha já foi feita', async () => {
    renderSection()
    await screen.findByText('Anexo II')
    expect(screen.queryByRole('button', { name: 'É este' })).not.toBeInTheDocument()
  })

  it('quando o serviço recusa escolher, lista os candidatos e pede que alguém aponte', async () => {
    intakeApi.list.mockResolvedValue(
      page([
        intake({
          status: 'AWAITING_CHOICE',
          chosen_url: null,
          notice_public_id: null,
          detail:
            'dois ou mais PDFs são igualmente plausíveis como edital — aponte qual é o certo',
        }),
      ]),
    )
    renderSection()

    expect(await screen.findByText(/O serviço não escolheu o PDF/)).toBeInTheDocument()
    expect(screen.getByText(/aponte qual é o certo/)).toBeInTheDocument()
    expect(screen.getByText('-3: é anexo')).toBeInTheDocument()

    const botoes = screen.getAllByRole('button', { name: 'É este' })
    expect(botoes).toHaveLength(2)
    await userEvent.click(botoes[0])
    expect(intakeApi.choose).toHaveBeenCalledWith(
      'I1',
      'https://orgao.gov.br/arquivos/edital-de-abertura-01-2026.pdf',
      true,
    )
  })

  it('não deixa descartar sem motivo escrito', async () => {
    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Descartar/ }))

    const confirmar = screen.getByRole('button', { name: /Confirmar descarte/ })
    expect(confirmar).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Por que descartar?'), 'é do ano passado')
    expect(confirmar).toBeEnabled()
    await userEvent.click(confirmar)
    expect(intakeApi.reject).toHaveBeenCalledWith('I1', 'é do ano passado')
  })

  it('aplica apenas os valores que estão no formulário, sem o que ficou em branco', async () => {
    intakeApi.apply.mockResolvedValue({ public_id: 'C1' })
    renderSection()

    await userEvent.type(await screen.findByLabelText('Órgão (sigla)'), 'PCDF')
    await userEvent.click(screen.getByRole('button', { name: /Cadastrar concurso/ }))

    expect(intakeApi.apply).toHaveBeenCalledTimes(1)
    const [, payload] = intakeApi.apply.mock.calls[0]
    expect(payload.fields).toEqual({ salary_max_cents: '815700' })
    // O cargo vai no mesmo pedido: é ele que carrega a grade de disciplinas.
    expect(payload.position).toEqual({ salary_cents: '815700' })
    expect(payload.organization_short_name).toBe('PCDF')
  })

  it('avisa quando já existe concurso parecido no catálogo', async () => {
    intakeApi.list.mockResolvedValue(
      page([
        intake({
          matches: {
            organization: { public_id: 'O1', name: 'Polícia Civil do Distrito Federal' },
            competitions: [{ public_id: 'C9', name: 'Concurso PCDF Agente', year: 2026 }],
          },
        }),
      ]),
    )
    renderSection()

    expect(await screen.findByText(/Já existe concurso com nome parecido/)).toBeInTheDocument()
    expect(screen.getByText('Concurso PCDF Agente (2026)')).toBeInTheDocument()
    // Órgão reaproveitado: a tela não pede nome e sigla de novo.
    expect(screen.getByText(/Órgão reaproveitado do catálogo/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Órgão (sigla)')).not.toBeInTheDocument()
  })
})

describe('IntakeSection — subir o edital', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    intakeApi.list.mockResolvedValue(page([intake()]))
    intakeApi.start.mockResolvedValue(intake())
    intakeApi.upload.mockResolvedValue(intake())
    intakeApi.choose.mockResolvedValue(intake())
    intakeApi.reject.mockResolvedValue(intake({ status: 'REJECTED' }))
    adminCatalogApi.competitionSchedule.mockResolvedValue([])
  })

  it('sobe o PDF com o cadastro automático ligado por padrão', async () => {
    renderSection()
    const arquivo = new File(['%PDF-1.7'], 'edital.pdf', { type: 'application/pdf' })

    await userEvent.upload(await screen.findByLabelText('Arquivo PDF do edital'), arquivo)

    expect(intakeApi.upload).toHaveBeenCalledTimes(1)
    expect(intakeApi.upload.mock.calls[0][1]).toBe(true)
  })

  it('desligar o automático passa a escolha para o serviço', async () => {
    renderSection()
    await userEvent.click(
      await screen.findByRole('checkbox', {
        name: /Cadastrar automaticamente o que o edital sustentar/,
      }),
    )

    const arquivo = new File(['%PDF-1.7'], 'edital.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByLabelText('Arquivo PDF do edital'), arquivo)

    expect(intakeApi.upload.mock.calls[0][1]).toBe(false)
  })

  it('num cadastro automático, mostra as duas contas: o que entrou e o que faltou', async () => {
    intakeApi.list.mockResolvedValue(
      page([
        intake({
          status: 'APPLIED',
          source_kind: 'UPLOAD',
          source_url: null,
          source_name: 'edital-de-abertura.pdf',
          chosen_url: null,
          choice_reason: 'o arquivo foi enviado direto',
          candidates: [],
          auto_applied: true,
          competition_public_id: 'C1',
          gaps: [
            {
              code: 'BOARD_NOT_FOUND',
              label: "A banca 'Cebraspe' não está no catálogo",
              detail: 'cadastre-a em Bancas e vincule o concurso — ele ficou sem banca',
            },
            {
              code: 'SUBJECT_WITHOUT_CATALOG',
              label: 'Disciplina fora da grade: Legislação Especial',
              detail: 'não existe disciplina com este nome no catálogo.',
            },
          ],
        }),
      ]),
    )
    renderSection()

    expect(
      await screen.findByText('Concurso cadastrado, com partes em branco'),
    ).toBeInTheDocument()
    expect(screen.getByText(/só os campos com citação conferida/)).toBeInTheDocument()
    expect(screen.getByText('2 coisas ficaram faltando')).toBeInTheDocument()
    expect(screen.getByText(/A banca 'Cebraspe' não está no catálogo/)).toBeInTheDocument()
    expect(screen.getByText(/Disciplina fora da grade/)).toBeInTheDocument()
    expect(screen.getByText('cadastrado automaticamente')).toBeInTheDocument()
    // O nome do arquivo identifica a passagem, já que não houve endereço.
    expect(screen.getByText('edital-de-abertura.pdf')).toBeInTheDocument()
    // E a tela não diz "nenhum PDF escolhido": não havia o que escolher.
    expect(screen.getByText('o arquivo foi enviado direto')).toBeInTheDocument()
    expect(screen.queryByText(/nenhum PDF escolhido/)).not.toBeInTheDocument()
  })

  it('sem lacuna nenhuma, aí sim cadastrado quer dizer completo', async () => {
    intakeApi.list.mockResolvedValue(
      page([
        intake({
          status: 'APPLIED',
          auto_applied: true,
          competition_public_id: 'C1',
          gaps: [],
        }),
      ]),
    )
    renderSection()

    expect(await screen.findByText('Concurso cadastrado')).toBeInTheDocument()
    expect(screen.queryByText(/ficaram faltando/)).not.toBeInTheDocument()
    expect(screen.queryByText(/ficou faltando/)).not.toBeInTheDocument()
  })

  it('quando o automático para, diz o motivo e devolve o formulário', async () => {
    intakeApi.list.mockResolvedValue(
      page([
        intake({
          status: 'AWAITING_REVIEW',
          detail: 'já existe um concurso com este nome e ano no catálogo',
          gaps: [{ code: 'DUPLICATE', label: 'duplicata', detail: null }],
        }),
      ]),
    )
    renderSection()

    expect(await screen.findByText(/O cadastro automático parou aqui/)).toBeInTheDocument()
    expect(screen.getByText(/já existe um concurso com este nome e ano/)).toBeInTheDocument()
    // O formulário continua ali: é o caminho de quem revisa.
    expect(screen.getByRole('button', { name: /Cadastrar concurso/ })).toBeInTheDocument()
  })
})

describe('IntakeSection — cronograma cadastrado', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    intakeApi.start.mockResolvedValue(intake())
    intakeApi.upload.mockResolvedValue(intake())
    intakeApi.list.mockResolvedValue(
      page([
        intake({
          status: 'APPLIED',
          auto_applied: true,
          competition_public_id: 'C1',
          candidates: [],
          gaps: [],
        }),
      ]),
    )
    adminCatalogApi.competitionSchedule.mockResolvedValue([
      {
        public_id: 'E1',
        kind: 'EXAM',
        title: 'Aplicação da prova objetiva',
        date_start: '2026-03-15',
        date_end: null,
        is_critical: true,
        source: 'NOTICE',
        evidence_level: 'OFFICIAL',
        page_number: 2,
        quote: 'A prova objetiva será aplicada no dia 15 de março de 2026',
      },
      {
        public_id: 'E2',
        kind: 'EXEMPTION_PERIOD',
        title: 'Pedido de isenção da taxa',
        date_start: '2026-01-20',
        date_end: '2026-01-24',
        is_critical: false,
        source: 'NOTICE',
        evidence_level: 'OFFICIAL',
        page_number: 2,
        quote: 'poderá solicitar isenção da taxa entre 20 e 24 de janeiro de 2026',
      },
    ])
  })

  it('mostra cada data com a citação que a sustenta', async () => {
    renderSection()

    expect(await screen.findByText('Cronograma cadastrado — 2 data(s)')).toBeInTheDocument()
    expect(screen.getByText('15/03/2026')).toBeInTheDocument()
    expect(screen.getByText('Aplicação da prova objetiva')).toBeInTheDocument()
    expect(screen.getByText('prova')).toBeInTheDocument()
    // Prazo é a informação que o candidato usa para não perder o concurso:
    // precisa poder conferir de onde veio.
    expect(screen.getByText(/15 de março de 2026/)).toBeInTheDocument()
    // As duas datas estão na página 2 do edital, e cada uma diz a sua.
    expect(screen.getAllByText(/página 2/)).toHaveLength(2)
  })

  it('marca o prazo crítico e mostra o período quando a data tem fim', async () => {
    renderSection()
    await screen.findByText('Cronograma cadastrado — 2 data(s)')

    expect(screen.getByText('prazo crítico')).toBeInTheDocument()
    expect(screen.getByText('a 24/01/2026')).toBeInTheDocument()
  })
})
