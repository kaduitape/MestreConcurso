import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CategoryBars, IntervalChart } from '../components/interval-chart'
import { MasterScorePanel } from '../components/master-score-panel'
import { PathList, ProjectionPanel } from '../components/projection-panel'
import type { AnalyticsChart, ExamProjection, MasterScore, StudyPath } from '@/lib/api/types'

const score: MasterScore = {
  value: 644,
  low: 592,
  high: 686,
  band: 'Consolidando',
  band_note: 'O conteúdo já responde, com pontos frágeis claros.',
  confidence: 'MEDIUM',
  available_weight: 1,
  components: [
    {
      key: 'acerto',
      label: 'Acerto em questões',
      weight: 0.3,
      points: 210,
      value: 0.7,
      low: 0.6462,
      high: 0.7484,
      sample: 300,
      available: true,
      detail: '70,0% em 300 respostas (faixa 65–75%)',
    },
    {
      key: 'retencao',
      label: 'Retenção na revisão',
      weight: 0.2,
      points: 160,
      value: 0.8,
      low: 0.71,
      high: 0.87,
      sample: 100,
      available: true,
      detail: '80,0% em 100 revisões (faixa 71–87%)',
    },
  ].map((item) => ({ ...item, confidence: 'MEDIUM' as const })),
  missing_signals: [],
  interval_note:
    'A faixa é a propagação do intervalo de Wilson (95%) de cada sinal pelos respectivos pesos. Não é uma previsão, e não é probabilidade de aprovação.',
  empty_reason: null,
}

describe('MasterScorePanel', () => {
  it('mostra a faixa junto do valor, sempre', () => {
    render(<MasterScorePanel score={score} />)

    expect(screen.getByText('644')).toBeInTheDocument()
    expect(screen.getByText('faixa 592–686')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /faixa de 592 a 686/ })).toBeInTheDocument()
  })

  it('abre as parcelas e declara que XP não entra', async () => {
    render(<MasterScorePanel score={score} />)
    await userEvent.click(screen.getByRole('button', { name: /por quê/i }))

    expect(screen.getByText(/somam exatamente 644/)).toBeInTheDocument()
    expect(screen.getByText(/XP não entra nesta conta/)).toBeInTheDocument()
    expect(screen.getByText(/Wilson/)).toBeInTheDocument()
  })

  it('sem amostra não inventa nota — mostra o que falta', () => {
    render(
      <MasterScorePanel
        score={{
          ...score,
          value: 0,
          low: 0,
          high: 0,
          confidence: 'NONE',
          available_weight: 0,
          empty_reason: 'Ainda não há dados suficientes para medir competência.',
          components: score.components.map((item) => ({
            ...item,
            available: false,
            value: null,
            low: null,
            high: null,
            points: 0,
            sample: 0,
            detail: '0 de 30 respostas para entrar na conta',
          })),
        }}
      />,
    )

    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText(/Ainda não há dados suficientes/)).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('avisa quando parte dos sinais não tem amostra', () => {
    render(<MasterScorePanel score={{ ...score, available_weight: 0.5 }} />)
    expect(screen.getByText(/50% dos sinais têm amostra/)).toBeInTheDocument()
  })
})

const projection: ExamProjection = {
  total_questions: 60,
  covered_questions: 50,
  coverage: 0.8333,
  expected: 44,
  expected_low: 35.66,
  expected_high: 52.04,
  expected_percent: 0.88,
  confidence: 'MEDIUM',
  is_reliable: true,
  disclaimer:
    'Esta é uma estimativa de acerto sobre o seu próprio histórico, não uma previsão de resultado. A plataforma não estima chance de aprovação.',
  empty_reason: null,
  subjects: [
    {
      subject_id: 2,
      name: 'Direito Penal',
      questions: 30,
      weight: 2,
      is_eliminatory: true,
      accuracy: 0.5,
      low: 0.393,
      high: 0.607,
      expected: 15,
      expected_low: 11.79,
      expected_high: 18.21,
      sample: 80,
      included: true,
      confidence: 'MEDIUM',
      detail: '50% em 80 respostas · 15 de 30 questões (faixa 11.79–18.21)',
      risk_note: 'O edital exige 15 nesta disciplina e o limite inferior da sua faixa é 11.79.',
    },
    {
      subject_id: 3,
      name: 'Informática',
      questions: 10,
      weight: 1,
      is_eliminatory: false,
      accuracy: null,
      low: null,
      high: null,
      expected: null,
      expected_low: null,
      expected_high: null,
      sample: 5,
      included: false,
      confidence: 'NONE',
      detail: '5 de 20 respostas para esta disciplina entrar na estimativa.',
      risk_note: null,
    },
  ],
}

