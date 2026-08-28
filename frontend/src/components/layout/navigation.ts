import {
  BookMarked,
  Brain,
  Briefcase,
  CalendarDays,
  ClipboardList,
  CreditCard,
  Crosshair,
  FileText,
  LayoutDashboard,
  Layers,
  ListChecks,
  Map,
  Medal,
  RefreshCw,
  Shield,
  Sparkles,
  Swords,
  Target,
  TrendingUp,
  Trophy,
  User,
  Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  label: string
  to?: string
  icon: LucideIcon
  /** Itens ainda não entregues aparecem desabilitados, com a fase indicada. */
  phase?: string
  permission?: string
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

export const navigation: NavGroup[] = [
  {
    title: 'Preparação',
    items: [
      { label: 'Hoje', to: '/hoje', icon: LayoutDashboard },
      { label: 'Missões', to: '/missoes', icon: Target },
      { label: 'Concursos', to: '/concursos', icon: Briefcase },
      { label: 'Plano de estudo', to: '/plano', icon: Target },
      { label: 'Calendário', to: '/calendario', icon: CalendarDays },
      { label: 'Meu edital', icon: FileText, phase: 'Fase 3' },
    ],
  },
  {
    title: 'Treino',
    items: [
      { label: 'Questões', to: '/questoes', icon: ListChecks },
      { label: 'Simulados', to: '/simulados', icon: ClipboardList },
      { label: 'Flashcards', to: '/flashcards', icon: Layers },
      { label: 'Revisão', to: '/revisao', icon: RefreshCw },
      { label: 'Meus erros', to: '/meus-erros', icon: TrendingUp },
      { label: 'Você vs Banca', to: '/voce-vs-banca', icon: Crosshair },
      { label: 'Desafios', to: '/desafios', icon: Zap },
      { label: 'Arena', to: '/arena', icon: Swords },
    ],
  },
  {
    title: 'Inteligência',
    items: [
      { label: 'Inteligência', to: '/inteligencia', icon: Sparkles },
      { label: 'Mestre IA', to: '/mestre-ia', icon: Brain },
      { label: 'Vocabulário', to: '/vocabulario', icon: BookMarked },
      { label: 'Analytics', to: '/analytics', icon: TrendingUp },
    ],
  },
  {
    title: 'Conta',
    items: [
      { label: 'Meu progresso', to: '/progresso', icon: Trophy },
      { label: 'Jornada', to: '/jornada', icon: Map },
      { label: 'Temporada', to: '/temporada', icon: Medal },
      { label: 'Minha conta', to: '/conta', icon: User },
      { label: 'Plano e cobrança', to: '/plano-e-cobranca', icon: CreditCard },
      {
        label: 'Administração',
        to: '/admin',
        icon: Shield,
        permission: 'admin_dashboard:read',
      },
    ],
  },
]
