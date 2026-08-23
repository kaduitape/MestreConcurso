import { describe, expect, it } from 'vitest'
import { firstName, greeting, initials } from '@/lib/utils'

describe('initials', () => {
  it('usa a primeira e a última palavra do nome', () => {
    expect(initials('Carlos Eduardo Souza')).toBe('CS')
  })

  it('usa duas letras quando há apenas um nome', () => {
    expect(initials('Carlos')).toBe('CA')
  })

  it('não quebra com entrada vazia', () => {
    expect(initials('   ')).toBe('?')
  })
})

describe('firstName', () => {
  it('retorna o primeiro nome', () => {
    expect(firstName('Ana Paula Lima')).toBe('Ana')
  })
})

describe('greeting', () => {
  it.each([
    [new Date('2026-03-10T08:00:00'), 'Bom dia'],
    [new Date('2026-03-10T13:00:00'), 'Boa tarde'],
    [new Date('2026-03-10T20:00:00'), 'Boa noite'],
  ])('saúda conforme o horário', (date, expected) => {
    expect(greeting(date)).toBe(expected)
  })
})
