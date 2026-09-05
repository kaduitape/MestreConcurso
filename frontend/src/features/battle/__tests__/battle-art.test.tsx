import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BattleMonster } from '@/lib/api/types'
import { Monster } from '../components/monster'
import { PlayerCharacter } from '../components/player-character'

const base: BattleMonster = {
  letter: 'A',
  species: 'orc',
  name: 'Orc da Banca',
  shape: 'brute',
  color_token: 'game-purple',
  accent_token: 'game-blue',
  variant: 0,
  image_url: null,
}

describe('arte da batalha', () => {
  it('sem arte cadastrada, o monstro é a silhueta em SVG', () => {
    const { container } = render(<Monster monster={base} />)
    expect(container.querySelector('svg')).not.toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })

  it('com arte cadastrada, a imagem entra no lugar da silhueta', () => {
    const { container } = render(
      <Monster monster={{ ...base, image_url: '/api/v1/game/battle/art/abc' }} />,
    )
    const image = screen.getByRole('img', { name: 'Orc da Banca, alternativa A' })
    expect(image).toHaveAttribute('src', '/api/v1/game/battle/art/abc')
    expect(container.querySelector('svg')).toBeNull()
  })

  it('o inimigo do palco não é anunciado como alternativa', () => {
    render(<Monster monster={{ ...base, letter: '', image_url: '/art/x' }} />)
    expect(screen.getByRole('img', { name: 'Orc da Banca' })).toBeInTheDocument()
  })

  it('o guerreiro sem arte cadastrada mantém o personagem do produto', () => {
    render(<PlayerCharacter />)
    const image = screen.getByRole('img', { name: 'Seu guerreiro' })
    expect(image.getAttribute('src')).not.toBe('')
  })

  it('o guerreiro com arte cadastrada usa a arte', () => {
    render(<PlayerCharacter imageUrl="/api/v1/game/battle/art/guerreiro" />)
    expect(screen.getByRole('img', { name: 'Seu guerreiro' })).toHaveAttribute(
      'src',
      '/api/v1/game/battle/art/guerreiro',
    )
  })
})
