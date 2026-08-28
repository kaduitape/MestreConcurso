import {
  BookMarked,
  Brain,
  Briefcase,
  CalendarDays,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Layers,
  ListChecks,
  RefreshCw,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  User,
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
    ],
  },
  {
    title: 'Inteligência',
    items: [
      { label: 'Inteligência', to: '/inteligencia', icon: Sparkles },
      { label: 'Mestre IA', to: '/mestre-ia', icon: Brain },
      { label: 'Vocabulário', to: '/vocabulario', icon: BookMarked },
      { label: 'Analytics', icon: TrendingUp, phase: 'Fase 9' },
    ],
  },
  {
    title: 'Conta',
    items: [
      { label: 'Meu progresso', to: '/progresso', icon: Trophy },
      { label: 'Minha conta', to: '/conta', icon: User },
      {
        label: 'Administração',
        to: '/admin',
        icon: Shield,
        permission: 'admin_dashboard:read',
      },
    ],
  },
]
