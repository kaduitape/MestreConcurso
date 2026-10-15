/**
 * O tabuleiro do mapa mental — moldura medieval, texto de verdade.
 *
 * O pedido já previa o problema: "caso o gerador de imagens não reproduza
 * textos com fidelidade, gere a arte sem os textos internos e insira-os
 * posteriormente por uma camada de texto programática". É exatamente o que
 * acontece aqui, e não só por precaução: num mapa de estudo, texto embaralhado
 * não é defeito estético, é conteúdo errado sendo decorado.
 *
 * Então a arte é moldura e fundo, e cada palavra é DOM: legível em qualquer
 * tamanho de tela, selecionável, pesquisável e audível por leitor de tela.
 */
import {
  Crown,
  Flame,
  KeyRound,
  Scroll,
  Shield,
  Skull,
  Swords,
  TriangleAlert,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { MindMapContent, MindMapPanel } from '@/lib/api/types'

/**
 * As classes são literais de propósito.
 *
 * O Tailwind 4 só emite a variável de tema que ENXERGA escrita no código:
 * `border-${token}` montado em tempo de execução não gera cor nenhuma e o
 * painel sai cinza. Já aconteceu duas vezes neste projeto (monstros pretos,
 * barra de foco vazia); o mapa inteiro depende da cor significar algo.
 */
const PANEL_STYLE: Record<string, { frame: string; wash: string; ink: string }> = {
  'game-blue': { frame: 'border-game-blue/50', wash: 'bg-game-blue/12', ink: 'text-sky-300' },
  success: { frame: 'border-success/50', wash: 'bg-success/12', ink: 'text-emerald-300' },
  'game-purple': {
    frame: 'border-game-purple/50',
    wash: 'bg-game-purple/14',
    ink: 'text-purple-300',
  },
  danger: { frame: 'border-danger/50', wash: 'bg-danger/12', ink: 'text-rose-300' },
  'game-gold': { frame: 'border-game-gold/50', wash: 'bg-game-gold/12', ink: 'text-amber-300' },
  'game-orange': {
    frame: 'border-game-orange/50',
    wash: 'bg-game-orange/12',
    ink: 'text-orange-300',
  },
}

const FALLBACK_STYLE = {
  frame: 'border-slate-600/50',
  wash: 'bg-slate-500/10',
  ink: 'text-slate-300',
}

/** A marca do item: o tom é informação, não enfeite. */
const TONE_STYLE: Record<string, { dot: string; ink: string }> = {
  slate: { dot: 'bg-slate-500', ink: 'text-slate-200' },
  success: { dot: 'bg-success', ink: 'text-emerald-100' },
  danger: { dot: 'bg-danger', ink: 'text-rose-100' },
  'game-orange': { dot: 'bg-game-orange', ink: 'text-orange-100' },
}

const ICONS: Record<string, LucideIcon> = {
  scroll: Scroll,
  shield: Shield,
  crown: Crown,
  sword: Swords,
  flame: Flame,
  skull: Skull,
  key: KeyRound,
  trap: TriangleAlert,
}

/** Legenda das cores. Cor sem legenda é enfeite; com legenda é informação. */
const LEGEND: { label: string; dot: string }[] = [
  { label: 'Conceito', dot: 'bg-game-blue' },
  { label: 'Regra que vale', dot: 'bg-success' },
  { label: 'Classificação', dot: 'bg-game-purple' },
  { label: 'Proibição / exceção', dot: 'bg-danger' },
  { label: 'Macete', dot: 'bg-game-gold' },
  { label: 'Pegadinha', dot: 'bg-game-orange' },
]

function PanelCard({ panel }: { panel: MindMapPanel }) {
  const style = PANEL_STYLE[panel.color_token] ?? FALLBACK_STYLE
  const Icon = ICONS[panel.icon] ?? Scroll

  return (
    <section
      className={`battle-frame flex flex-col gap-3 border p-4 ${style.frame} ${style.wash}`}
      aria-label={panel.label}
    >
      <header className="flex items-center gap-2">
        <Icon className={`size-4 shrink-0 ${style.ink}`} aria-hidden />
        <h3 className={`text-sm font-extrabold tracking-wide ${style.ink}`}>{panel.title}</h3>
      </header>
      <p className="game-label -mt-2 text-[0.6rem] text-slate-500">{panel.label}</p>
      <ul className="space-y-2">
        {panel.items.map((item, index) => {
          const tone = TONE_STYLE[item.tone_color] ?? TONE_STYLE.slate
          return (
            <li key={`${item.text}-${index}`} className="flex gap-2 text-left">
              <span
                className={`mt-1.5 size-1.5 shrink-0 rounded-full ${tone.dot}`}
                aria-hidden
              />
              <span className="min-w-0">
                <span className={`text-[0.82rem] leading-snug ${tone.ink}`}>{item.text}</span>
                {item.source && (
                  // Só aparece quando a fonte estava no material enviado.
                  <span className="mt-0.5 block text-[0.68rem] text-slate-500">
                    {item.source}
                  </span>
                )}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export interface MindMapBoardProps {
  content: MindMapContent
  /** O rodapé com a marca. Desligado na pré-visualização do estúdio. */
  showBrand?: boolean
}

export function MindMapBoard({ content, showBrand = true }: MindMapBoardProps) {
  const panels = content.panels ?? []
  if (panels.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-700 p-6 text-center text-sm text-muted">
        Este mapa ainda não tem painéis.
      </p>
    )
  }

  // O medalhão fica no meio da grade de três colunas: a linha é calculada a
  // partir de quantos painéis existem, para o mapa não ficar torto com 4 ou 8.
  const centerRow = Math.max(1, Math.round((panels.length + 1) / 3 / 2))

  return (
    <figure className="mindmap-stage battle-frame m-0 p-4 sm:p-6">
      <div className="flex h-full flex-col justify-center gap-4">
        <div className="grid grid-cols-1 gap-3 [grid-auto-flow:dense] md:grid-cols-2 xl:grid-cols-3">
          <div
            className="mindmap-center battle-frame flex flex-col items-center justify-center gap-2 border-game-gold/45 bg-game-gold/8 p-5 text-center"
            style={{ '--center-row': centerRow } as React.CSSProperties}
          >
            <span className="game-label text-game-gold">{content.subject}</span>
            <h2 className="text-lg font-extrabold text-white sm:text-xl">
              {content.center_label || content.topic}
            </h2>
            {content.topic && content.topic !== content.center_label && (
              <p className="text-xs text-slate-400">{content.topic}</p>
            )}
          </div>
          {panels.map((panel) => (
            <PanelCard key={panel.kind} panel={panel} />
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 border-t border-game-gold/15 pt-3">
          {LEGEND.map((entry) => (
            <span key={entry.label} className="flex items-center gap-1.5 text-[0.68rem] text-slate-400">
              <span className={`size-1.5 rounded-full ${entry.dot}`} aria-hidden />
              {entry.label}
            </span>
          ))}
        </div>

        {showBrand && (
          <figcaption className="flex flex-col items-center gap-1 pt-1">
            <span className="game-label text-game-gold">Game of Concursos</span>
            <span className="text-[0.62rem] font-semibold tracking-[0.2em] text-slate-500 uppercase">
              Disciplina • Estratégia • Aprovação
            </span>
          </figcaption>
        )}
      </div>
    </figure>
  )
}
