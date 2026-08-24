import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { MissionPanel } from '../mission'
import type { TodayMission } from '@/lib/api/types'

const mission: TodayMission = {
  day: '2026-08-24',
  plan_public_id: 'PLAN',
  plan_name: 'Plano — Agente de Polícia',
  days_until_exam: 87,
  planned_minutes: 105,
  done_minutes: 25,
  overdue_count: 0,
  tasks: [
    {
      public_id: 'T1',
      scheduled_for: '2026-08-24',
      kind: 'THEORY',
      kind_label: 'Teoria',
      subject_key: 'sub:direito-penal',
      subject_label: 'Direito Penal',
      color_token: 'subject-direito',
      planned_minutes: 25,
      actual_minutes: 0,
      status: 'PENDING',
      order_index: 0,
      source: 'PLANNER',
      reschedule_count: 0,
      rescheduled_from: null,
      score_breakdown: { participacao_no_plano: 0.42, peso_no_edital: 0.2 },
    },
    {
      public_id: 'T2',
      scheduled_for: '2026-08-24',
      kind: 'REVIEW',
      kind_label: 'Revisão',
      subject_key: null,
      subject_label: null,
      color_token: 'subject-especifica',
      planned_minutes: 30,
      actual_minutes: 30,
      status: 'DONE',
      order_index: 1,
      source: 'PLANNER',
      reschedule_count: 0,
      rescheduled_from: null,
      score_breakdown: { motivo: 'bloco fixo de consolidação do plano' },
    },
  ],
}

function renderMission() {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(null), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MissionPanel mission={mission} />
    </QueryClientProvider>,
  )
}

describe('MissionPanel', () => {
  it('mostra o tempo planejado e o que falta', () => {
    renderMission()
    expect(screen.getByText(/1h45 planejados/)).toBeInTheDocument()
    expect(screen.getByText(/25min restantes/)).toBeInTheDocument()
  })

  it('lista as tarefas com disciplina e tipo', () => {
    renderMission()
    expect(screen.getByText('Direito Penal')).toBeInTheDocument()
    expect(screen.getByText('Teoria')).toBeInTheDocument()
    expect(screen.getByText('Revisão')).toBeInTheDocument()
  })

  it('destaca os dias até a prova', () => {
    renderMission()
    expect(screen.getByText('87 dias para a prova')).toBeInTheDocument()
  })

  it('explica por que a tarefa está na agenda', async () => {
    const user = userEvent.setup()
    renderMission()

    await user.click(
      screen.getByRole('button', { name: /Por que esta tarefa: Direito Penal/ }),
    )

    expect(
      await screen.findByText(/Participação da disciplina no plano: 42.0%/),
    ).toBeInTheDocument()
    // A explicação deixa claro que ainda não há priorização por desempenho.
    expect(screen.getByText(/Mestre Priority Score.*Fase 6/)).toBeInTheDocument()
  })
})