describe('ProjectionPanel', () => {
  it('declara que não estima aprovação', () => {
    render(<ProjectionPanel projection={projection} />)
    expect(screen.getByText(/não estima chance de aprovação/)).toBeInTheDocument()
  })

  it('mostra a faixa e a cobertura da estimativa', () => {
    render(<ProjectionPanel projection={projection} />)

    expect(screen.getByText('44')).toBeInTheDocument()
    expect(screen.getByText('faixa 35.7–52.0')).toBeInTheDocument()
    expect(screen.getByText(/cobre 83% das questões da prova/)).toBeInTheDocument()
  })

  it('mostra o alerta do edital na disciplina eliminatória', () => {
    render(<ProjectionPanel projection={projection} />)

    expect(screen.getByText('eliminatória')).toBeInTheDocument()
    expect(screen.getByText(/O edital exige 15 nesta disciplina/)).toBeInTheDocument()
  })

  it('cobertura baixa não exibe total: exibe o motivo', () => {
    render(
      <ProjectionPanel
        projection={{
          ...projection,
          is_reliable: false,
          expected: null,
          expected_low: null,
          expected_high: null,
          coverage: 0.33,
          empty_reason: 'A estimativa cobriria apenas 33% das questões da prova.',
        }}
      />,
    )

    expect(screen.queryByText('44')).not.toBeInTheDocument()
    expect(screen.getByText(/cobriria apenas 33%/)).toBeInTheDocument()
  })
})

const path: StudyPath = {
  disclaimer:
    'As ações são ordenadas por quantas questões da prova elas colocam em jogo. Seguir a lista melhora o que é medido aqui; não é garantia de resultado.',
  empty_reason: null,
  steps: [
    {
      subject_id: 2,
      subject_name: 'Direito Penal',
      kind: 'IMPROVE',
      label: 'Melhorar',
      action: 'Estudar e resolver questões de Direito Penal.',
      evidence: '50% em 80 respostas · 30 questões na prova · peso 2',
      questions_at_stake: 30,
      is_eliminatory: true,
      risk_note: null,
    },
    {
      subject_id: 3,
      subject_name: 'Informática',
      kind: 'MEASURE',
      label: 'Medir',
      action: 'Responder 15 questões de Informática para a disciplina entrar na estimativa.',
      evidence: '5 respostas registradas · 10 questões desta disciplina na prova',
      questions_at_stake: 0,
      is_eliminatory: false,
      risk_note: null,
    },
  ],
}

describe('PathList', () => {
  it('todo passo mostra o número que o gerou', () => {
    render(<PathList path={path} />)

    expect(
      screen.getByText('50% em 80 respostas · 30 questões na prova · peso 2'),
    ).toBeInTheDocument()
    expect(screen.getByText(/5 respostas registradas/)).toBeInTheDocument()
  })

  it('quantifica o que está em jogo apenas onde há medição', () => {
    render(<PathList path={path} />)

    expect(screen.getByText('30.0 questões em jogo')).toBeInTheDocument()
    expect(screen.queryByText('0.0 questões em jogo')).not.toBeInTheDocument()
  })

  it('não promete aprovação', () => {
    const { container } = render(<PathList path={path} />)
    const texto = container.textContent!.toLowerCase()

    expect(texto).toContain('não é garantia')
    for (const proibido of ['você será aprovado', 'garante aprovação']) {
      expect(texto).not.toContain(proibido)
    }
  })
})

const chart: AnalyticsChart = {
  key: 'acerto',
  title: 'Evolução do acerto',
  decision: 'Mostra se o desempenho está subindo ou escorregando.',
  unit: '%',
  note: 'Cada semana traz a própria faixa.',
  empty_reason: null,
  points: [
    { label: '02/03', value: 0.6, low: 0.3, high: 0.85, sample: 10, day: '2026-03-02' },
    { label: '09/03', value: 0.72, low: 0.67, high: 0.77, sample: 300, day: '2026-03-09' },
  ],
}

describe('IntervalChart', () => {
  it('descreve os pontos com valor e amostra', () => {
    render(<IntervalChart chart={chart} />)
    expect(
      screen.getByRole('img', { name: /02\/03: 60% em 10; 09\/03: 72% em 300/ }),
    ).toBeInTheDocument()
  })

  it('mostra a faixa do último ponto ao lado do valor', () => {
    render(<IntervalChart chart={chart} />)
    expect(screen.getByText(/\(67%–77%\)/)).toBeInTheDocument()
  })

  it('gráfico vazio mostra o motivo e a decisão que ele serviria', () => {
    render(
      <IntervalChart
        chart={{ ...chart, points: [], empty_reason: 'Aparece a partir da segunda semana.' }}
      />,
    )

    expect(screen.getByText('Aparece a partir da segunda semana.')).toBeInTheDocument()
    expect(screen.getByText(chart.decision)).toBeInTheDocument()
  })
})

describe('CategoryBars', () => {
  it('mostra cada categoria com o percentual', () => {
    render(
      <CategoryBars
        chart={{
          ...chart,
          key: 'cobertura',
          points: [
            { label: 'Português', value: 0.5, low: null, high: null, sample: 600, day: null },
          ],
          note: 'Cobertura é tempo cumprido sobre tempo planejado — não é domínio.',
        }}
      />,
    )

    expect(screen.getByText('Português')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText(/não é domínio/)).toBeInTheDocument()
  })
})
