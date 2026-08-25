import { describe, expect, it } from 'vitest'
import { ORIGIN_LABEL, RATING_LABEL, explainInterval, intervalLabel } from '../helpers'

describe('intervalLabel', () => {
  it('descreve o próximo encontro em linguagem comum', () => {
    expect(intervalLabel(0)).toBe('ainda hoje')
    expect(intervalLabel(1)).toBe('amanhã')
    expect(intervalLabel(14)).toBe('em 14 dias')
    expect(intervalLabel(30)).toBe('em cerca de 1 mês')
    expect(intervalLabel(90)).toBe('em cerca de 3 meses')
  })
})

describe('explainInterval', () => {
  it('explica o crescimento de um cartão em revisão', () => {
    const lines = explainInterval({
      motivo: 'revisão',
      intervalo_anterior: 10,
      fator_aplicado: 2.5,
      intervalo_calculado: 25,
      intervalo_final: 25,
      ajuste_de_velocidade: 1,
      facilidade_anterior: 2.5,
      facilidade_nova: 2.5,
    })

    expect(lines[0]).toBe('10 dia(s) × fator 2.5 = 25 dia(s).')
  })

  it('diz que o erro encurta sem apagar o progresso', () => {
    const lines = explainInterval({
      motivo: 'erro',
      intervalo_anterior: 40,
      intervalo_final: 14,
      facilidade_anterior: 2.5,
      facilidade_nova: 2.3,
    })

    expect(lines[0]).toContain('caiu de 40 para 14')
    expect(lines[0]).toContain('sem apagar o progresso')
    expect(lines).toContain('Facilidade do cartão: 2.5 → 2.3.')
  })

  it('mostra o efeito da velocidade nos dois sentidos', () => {
    const rapido = explainInterval({
      motivo: 'revisão',
      intervalo_anterior: 10,
      fator_aplicado: 2.5,
      intervalo_calculado: 25,
      ajuste_de_velocidade: 1.15,
      tempo_de_resposta_s: 4,
    })
    expect(rapido.some((line) => line.includes('respondeu rápido (4s): +15%'))).toBe(true)

    const lento = explainInterval({
      motivo: 'revisão',
      intervalo_anterior: 10,
      fator_aplicado: 2.5,
      intervalo_calculado: 25,
      ajuste_de_velocidade: 0.85,
      tempo_de_resposta_s: 90,
    })
    expect(lento.some((line) => line.includes('demorou (90s): -15%'))).toBe(true)
  })

  it('não cita velocidade quando ela não mudou nada', () => {
    const lines = explainInterval({
      motivo: 'revisão',
      intervalo_anterior: 5,
      fator_aplicado: 2.5,
      intervalo_calculado: 12,
      ajuste_de_velocidade: 1,
    })

    expect(lines.some((line) => line.includes('rápido') || line.includes('demorou'))).toBe(
      false,
    )
  })

  it('avisa quando o teto de intervalo foi aplicado', () => {
    const lines = explainInterval({
      motivo: 'revisão',
      intervalo_anterior: 180,
      fator_aplicado: 2.5,
      intervalo_calculado: 450,
      teto_aplicado: 180,
    })

    expect(lines).toContain('Teto de 180 dias aplicado.')
  })

  it('ignora um breakdown vazio em vez de inventar texto', () => {
    expect(explainInterval({})).toEqual([])
  })
})

describe('rótulos', () => {
  it('distinguem a origem do cartão', () => {
    expect(ORIGIN_LABEL.AI).toBe('Gerado por IA')
    expect(ORIGIN_LABEL.USER).toBe('Escrito por você')
    expect(ORIGIN_LABEL.ERROR).toBe('De um erro seu')
  })

  it('cobrem as quatro respostas possíveis', () => {
    expect(Object.keys(RATING_LABEL)).toEqual(['AGAIN', 'HARD', 'GOOD', 'EASY'])
  })
})
