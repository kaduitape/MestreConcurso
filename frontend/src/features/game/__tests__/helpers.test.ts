import { describe, expect, it } from 'vitest'
import {
  EVENT_LABEL,
  PRIORITY_LABEL,
  RANK_STYLE,
  formatEstimate,
  scorePercent,
} from '../helpers'

describe('scorePercent', () => {
  it('usa vírgula decimal, como o resto do produto', () => {
    expect(scorePercent(0.6587)).toBe('65,9%')
    expect(scorePercent(0.5, 0)).toBe('50%')
  })
})

describe('formatEstimate', () => {
  it('descreve o tempo estimado da missão', () => {
    expect(formatEstimate(12)).toBe('~12 min')
    expect(formatEstimate(60)).toBe('~1h')
    expect(formatEstimate(95)).toBe('~1h35')
  })
})

describe('catálogos', () => {
  it('cobrem os oito ranks', () => {
    expect(Object.keys(RANK_STYLE)).toHaveLength(8)
    expect(RANK_STYLE.GRAO_MESTRE.label).toBe('Grão-Mestre')
  })

  it('traduzem prioridade e eventos de XP', () => {
    expect(PRIORITY_LABEL.HIGH).toBe('Alta')
    expect(EVENT_LABEL.STUDY_SESSION).toBe('Estudo com foco')
    expect(EVENT_LABEL.ACHIEVEMENT_UNLOCKED).toBe('Conquista')
  })
})
