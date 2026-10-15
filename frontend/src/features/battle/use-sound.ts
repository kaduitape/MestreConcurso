import { useCallback, useState } from 'react'
import { playBattleSound, setSoundEnabled, soundEnabled, type BattleSound } from './sound'

/** O interruptor do som, com a preferência gravada neste aparelho. */
export function useBattleSound() {
  const [enabled, setEnabled] = useState(soundEnabled)

  const toggle = useCallback(() => {
    setEnabled((current) => {
      const next = !current
      setSoundEnabled(next)
      // O clique que liga o som já é o gesto que libera o áudio no navegador.
      if (next) playBattleSound('select')
      return next
    })
  }, [])

  const play = useCallback((name: BattleSound) => playBattleSound(name), [])

  return { enabled, toggle, play }
}
