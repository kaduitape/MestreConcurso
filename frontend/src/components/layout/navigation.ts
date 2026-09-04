import {
  BarChart3,
  BookMarked,
  Brain,
  Briefcase,
  CalendarDays,
  ClipboardList,
  CreditCard,
  Crosshair,
  Flame,
  LayoutDashboard,
  Layers,
  Medal,
  RefreshCw,
  Shield,
  Sparkles,
  Swords,
  Target,
  Theater,
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
  phase?: string
  permission?: string
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

export const navigation: NavGroup[] = [
  {
    title: 'Painel principal',
    items: [
      { label: 'Hoje', to: '/hoje', icon: LayoutDashboard },
      { label: 'Missões', to: '/missoes', icon: Target },
      { label: 'Conquistas', to: '/progresso', icon: Trophy },
      { label: 'Batalhas', to: '/arena', icon: Swords },
      { label: 'Concursos', to: '/concursos', icon: Briefcase },
      { label: 'Plano de estudo', to: '/plano', icon: Flame },
      { label: 'Calendário', to: '/calendario', icon: CalendarDays },
    ],
  },
  {
    title: 'Treinamento',
    items: [
      { label: 'Questões', to: '/questoes', icon: Target },
      { label: 'Simulados', to: '/simulados', icon: ClipboardList },
      { label: 'Flashcards', to: '/flashcards', icon: Layers },
      { label: 'Dia de treinamento', to: '/treinamentos', icon: Theater },
      { label: 'Revisão', to: '/revisao', icon: RefreshCw },
      { label: 'Meus erros', to: '/meus-erros', icon: TrendingUp },
      { label: 'Você vs Banca', to: '/voce-vs-banca', icon: Crosshair },
      { label: 'Desafios', to: '/desafios', icon: Zap },
    ],
  },
  {
    title: 'Comando',
    items: [
      { label: 'Mestre IA', to: '/mestre-ia', icon: Brain },
      { label: 'Inteligência', to: '/inteligencia', icon: Sparkles },
      { label: 'Analytics', to: '/analytics', icon: BarChart3 },
      { label: 'Vocabulário', to: '/vocabulario', icon: BookMarked },
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
