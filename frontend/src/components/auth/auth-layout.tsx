import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BrandMark } from '@/components/game/brand-mark'

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="game-shell dark relative grid min-h-dvh grid-cols-1 overflow-hidden lg:grid-cols-[1.1fr_1fr]">
      <section className="relative z-10 hidden flex-col justify-between border-r border-white/[0.07] p-12 lg:flex">
        <Link to="/" className="w-fit">
          <BrandMark />
        </Link>

        <div className="max-w-lg space-y-6">
          <p className="game-label text-game-purple-light">Bem-vindo à campanha</p>
          <h2 className="text-5xl leading-[1.05] font-black tracking-[-0.05em] text-white">
            Sua preparação acaba de virar uma missão.
          </h2>
          <p className="text-slate-400">
            A plataforma cruza edital, banca, provas anteriores, seu desempenho e o tempo que
            falta para a prova — e responde a única pergunta que importa:
            <span className="font-semibold text-white"> o que estudar agora?</span>
          </p>
          <ul className="space-y-2 text-sm text-slate-500">
            <li>• Cada recomendação mostra o porquê, com os pesos que a geraram.</li>
            <li>• Nenhum número é inventado: estatística vem de dados, não de chute.</li>
            <li>• Seus dados são seus — exportação e exclusão a qualquer momento.</li>
          </ul>
        </div>

        <p className="text-xs text-slate-600">
          © {new Date().getFullYear()} Game of Concursos — Sua aprovação é a missão.
        </p>
      </section>

      <section className="relative z-10 flex items-center justify-center p-6 lg:bg-[#090d1c]/75 lg:backdrop-blur-xl">
        <div className="w-full max-w-sm space-y-6 rounded-3xl border border-white/[0.08] bg-[#0d1326]/80 p-6 shadow-[0_24px_80px_rgb(0_0_0/0.34)] sm:p-8">
          <div className="lg:hidden">
            <BrandMark />
          </div>
          <div className="space-y-1.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-white">{title}</h1>
            <p className="text-sm text-slate-500">{subtitle}</p>
          </div>
          {children}
          {footer && <div className="text-center text-sm text-muted">{footer}</div>}
        </div>
      </section>
    </div>
  )
}
