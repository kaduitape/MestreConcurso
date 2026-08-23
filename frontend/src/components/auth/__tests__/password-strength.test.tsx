import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PasswordStrength } from '../password-strength'

describe('PasswordStrength', () => {
  it('lista todos os requisitos da política de senha', () => {
    render(<PasswordStrength value="" />)
    expect(screen.getByText(/10\+ caracteres/)).toBeInTheDocument()
    expect(screen.getByText(/símbolo/)).toBeInTheDocument()
  })

  it('marca como atendidos apenas os requisitos cumpridos', () => {
    render(<PasswordStrength value="senhaSenha1" />)
    expect(screen.getByText('✓ 10+ caracteres')).toBeInTheDocument()
    expect(screen.getByText('○ símbolo')).toBeInTheDocument()
  })

  it('marca todos como atendidos em uma senha forte', () => {
    render(<PasswordStrength value="Senha@Forte123" />)
    expect(screen.queryByText(/^○/)).not.toBeInTheDocument()
  })
})
