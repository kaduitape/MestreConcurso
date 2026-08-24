import type { StudyTaskKind, StudyTaskStatus } from '@/lib/api/types'

export const KIND_TONE: Record<StudyTaskKind, string> = {
  THEORY: 'bg-primary-soft text-primary',
  QUESTIONS: 'bg-info-soft text-info',
  REVIEW: 'bg-warning-soft text-warning',
  FLASHCARDS: 'bg-secondary-soft text-secondary',
  SIMULATION: 'bg-danger-soft text-danger',
  SPRINT: 'bg-success-soft text-success',
}

export const STATUS_LABEL: Record<StudyTaskStatus, string> = {
  PENDING: 'Pendente',
  DONE: 'Concluída',
  SKIPPED: 'Pulada',
  RESCHEDULED: 'Remarcada',
  DROPPED: 'Removida do plano',
}

export const WEEKDAYS: { value: number; label: string; short: string }[] = [
  { value: 0, label: 'Segunda-feira', short: 'Seg' },
  { value: 1, label: 'Terça-feira', short: 'Ter' },
  { value: 2, label: 'Quarta-feira', short: 'Qua' },
  { value: 3, label: 'Quinta-feira', short: 'Qui' },
  { value: 4, label: 'Sexta-feira', short: 'Sex' },
  { value: 5, label: 'Sábado', short: 'Sáb' },
  { value: 6, label: 'Domingo', short: 'Dom' },
]

/** 105 → "1h45"; 45 → "45min". */
export function formatMinutes(minutes: number): string {
  if (minutes <= 0) return '0min'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest}min`
  if (rest === 0) return `${hours}h`
  return `${hours}h${String(rest).padStart(2, '0')}`
}

export function formatSeconds(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(rest)}`
    : `${pad(minutes)}:${pad(rest)}`
}

/**
 * Traduz o `score_breakdown` gravado com a tarefa em frases legíveis.
 * Nenhum texto é inventado: cada linha corresponde a um número real.
 */
export function explainTask(breakdown: Record<string, unknown>): string[] {
  const labels: Record<string, string> = {
    participacao_no_plano: 'Participação da disciplina no plano',
    peso_no_edital: 'Peso no edital',
    questoes_na_prova: 'Questões na prova',
    extensao_do_conteudo: 'Extensão do conteúdo',
    duracao_solicitada: 'Duração pedida no sprint',
    tentativa: 'Vez em que foi remarcada',
  }

  const lines: string[] = []
  for (const [key, value] of Object.entries(breakdown)) {
    if (key === 'motivo') {
      lines.push(String(value))
      continue
    }
    if (key === 'remarcada_de') {
      lines.push(
        `Remarcada de ${new Date(`${String(value)}T00:00:00`).toLocaleDateString('pt-BR')}`,
      )
      continue
    }
    const label = labels[key]
    if (!label) continue
    lines.push(
      typeof value === 'number' && value <= 1 && key !== 'tentativa'
        ? `${label}: ${(value * 100).toFixed(1)}%`
        : `${label}: ${String(value)}`,
    )
  }
  return lines
}
