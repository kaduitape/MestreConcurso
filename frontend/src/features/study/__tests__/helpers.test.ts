import { describe, expect, it } from 'vitest'
import { explainTask, formatMinutes, formatSeconds } from '../helpers'

describe('formatMinutes', () => {
  it.each([
    [45, '45min'],
    [60, '1h'],
    [105, '1h45'],
    [125, '2h05'],
    [0, '0min'],
  ])('formata %i minutos como %s', (minutes, expected) => {
    expect(formatMinutes(minutes)).toBe(expected)
  })
})

describe('formatSeconds', () => {
  it('mostra minutos e segundos abaixo de uma hora', () => {
    expect(formatSeconds(125)).toBe('02:05')
  })

  it('inclui horas quando passa de 60 minutos', () => {
    expect(formatSeconds(3725)).toBe('1:02:05')
  })

  it('nunca mostra tempo negativo', () => {
    expect(formatSeconds(-10)).toBe('00:00')
  })
})

describe('explainTask', () => {
  it('traduz as contribuições do planejador em frases', () => {
    const lines = explainTask({
      participacao_no_plano: 0.42,
      peso_no_edital: 0.2,
      questoes_na_prova: 0.15,
    })
    expect(lines).toContain('Participação da disciplina no plano: 42.0%')
    expect(lines).toContain('Peso no edital: 20.0%')
  })

  it('mostra o motivo textual quando existe', () => {
    expect(explainTask({ motivo: 'sprint pedido pelo candidato' })).toEqual([
      'sprint pedido pelo candidato',
    ])
  })

  it('informa quando a tarefa foi remarcada', () => {
    const lines = explainTask({ remarcada_de: '2026-03-01', tentativa: 2 })
    expect(lines[0]).toContain('Remarcada de 01/03/2026')
    expect(lines).toContain('Vez em que foi remarcada: 2')
  })

  it('ignora chaves desconhecidas em vez de inventar texto', () => {
    expect(explainTask({ chave_estranha: 1 })).toEqual([])
  })
})
