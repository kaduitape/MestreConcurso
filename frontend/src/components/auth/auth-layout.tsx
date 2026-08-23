import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { GraduationCap } from 'lucide-react'

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
    <div className="aurora grid min-h-dvh grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
      <section className="hidden flex-col justify-between p-12 lg:flex">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="ai-gradient grid size-10 place-items-center rounded-md text-white">
            <GraduationCap className="size-5" aria-hidden />
          </span>
          <span className="text-lg font-semibold">
            Concurso Mestre <span className="ai-text">IA</span>
          </span>
        </Link>

        <div className="max-w-lg space-y-6">
          <h2 className="text-4xl leading-tight font-semibold tracking-tight">
            Do edital à aprovação, com uma estratégia que se ajusta a você.
          </h2>
          <p className="text-muted">
            A plataforma cruza edital, banca, provas anteriores, seu desempenho e o tempo que
            falta para a prova — e responde a única pergunta que importa:
            <span className="text-foreground"> o que estudar agora?</span>
          </p>
          <ul className="space-y-2 text-sm text-muted">
            <li>• Cada recomendação mostra o porquê, com os pesos que a geraram.</li>
            <li>• Nenhum número é inventado: estatística vem de dados, não de chute.</li>
            <li>• Seus dados são seus — exportação e exclusão a qualquer momento.</li>
          </ul>
        </div>

        <p className="text-xs text-subtle">
          © {new Date().getFullYear()} Concurso Mestre IA — Plataforma em desenvolvimento.
        </p>
      </section>

      <section className="flex items-center justify-center p-6 lg:bg-surface">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1.5 lg:hidden">
            <span className="ai-gradient grid size-10 place-items-center rounded-md text-white">
              <GraduationCap className="size-5" aria-hidden />
            </span>
          </div>
          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="text-sm text-muted">{subtitle}</p>
          </div>
          {children}
          {footer && <div className="text-center text-sm text-muted">{footer}</div>}
        </div>
      </section>
    </div>
  )
}
