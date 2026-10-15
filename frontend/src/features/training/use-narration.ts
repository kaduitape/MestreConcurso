import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { NarrationSegment, TrainingNarration, TrainingScene } from '@/lib/api/types'

/** O trecho que está tocando agora, para a tela acender a frase certa. */
export interface SpokenRange {
  offset: number
  length: number
}

export type NarrationSource = 'generated' | 'browser' | 'none'

/**
 * A narração de uma cena.
 *
 * Duas fontes, nessa ordem: o áudio gerado (voz de verdade, com direção de
 * cena) e, quando ele não existe, a voz do navegador. **A segunda nunca é
 * escondida** — a tela diz qual está tocando, porque a diferença é audível e
 * fingir que são a mesma coisa seria enganar quem configura a plataforma.
 *
 * Os trechos tocam em sequência, e é por isso que o destaque acerta o lugar: a
 * frase acesa é a frase cujo arquivo está no ar, não uma estimativa de onde a
 * voz deveria estar.
 */
export function useSceneNarration({
  enabled,
  scene,
  sceneId,
  narration,
  rate,
  browserVoiceURI,
}: {
  enabled: boolean
  scene: TrainingScene | undefined
  sceneId: number
  narration: TrainingNarration | undefined
  rate: number
  browserVoiceURI: string
}) {
  const [active, setActive] = useState(false)
  const [spoken, setSpoken] = useState<SpokenRange | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const cancelled = useRef(false)

  const segments: NarrationSegment[] = useMemo(() => {
    const found = narration?.scenes.find((item) => item.scene_id === sceneId)
    const list = found?.segments ?? []
    // Um trecho sem áudio no meio quebraria a sequência: ou a cena inteira tem
    // voz gerada, ou ela toca pela voz do navegador.
    return list.length > 0 && list.every((item) => item.audio_url) ? list : []
  }, [narration, sceneId])

  const source: NarrationSource = !enabled
    ? 'none'
    : segments.length > 0
      ? 'generated'
      : typeof window !== 'undefined' && 'speechSynthesis' in window
        ? 'browser'
        : 'none'

  const stop = useCallback(() => {
    cancelled.current = true
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current = null
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    setActive(false)
    setSpoken(null)
  }, [])

  useEffect(() => {
    if (!enabled || !scene) return
    cancelled.current = false

    if (source === 'generated') {
      let current = 0
      const playNext = () => {
        if (cancelled.current || current >= segments.length) {
          setActive(false)
          setSpoken(null)
          return
        }
        const segment = segments[current]
        setSpoken({ offset: segment.offset, length: segment.length })
        const audio = new Audio(segment.audio_url!)
        audio.playbackRate = rate
        audioRef.current = audio
        audio.onended = () => {
          current += 1
          playNext()
        }
        // Falha ao carregar um trecho não pode travar a cena no meio: segue
        // para o próximo e a aula continua.
        audio.onerror = () => {
          current += 1
          playNext()
        }
        setActive(true)
        void audio.play().catch(() => {
          current += 1
          playNext()
        })
      }
      playNext()
      return stop
    }

    if (source === 'browser') {
      const text = scene.narration || scene.dialogue
      if (!text) return
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'pt-BR'
      utterance.rate = rate
      const voices = window.speechSynthesis.getVoices()
      utterance.voice = voices.find((item) => item.voiceURI === browserVoiceURI) ?? null
      utterance.onstart = () => setActive(true)
      // O navegador só informa onde começou a palavra; o fim é o próximo espaço.
      utterance.onboundary = (event) => {
        const start = event.charIndex
        const nextSpace = text.indexOf(' ', start)
        setSpoken({ offset: start, length: (nextSpace < 0 ? text.length : nextSpace) - start })
      }
      utterance.onend = () => {
        setActive(false)
        setSpoken(null)
      }
      utterance.onerror = () => {
        setActive(false)
        setSpoken(null)
      }
      window.speechSynthesis.speak(utterance)
      return stop
    }

    return undefined
  }, [browserVoiceURI, enabled, rate, scene, segments, source, stop])

  return { active, spoken, source, stop, segments }
}
