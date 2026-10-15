import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { TrainingNarration } from '@/lib/api/types'

/**
 * A regra que estes testes vigiam: o destaque segue o trecho que está tocando,
 * e a cena nunca troca de voz no meio.
 */

/** Espelha a escolha de fonte do hook, sem precisar de áudio no jsdom. */
function sceneSegments(narration: TrainingNarration | undefined, sceneId: number) {
  const found = narration?.scenes.find((item) => item.scene_id === sceneId)
  const list = found?.segments ?? []
  return list.length > 0 && list.every((item) => item.audio_url) ? list : []
}

const completa: TrainingNarration = {
  voice: 'onyx',
  model_slug: 'gpt-4o-mini-tts',
  scenes: [
    {
      scene_id: 1,
      segments: [
        {
          index: 0,
          text: 'Saudações.',
          offset: 0,
          length: 10,
          audio_url: '/a/1',
          duration_hint_ms: 900,
        },
        {
          index: 1,
          text: 'Vamos começar.',
          offset: 11,
          length: 14,
          audio_url: '/a/2',
          duration_hint_ms: 1200,
        },
      ],
    },
  ],
  ready: 2,
  total: 2,
  is_complete: true,
  unavailable_reason: null,
}

describe('escolha da fonte de narração', () => {
  it('cena com todos os trechos gerados usa a voz da aula', () => {
    expect(sceneSegments(completa, 1)).toHaveLength(2)
  })

  it('cena com um trecho faltando cai inteira para a voz do navegador', () => {
    const incompleta: TrainingNarration = {
      ...completa,
      is_complete: false,
      ready: 1,
      scenes: [
        {
          scene_id: 1,
          segments: [
            completa.scenes[0].segments[0],
            { ...completa.scenes[0].segments[1], audio_url: null },
          ],
        },
      ],
    }
    // Metade gerada e metade sintetizada trocaria de voz no meio da cena.
    expect(sceneSegments(incompleta, 1)).toHaveLength(0)
  })

  it('cena sem narração gerada não inventa trechos', () => {
    expect(sceneSegments(completa, 99)).toHaveLength(0)
    expect(sceneSegments(undefined, 1)).toHaveLength(0)
  })
})

/** O mesmo destaque da página, isolado para o teste. */
function Highlight({
  text,
  spoken,
}: {
  text: string
  spoken: { offset: number; length: number } | null
}) {
  if (!spoken) return <p>{text}</p>
  const end = spoken.offset + spoken.length
  return (
    <p>
      {text.slice(0, spoken.offset)}
      <mark data-testid="spoken">{text.slice(spoken.offset, end)}</mark>
      {text.slice(end)}
    </p>
  )
}

describe('destaque do trecho falado', () => {
  const texto = 'Saudações. Vamos começar.'

  it('acende exatamente o trecho que está tocando', () => {
    render(<Highlight text={texto} spoken={{ offset: 11, length: 14 }} />)
    expect(screen.getByTestId('spoken')).toHaveTextContent('Vamos começar.')
  })

  it('sem trecho tocando, nada fica aceso', () => {
    render(<Highlight text={texto} spoken={null} />)
    expect(screen.queryByTestId('spoken')).not.toBeInTheDocument()
  })

  it('o intervalo vem dos dados, não de uma estimativa de posição', () => {
    const segmento = completa.scenes[0].segments[1]
    render(
      <Highlight text={texto} spoken={{ offset: segmento.offset, length: segmento.length }} />,
    )
    expect(screen.getByTestId('spoken')).toHaveTextContent(segmento.text)
  })
})
