import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MissionCard } from '../components/mission-card'
import type { Mission } from '@/lib/api/types'

const base: Mission = {
  public_id: 'M1',
  scope: 'DAILY',
  kind: 'REVIEW_CARDS',
  title: 'Revisar 24 cartões vencidos',
  description: 'Memória vencida se perde hoje; revisada, volta a render.',
  target_metric: 'cards_reviewed',
  target_value: 24,
  current_value: 18,
  progress_ratio: 0.75,
  xp_reward: 80,
  priority: 'HIGH',
  difficulty: 'MEDIA',
  estimated_minutes: 12,
  status: 'PENDING',
  rationale: '24 cartão(ões) venceram. Adiar hoje empurra todos para amanhã.',
  valid_from: '2026-08-28',
}

describe('MissionCard', () => {
  it('mostra prioridade, tempo estimado, recompensa e progresso real', () => {
    render(<MissionCard mission={base} />)

    expect(screen.getByText('Alta')).toBeInTheDocument()
    expect(screen.getByText('~12 min')).toBeInTheDocument()
    expect(screen.getByText('+80 XP')).toBeInTheDocument()
    expect(screen.getByText('18 / 24')).toBeInTheDocument()
  })

  it('abre o "por quê?" com o número que gerou a missão', async () => {
    render(<MissionCard mission={base} />)

    await userEvent.click(screen.getByRole('button', { name: /por quê/i }))
    expect(screen.getByText(/24 cartão\(ões\) venceram/)).toBeInTheDocument()
  })

  it('não oferece resgate enquanto a missão não foi cumprida', () => {
    render(<MissionCard mission={base} onClaim={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /resgatar/i })).not.toBeInTheDocument()
  })

  it('oferece o resgate quando a missão está cumprida', async () => {
    const onClaim = vi.fn()
    render(
      <MissionCard
        mission={{ ...base, current_value: 24, progress_ratio: 1, status: 'DONE' }}
        onClaim={onClaim}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /resgatar 80 XP/i }))
    expect(onClaim).toHaveBeenCalledOnce()
  })

  it('missão resgatada não oferece resgate de novo', () => {
    render(
      <MissionCard
        mission={{ ...base, current_value: 24, progress_ratio: 1, status: 'CLAIMED' }}
        onClaim={vi.fn()}
      />,
    )

    expect(screen.getByText('Concluída')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /resgatar/i })).not.toBeInTheDocument()
  })
})
