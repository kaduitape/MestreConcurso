import {
  Brain,
  Briefcase,
  CalendarDays,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Layers,
  ListChecks,
  Shield,
  Target,
  TrendingUp,
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
      { label: 'Concursos', to: '/concursos', icon: Briefcase },
      { label: 'Plano de estudo', to: '/plano', icon: Target },
      { label: 'Calendário', to: '/calendario', icon: CalendarDays },
      { label: 'Meu edital', icon: FileText, phase: 'Fase 3' },
    ],
  },
  {
    title: 'Treino',
    items: [
      { label: 'Questões', icon: ListChecks, phase: 'Fase 5' },
      { label: 'Simulados', icon: ClipboardList, phase: 'Fase 5' },
      { label: 'Flashcards', icon: Layers, phase: 'Fase 8' },
      { label: 'Meus erros', icon: TrendingUp, phase: 'Fase 6' },
    ],
  },
  {
    title: 'Inteligência',
    items: [
      { label: 'Mestre IA', icon: Brain, phase: 'Fase 7' },
      { label: 'Analytics', icon: TrendingUp, phase: 'Fase 9' },
    ],
  },
  {
    title: 'Conta',
    items: [
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
