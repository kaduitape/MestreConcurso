import { useEffect, useState } from 'react'
import type { BattleViewport } from '@/lib/api/types'
import { viewportOf } from './layout'

/**
 * A largura real da tela, reduzida às três faixas que a batalha usa.
 *
 * O servidor recebe esta faixa junto com o pedido para sugerir um layout, mas
 * quem tem a medida é o navegador. O estado guarda a **faixa**, não a largura:
 * arrastar a janela um pixel não deve provocar re-render em cascata.
 */
export function useBattleViewport(): BattleViewport {
  const [viewport, setViewport] = useState<BattleViewport>(() =>
    typeof window === 'undefined' ? 'desktop' : viewportOf(window.innerWidth),
  )

  useEffect(() => {
    const update = () => {
      const next = viewportOf(window.innerWidth)
      setViewport((current) => (current === next ? current : next))
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  return viewport
}
