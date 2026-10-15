/**
 * Sons da batalha, sintetizados na hora.
 *
 * Sete efeitos curtos, nenhum arquivo. A razão é a mesma das silhuetas em SVG:
 * a primeira prioridade do pedido é leveza, e sete MP3 seriam sete downloads
 * antes da primeira questão — num celular modesto, na fila do ônibus. Osciladores
 * da Web Audio custam alguns bytes de código e tocam na hora.
 *
 * Nada toca sozinho: não há música, e o `AudioContext` só nasce depois de um
 * clique. Uma plataforma de concurso é usada no trabalho e na biblioteca; som
 * que surpreende é som que faz fechar a aba. Por isso o padrão é **desligado**,
 * e a escolha fica gravada por aparelho — fone no ônibus e silêncio no
 * escritório são a mesma pessoa.
 */

export type BattleSound =
  'select' | 'sword' | 'impact' | 'monster_attack' | 'correct' | 'wrong' | 'level_up'

const STORAGE_KEY = 'mestre.battle.sound'

let context: AudioContext | null = null

function audio(): AudioContext | null {
  if (typeof window === 'undefined') return null
  try {
    context ??= new AudioContext()
    // Navegadores suspendem o contexto criado fora de um gesto do usuário.
    if (context.state === 'suspended') void context.resume()
    return context
  } catch {
    return null
  }
}

export function soundEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'on'
  } catch {
    return false
  }
}

export function setSoundEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? 'on' : 'off')
  } catch {
    // Navegação privada sem armazenamento: o som vale só para esta sessão.
  }
}

interface Tone {
  type: OscillatorType
  /** Frequência inicial e final, em hertz — a curva dá o caráter do efeito. */
  from: number
  to: number
  duration: number
  gain: number
}

/** Cada som é uma varredura de frequência curta. Nada dura mais que meio segundo. */
const TONES: Record<BattleSound, Tone[]> = {
  select: [{ type: 'triangle', from: 420, to: 560, duration: 0.07, gain: 0.05 }],
  sword: [{ type: 'sawtooth', from: 900, to: 180, duration: 0.16, gain: 0.06 }],
  impact: [
    { type: 'square', from: 160, to: 60, duration: 0.13, gain: 0.09 },
    { type: 'triangle', from: 320, to: 90, duration: 0.1, gain: 0.05 },
  ],
  monster_attack: [{ type: 'sawtooth', from: 220, to: 70, duration: 0.24, gain: 0.08 }],
  correct: [
    { type: 'sine', from: 660, to: 880, duration: 0.11, gain: 0.06 },
    { type: 'sine', from: 880, to: 1180, duration: 0.14, gain: 0.05 },
  ],
  wrong: [{ type: 'sine', from: 300, to: 150, duration: 0.26, gain: 0.06 }],
  level_up: [
    { type: 'sine', from: 520, to: 660, duration: 0.1, gain: 0.05 },
    { type: 'sine', from: 660, to: 880, duration: 0.12, gain: 0.05 },
    { type: 'sine', from: 880, to: 1320, duration: 0.2, gain: 0.05 },
  ],
}

/** Toca um efeito. Silencioso e sem erro quando o som está desligado. */
export function playBattleSound(name: BattleSound): void {
  if (!soundEnabled()) return
  const ctx = audio()
  if (!ctx) return

  let at = ctx.currentTime
  for (const tone of TONES[name]) {
    const oscillator = ctx.createOscillator()
    const envelope = ctx.createGain()

    oscillator.type = tone.type
    oscillator.frequency.setValueAtTime(tone.from, at)
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(1, tone.to), at + tone.duration)

    // Ataque rápido e queda exponencial: sem estalo no início nem no fim.
    envelope.gain.setValueAtTime(0.0001, at)
    envelope.gain.exponentialRampToValueAtTime(tone.gain, at + 0.012)
    envelope.gain.exponentialRampToValueAtTime(0.0001, at + tone.duration)

    oscillator.connect(envelope).connect(ctx.destination)
    oscillator.start(at)
    oscillator.stop(at + tone.duration + 0.02)
    at += tone.duration * 0.7
  }
}
