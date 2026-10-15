import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MindMapContent } from '@/lib/api/types'
import { MindMapBoard } from '../mindmap-board'

/**
 * A regra que estes testes vigiam: **o texto do mapa é texto de verdade**.
 *
 * Se um dia alguém trocar a renderização por uma imagem gerada, estes testes
 * caem — e é para cair. Num mapa de estudo, texto embaralhado não é defeito
 * estético, é conteúdo errado sendo decorado.
 */

const CONTENT: MindMapContent = {
  version: 'v1',
  subject: 'Direito Administrativo',
  topic: 'Princípios da Administração Pública',
  center_label: 'Princípios',
  review_notes: ['Confirmar se o edital cobra eficiência como princípio expresso.'],
  panels: [
    {
      kind: 'CONCEITO',
      title: 'O que são',
      label: 'Conceito',
      color_token: 'game-blue',
      icon: 'scroll',
      items: [
        {
          text: 'Vetores que orientam toda a atuação da Administração.',
          tone: 'NEUTRO',
          tone_color: 'slate',
          source: 'art. 37, caput, CF/88',
        },
      ],
    },
    {
      kind: 'REGRAS',
      title: 'LIMPE',
      label: 'Regras fundamentais',
      color_token: 'success',
      icon: 'shield',
      items: [
        { text: 'Legalidade', tone: 'CORRETO', tone_color: 'success', source: null },
        { text: 'Moralidade', tone: 'CORRETO', tone_color: 'success', source: null },
      ],
    },
    {
      kind: 'PEGADINHAS',
      title: 'O que a banca troca',
      label: 'Pegadinhas de concurso',
      color_token: 'game-orange',
      icon: 'trap',
      items: [
        {
          text: "Trocar 'publicidade' por 'publicação'.",
          tone: 'ALERTA',
          tone_color: 'game-orange',
          source: null,
        },
      ],
    },
  ],
}

describe('tabuleiro do mapa mental', () => {
  it('escreve cada item como texto na tela, não como imagem', () => {
    render(<MindMapBoard content={CONTENT} />)

    expect(
      screen.getByText('Vetores que orientam toda a atuação da Administração.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Legalidade')).toBeInTheDocument()
    expect(screen.getByText("Trocar 'publicidade' por 'publicação'.")).toBeInTheDocument()
    // Nenhuma imagem carrega o conteúdo: um alt-text não se amplia nem se copia.
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })

  it('mostra o centro com a matéria e o assunto', () => {
    render(<MindMapBoard content={CONTENT} />)

    expect(screen.getByRole('heading', { name: 'Princípios' })).toBeInTheDocument()
    expect(screen.getByText('Direito Administrativo')).toBeInTheDocument()
    expect(screen.getByText('Princípios da Administração Pública')).toBeInTheDocument()
  })

  it('dá a cada painel a cor fixa do seu tipo', () => {
    // Cor que muda de significado entre dois mapas deixa de ser informação.
    const { container } = render(<MindMapBoard content={CONTENT} />)

    const conceito = screen.getByRole('region', { name: 'Conceito' })
    expect(conceito.className).toContain('border-game-blue/50')
    expect(screen.getByRole('region', { name: 'Regras fundamentais' }).className).toContain(
      'border-success/50',
    )
    expect(
      screen.getByRole('region', { name: 'Pegadinhas de concurso' }).className,
    ).toContain('border-game-orange/50')

    // E a classe é literal: `border-${token}` montado em runtime não gera cor
    // nenhuma no Tailwind 4, e o painel sairia cinza.
    expect(container.innerHTML).not.toContain('border-undefined')
  })

  it('só mostra fonte quando ela veio do material enviado', () => {
    render(<MindMapBoard content={CONTENT} />)

    expect(screen.getByText('art. 37, caput, CF/88')).toBeInTheDocument()
    // "Legalidade" não tem fonte declarada, e nenhuma é inventada para ela.
    const regras = screen.getByRole('region', { name: 'Regras fundamentais' })
    expect(regras.textContent).not.toContain('art.')
  })

  it('traz a legenda das cores e a marca da plataforma', () => {
    render(<MindMapBoard content={CONTENT} />)

    expect(screen.getByText('Macete')).toBeInTheDocument()
    expect(screen.getByText('Pegadinha')).toBeInTheDocument()
    expect(screen.getByText('Game of Concursos')).toBeInTheDocument()
    expect(screen.getByText('Disciplina • Estratégia • Aprovação')).toBeInTheDocument()
  })

  it('não inventa tabuleiro quando o mapa está vazio', () => {
    render(<MindMapBoard content={{ subject: 'X', topic: 'Y', panels: [] }} />)

    expect(screen.getByText('Este mapa ainda não tem painéis.')).toBeInTheDocument()
    expect(screen.queryByText('Game of Concursos')).not.toBeInTheDocument()
  })

  it('um tipo de painel sem cor conhecida não derruba a tela', () => {
    render(
      <MindMapBoard
        content={{
          subject: 'X',
          topic: 'Y',
          panels: [
            {
              kind: 'NOVO',
              title: 'Novo painel',
              label: 'Novo',
              color_token: 'cor-que-nao-existe',
              icon: 'inexistente',
              items: [
                { text: 'Item', tone: 'NEUTRO', tone_color: 'tom-inexistente', source: null },
              ],
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Item')).toBeInTheDocument()
  })
})
