import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CalendarDays,
  Check,
  ChevronRight,
  Circle,
  Clock3,
  Crosshair,
  Flame,
  Lock,
  Map,
  Medal,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Swords,
  Target,
  Trophy,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import strategistCharacter from '@/assets/game/strategist-character.webp'
import { GameButton } from '@/components/game/game-button'
import { AnimatedGameCard, GameCard, GlowCard } from '@/components/game/game-card'
import { Alert } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { analyticsApi } from '@/lib/api/analytics'
import { ApiError } from '@/lib/api/client'
import { gameApi } from '@/lib/api/game'
import { studyApi } from '@/lib/api/study'
import type { DailyBoard, GameProfile, League, TerritoryMap } from '@/lib/api/types'
import { queryKeys } from '@/lib/query-client'
import { firstName, greeting } from '@/lib/utils'
import { useAuth } from '@/providers/auth-provider'
import { MissionPanel } from '@/features/study/mission'
import { SprintDialog } from '@/features/study/sprint-dialog'
import { formatMinutes } from '@/features/study/helpers'
import { CountUp } from '@/features/game/components/xp-bar'

function SetupStep({
  done,
  locked,
  title,
  description,
  action,
}: {
  done?: boolean
  locked?: boolean
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <li className="flex items-start gap-3 border-b border-white/[0.07] py-4 last:border-0">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-white/[0.045]">
        {done ? (
          <Check className="size-4 text-success" />
        ) : locked ? (
          <Lock className="size-4 text-slate-600" />
        ) : (
          <Circle className="size-4 text-game-purple-light" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold text-white">{title}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">{description}</p>
      </div>
      {action}
    </li>
  )
}

const statTone = {
  orange: 'from-game-orange/18 border-game-orange/25 text-game-orange',
  purple: 'from-game-purple/18 border-game-purple/25 text-game-purple-light',
  cyan: 'from-game-cyan/18 border-game-cyan/25 text-game-cyan',
  gold: 'from-game-gold/18 border-game-gold/25 text-game-gold',
}

function StatCard({
  icon: Icon,
  value,
  label,
  detail,
  tone,
  delay,
}: {
  icon: LucideIcon
  value: ReactNode
  label: string
  detail?: string
  tone: keyof typeof statTone
  delay: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.34, delay }}
      className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br ${statTone[tone]} to-transparent p-4`}
    >
      <div className="relative z-10 flex items-center gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-current/10">
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="game-number truncate text-2xl">{value}</p>
          <p className="game-label mt-0.5 truncate text-[9px]">{label}</p>
          {detail && <p className="mt-1 truncate text-[10px] text-slate-500">{detail}</p>}
        </div>
      </div>
    </motion.div>
  )
}

function SectionTitle({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string
  title: string
  action?: ReactNode
}) {
  return (
    <div className="relative z-10 flex items-end justify-between gap-3">
      <div>
        {eyebrow && <p className="game-label text-game-purple-light">{eyebrow}</p>}
        <h2 className="mt-1 text-lg font-extrabold tracking-tight text-white">{title}</h2>
      </div>
      {action}
    </div>
  )
}

function CharacterCard({ profile }: { profile?: GameProfile }) {
  return (
    <GlowCard className="min-h-[340px] border-game-purple/30">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_78%_28%,rgb(124_58_237/0.24),transparent_34%)]" />
      <img
        src={strategistCharacter}
        alt="Estrategista do conhecimento"
        className="absolute right-[-12%] bottom-0 h-[96%] w-[78%] object-contain object-bottom drop-shadow-[0_12px_30px_rgb(0_0_0/0.5)]"
      />
      <div className="relative z-10 flex min-h-[340px] max-w-[54%] flex-col p-5">
        <p className="game-label text-game-purple-light">Sua evolução</p>
        {profile ? (
          <>
            <p className="game-number mt-4 text-5xl">{profile.level.level}</p>
            <p className="mt-1 text-xs font-black tracking-[0.18em] text-game-gold uppercase">
              Nível atual
            </p>
            <span className="mt-5 w-fit rounded-lg border border-game-gold/30 bg-game-gold/10 px-3 py-1.5 text-xs font-extrabold text-game-gold uppercase">
              {profile.rank.name}
            </span>
            <div className="mt-auto pb-4">
              <div className="flex items-center justify-between text-[10px] font-bold text-slate-400">
                <span>{profile.level.xp_into_level.toLocaleString('pt-BR')} XP</span>
                <span>{profile.level.xp_for_next?.toLocaleString('pt-BR') ?? 'Máx.'}</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-game-purple via-game-purple-light to-game-blue shadow-[0_0_10px_rgb(168_85_247/0.6)]"
                  style={{ width: `${Math.round(profile.level.ratio * 100)}%` }}
                />
              </div>
            </div>
          </>
        ) : (
          <div className="mt-5 space-y-3">
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-4 w-28" />
          </div>
        )}
      </div>
    </GlowCard>
  )
}

function NextLevelCard({ profile, board }: { profile?: GameProfile; board?: DailyBoard }) {
  const next = profile && !profile.level.is_max ? profile.level.level + 1 : null
  const missions = board?.missions.slice(0, 3) ?? []
  return (
    <GameCard className="p-5">
      <SectionTitle
        eyebrow="Próximo nível"
        title={next ? `Nível ${next}` : profile ? 'Nível máximo' : 'Sincronizando'}
        action={<Trophy className="size-6 text-game-gold" />}
      />
      {profile && !profile.level.is_max && (
        <p className="relative z-10 mt-2 text-xs text-slate-500">
          Faltam{' '}
          {((profile.level.xp_for_next ?? 0) - profile.level.xp_into_level).toLocaleString(
            'pt-BR',
          )}{' '}
          XP.
        </p>
      )}
      <div className="relative z-10 mt-4 space-y-3">
        {missions.map((mission) => (
          <div key={mission.public_id}>
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate font-semibold text-slate-300">{mission.title}</span>
              <span className="shrink-0 font-bold text-game-purple-light">
                +{mission.xp_reward} XP
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-game-purple to-game-blue"
                style={{ width: `${Math.round(mission.progress_ratio * 100)}%` }}
              />
            </div>
            <p className="mt-1 text-[10px] text-slate-600">
              {mission.current_value.toLocaleString('pt-BR')} /{' '}
              {mission.target_value.toLocaleString('pt-BR')}
            </p>
          </div>
        ))}
        {board && missions.length === 0 && (
          <p className="rounded-xl border border-dashed border-white/10 p-4 text-xs leading-relaxed text-slate-500">
            {board.empty_reason ?? 'Nenhuma missão de XP disponível agora.'}
          </p>
        )}
      </div>
    </GameCard>
  )
}

function StreakCard({ profile }: { profile?: GameProfile }) {
  const days = profile?.streak.history.slice(-7) ?? []
  return (
    <GameCard tone="gold" className="p-5">
      <div className="relative z-10 flex items-center gap-4">
        <span className="grid size-16 shrink-0 place-items-center rounded-2xl bg-game-orange/12 shadow-[0_0_22px_rgb(249_115_22/0.12)]">
          <Flame className="size-9 animate-[pulse_2.4s_ease-in-out_infinite] text-game-orange" />
        </span>
        <div>
          <p className="game-number text-4xl">{profile?.streak.current ?? '—'}</p>
          <p className="game-label text-game-orange">Dias de sequência</p>
        </div>
      </div>
      <div className="relative z-10 mt-5 grid grid-cols-7 gap-1.5">
        {days.map((day) => (
          <div key={day.day} className="text-center">
            <span
              className={`mx-auto grid size-7 place-items-center rounded-lg ${
                day.qualified
                  ? 'bg-game-orange/18 text-game-orange'
                  : day.shielded
                    ? 'bg-game-cyan/15 text-game-cyan'
                    : 'bg-white/[0.045] text-slate-700'
              }`}
            >
              {day.qualified ? (
                <Flame className="size-3.5" />
              ) : day.shielded ? (
                <ShieldCheck className="size-3.5" />
              ) : (
                <Circle className="size-3" />
              )}
            </span>
            <span className="mt-1 block text-[9px] font-bold text-slate-600 uppercase">
              {new Date(`${day.day}T00:00:00`).toLocaleDateString('pt-BR', {
                weekday: 'narrow',
              })}
            </span>
          </div>
        ))}
      </div>
      {profile && (
        <p className="relative z-10 mt-4 text-xs leading-relaxed text-slate-500">
          {profile.streak.message}
        </p>
      )}
    </GameCard>
  )
}

function TerritoryCard({ map }: { map?: TerritoryMap }) {
  const territories = map?.territories ?? []
  const coverage = territories.length
    ? Math.round(
        (territories.reduce((sum, item) => sum + item.mastery, 0) / territories.length) * 100,
      )
    : null
  const tone: Record<string, string> = {
    MASTERED: 'from-game-purple to-game-blue border-game-purple/35',
    STUDYING: 'from-game-blue to-game-cyan border-game-blue/35',
    STARTED: 'from-emerald-600 to-success border-success/30',
    NEEDS_REVIEW: 'from-game-gold to-game-orange border-game-gold/35',
    LOCKED: 'from-slate-700 to-slate-800 border-white/10',
  }
  return (
    <AnimatedGameCard delay={0.18} className="p-5 sm:p-6">
      <SectionTitle
        eyebrow="Domínio estratégico"
        title="Mapa do edital"
        action={
          <GameButton asChild variant="ghost" size="sm">
            <Link to="/jornada">
              Explorar mapa <ArrowRight />
            </Link>
          </GameButton>
        }
      />
      {territories.length > 0 ? (
        <div className="relative z-10 mt-5 grid gap-4 lg:grid-cols-[150px_1fr]">
          <div className="grid place-items-center rounded-2xl border border-game-purple/20 bg-game-purple/8 p-5">
            <div className="relative grid size-24 place-items-center rounded-full border-[7px] border-game-purple/20 shadow-[inset_0_0_22px_rgb(124_58_237/0.18),0_0_28px_rgb(124_58_237/0.12)]">
              <span className="game-number text-3xl">{coverage}%</span>
            </div>
            <p className="game-label mt-3 text-center">Cobertura geral</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {territories.slice(0, 6).map((territory) => (
              <Link
                to="/jornada"
                key={territory.subject_key}
                title={territory.note}
                className={`group relative min-h-24 overflow-hidden rounded-xl border bg-gradient-to-br p-3 transition hover:-translate-y-0.5 hover:brightness-110 ${tone[territory.state]}`}
              >
                <Map className="absolute right-2 bottom-2 size-10 text-white/[0.08]" />
                <p className="relative z-10 truncate text-xs font-extrabold text-white">
                  {territory.subject_name}
                </p>
                <p className="relative z-10 mt-2 text-2xl font-black text-white">
                  {Math.round(territory.mastery * 100)}%
                </p>
                <p className="relative z-10 mt-1 text-[9px] font-bold tracking-wider text-white/60 uppercase">
                  {territory.state === 'MASTERED'
                    ? 'Dominado'
                    : territory.state === 'NEEDS_REVIEW'
                      ? 'Revisar'
                      : territory.state === 'LOCKED'
                        ? 'Não iniciado'
                        : 'Em progresso'}
                </p>
              </Link>
            ))}
          </div>
        </div>
      ) : (
        <div className="relative z-10 mt-5 rounded-2xl border border-dashed border-white/10 p-8 text-center">
          <Map className="mx-auto size-8 text-slate-600" />
          <p className="mt-3 text-sm font-bold text-slate-300">
            Seu mapa ainda não foi revelado
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {map?.empty_reason ?? 'Monte um plano para transformar disciplinas em territórios.'}
          </p>
        </div>
      )}
    </AnimatedGameCard>
  )
}

function LeagueCard({ league }: { league?: League }) {
  return (
    <AnimatedGameCard delay={0.22} className="p-5 sm:p-6">
      <SectionTitle
        eyebrow={league?.context_label ?? 'Competição saudável'}
        title="Liga dos concurseiros"
        action={
          <GameButton asChild variant="ghost" size="sm">
            <Link to="/temporada">
              Ranking <ChevronRight />
            </Link>
          </GameButton>
        }
      />
      {league && league.members.length > 0 ? (
        <div className="relative z-10 mt-5 space-y-2">
          {league.members.slice(0, 5).map((member) => (
            <div
              key={member.position}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 ${member.is_you ? 'border-game-purple/35 bg-game-purple/12 shadow-[0_0_18px_rgb(124_58_237/0.1)]' : 'border-white/[0.06] bg-white/[0.025]'}`}
            >
              <span
                className={`grid size-8 shrink-0 place-items-center rounded-lg text-xs font-black ${member.position <= 3 ? 'bg-game-gold/12 text-game-gold' : 'bg-white/5 text-slate-500'}`}
              >
                {member.position}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-bold text-slate-300">
                {member.label}
                {member.is_you && (
                  <span className="ml-2 text-[9px] text-game-purple-light uppercase">Você</span>
                )}
              </span>
              <span className="text-xs font-extrabold text-white tabular-nums">
                {member.seasonal_xp.toLocaleString('pt-BR')} XP
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="relative z-10 mt-5 rounded-xl border border-dashed border-white/10 p-5 text-sm text-slate-500">
          {league?.empty_reason ??
            'O ranking aparecerá quando existir uma liga ativa para o seu contexto.'}
        </p>
      )}
    </AnimatedGameCard>
  )
}

const quickActions = [
  {
    label: 'Fazer simulado',
    to: '/simulados',
    icon: Swords,
    tone: 'text-game-purple-light bg-game-purple/12 border-game-purple/20',
  },
  {
    label: 'Resolver questões',
    to: '/questoes',
    icon: Target,
    tone: 'text-game-cyan bg-game-cyan/10 border-game-cyan/20',
  },
  {
    label: 'Revisar flashcards',
    to: '/revisao',
    icon: BrainCircuit,
    tone: 'text-success bg-success/10 border-success/20',
  },
  {
    label: 'Ver meus erros',
    to: '/meus-erros',
    icon: AlertTriangle,
    tone: 'text-danger bg-danger/10 border-danger/20',
  },
  {
    label: 'Batalha da banca',
    to: '/voce-vs-banca',
    icon: Crosshair,
    tone: 'text-game-gold bg-game-gold/10 border-game-gold/20',
  },
]

export function TodayPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const mission = useQuery({
    queryKey: queryKeys.studyToday(),
    queryFn: () => studyApi.today(),
    retry: false,
  })
  const weekMinutes = useQuery({
    queryKey: queryKeys.studyWeekMinutes,
    queryFn: studyApi.weekMinutes,
    enabled: mission.isSuccess,
  })
  const profile = useQuery({ queryKey: queryKeys.gameProfile, queryFn: gameApi.profile })
  const board = useQuery({ queryKey: queryKeys.gameMissions, queryFn: gameApi.missionsToday })
  const territory = useQuery({ queryKey: queryKeys.gameTerritory, queryFn: gameApi.territory })
  const league = useQuery({ queryKey: queryKeys.gameLeague, queryFn: gameApi.league })
  const analytics = useQuery({
    queryKey: queryKeys.analyticsOverview,
    queryFn: analyticsApi.overview,
  })

  const rebalance = useMutation({
    mutationFn: studyApi.rebalance,
    onSuccess: (result) => {
      toast.success(result.summary)
      queryClient.invalidateQueries({ queryKey: ['study'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível replanejar.'),
  })

  if (!user) return null
  const hasNoPlan =
    mission.isError &&
    mission.error instanceof ApiError &&
    mission.error.code === 'no_active_plan'
  const game = profile.data
  const territories = territory.data?.territories ?? []
  const domain = territories.length
    ? Math.round(
        (territories.reduce((sum, item) => sum + item.mastery, 0) / territories.length) * 100,
      )
    : null
  const aiStep = analytics.data?.path.steps[0]

  return (
    <div className="space-y-5">
      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-end justify-between gap-4 py-1"
      >
        <div>
          <p className="game-label text-game-purple-light">Central de campanha</p>
          <h1 className="mt-2 text-3xl font-black tracking-[-0.04em] text-white sm:text-4xl">
            {greeting()},{' '}
            <span className="game-gradient-text">{firstName(user.full_name)}</span>.
          </h1>
          <p className="mt-2 text-sm text-slate-500">Seu próximo nível te espera.</p>
        </div>
        <div className="flex items-center gap-3">
          {game && (
            <div className="flex items-center gap-3 rounded-2xl border border-game-orange/20 bg-game-orange/8 px-4 py-2.5">
              <Flame className="size-6 text-game-orange" />
              <div>
                <p className="game-label text-[9px] text-game-orange">Sequência ativa</p>
                <p className="text-base font-black text-white">{game.streak.current} dias</p>
              </div>
            </div>
          )}
          {mission.isSuccess && <SprintDialog />}
        </div>
      </motion.header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={Flame}
          value={game ? <CountUp value={game.streak.current} /> : '—'}
          label="Dias de foco"
          detail={game ? `Recorde: ${game.streak.longest}` : undefined}
          tone="orange"
          delay={0.04}
        />
        <StatCard
          icon={ShieldCheck}
          value={domain === null ? '—' : `${domain}%`}
          label="Domínio geral"
          detail={
            territories.length ? `${territories.length} territórios medidos` : 'Sem mapa ainda'
          }
          tone="purple"
          delay={0.08}
        />
        <StatCard
          icon={Crosshair}
          value={
            game?.master_score === null || game?.master_score === undefined ? (
              '—'
            ) : (
              <CountUp value={game.master_score} />
            )
          }
          label="Mestre Score"
          detail={game?.master_score_note}
          tone="cyan"
          delay={0.12}
        />
        <StatCard
          icon={Medal}
          value={game?.rank.name ?? '—'}
          label="Rank atual"
          detail={game ? `${Math.round(game.rank.score * 100)}% de score` : undefined}
          tone="gold"
          delay={0.16}
        />
      </div>

      {mission.data?.overdue_count ? (
        <Alert
          tone="warning"
          title={`${mission.data.overdue_count} tarefa(s) pedem replanejamento`}
        >
          <p>O plano redistribui apenas o que cabe na sua disponibilidade real.</p>
          <GameButton
            variant="ghost"
            size="sm"
            className="mt-3"
            loading={rebalance.isPending}
            onClick={() => rebalance.mutate()}
          >
            <RefreshCw /> Replanejar agora
          </GameButton>
        </Alert>
      ) : null}

      <div className="grid items-start gap-5 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          {mission.isLoading && (
            <GameCard className="p-6">
              <Skeleton className="h-7 w-52" />
              <Skeleton className="mt-5 h-20 w-full" />
              <Skeleton className="mt-3 h-20 w-full" />
            </GameCard>
          )}

          {hasNoPlan && (
            <GlowCard className="p-6">
              <SectionTitle eyebrow="Primeira missão" title="Monte sua campanha de estudos" />
              <p className="relative z-10 mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
                A missão diária nasce do seu concurso, edital e disponibilidade. Comece com
                dados reais para desbloquear o mapa.
              </p>
              <ul className="relative z-10 mt-5">
                <SetupStep
                  done
                  title="Conta criada"
                  description={`Membro desde ${new Date(user.created_at).toLocaleDateString('pt-BR')}.`}
                />
                <SetupStep
                  done={Boolean(user.email_verified_at)}
                  title="E-mail confirmado"
                  description={
                    user.email_verified_at
                      ? 'Identidade confirmada.'
                      : 'Confirme seu e-mail para liberar todos os recursos.'
                  }
                />
                <SetupStep
                  title="Montar plano de estudo"
                  description="Escolha o cargo e informe sua disponibilidade real."
                  action={
                    <GameButton asChild size="sm">
                      <Link to="/plano/novo">
                        Iniciar jornada <ChevronRight />
                      </Link>
                    </GameButton>
                  }
                />
              </ul>
            </GlowCard>
          )}

          {mission.isError && !hasNoPlan && (
            <Alert tone="danger" title="Não foi possível carregar sua missão">
              Tente recarregar a página em instantes.
            </Alert>
          )}
          {mission.data && <MissionPanel mission={mission.data} />}

          <AnimatedGameCard delay={0.14} className="p-5 sm:p-6">
            <SectionTitle eyebrow="Treinamento" title="Ações rápidas" />
            <div className="relative z-10 mt-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              {quickActions.map((action) => (
                <Link
                  key={action.to}
                  to={action.to}
                  className={`group flex min-h-28 flex-col justify-between rounded-2xl border p-4 transition hover:-translate-y-1 hover:brightness-110 ${action.tone}`}
                >
                  <action.icon className="size-7 transition-transform group-hover:scale-110" />
                  <span className="mt-4 text-xs font-black tracking-[0.06em] text-white uppercase">
                    {action.label}
                  </span>
                </Link>
              ))}
            </div>
          </AnimatedGameCard>

          <div className="grid gap-5 xl:grid-cols-2">
            <GameCard className="p-5 sm:p-6">
              <SectionTitle
                eyebrow="Desempenho real"
                title="Estatísticas de campanha"
                action={
                  <GameButton asChild variant="ghost" size="sm">
                    <Link to="/analytics">
                      Detalhes <ArrowRight />
                    </Link>
                  </GameButton>
                }
              />
              <div className="relative z-10 mt-5 grid grid-cols-2 gap-3">
                {[
                  [
                    'Questões',
                    Math.round(game?.metrics.questions_answered ?? 0).toLocaleString('pt-BR'),
                    'resolvidas',
                  ],
                  [
                    'Acertos',
                    (game?.metrics.questions_answered ?? 0) > 0
                      ? `${Math.round((game?.metrics.accuracy ?? 0) * 100)}%`
                      : '—',
                    'desempenho',
                  ],
                  [
                    'Horas',
                    `${(game?.metrics.focus_hours ?? 0).toString().replace('.', ',')}h`,
                    'foco registrado',
                  ],
                  [
                    'Revisões',
                    Math.round(game?.metrics.flashcard_reviews ?? 0).toLocaleString('pt-BR'),
                    'flashcards',
                  ],
                ].map(([label, value, detail]) => (
                  <div
                    key={label}
                    className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4"
                  >
                    <p className="game-label text-[9px]">{label}</p>
                    <p className="game-number mt-2 text-2xl">{value}</p>
                    <p className="mt-1 text-[10px] text-slate-600">{detail}</p>
                  </div>
                ))}
              </div>
              <div className="relative z-10 mt-3 flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.025] px-4 py-3 text-xs text-slate-500">
                <span className="flex items-center gap-2">
                  <Clock3 className="size-4 text-game-cyan" /> Últimos 7 dias
                </span>
                <span className="font-bold text-white">
                  {weekMinutes.isLoading ? '…' : formatMinutes(weekMinutes.data?.minutes ?? 0)}
                </span>
              </div>
            </GameCard>
            <LeagueCard league={league.data} />
          </div>

          <TerritoryCard map={territory.data} />
        </div>

        <aside className="space-y-5 2xl:sticky 2xl:top-[94px]">
          <CharacterCard profile={game} />
          <NextLevelCard profile={game} board={board.data} />
          <StreakCard profile={game} />
          <GameCard tone="blue" className="p-5">
            <SectionTitle
              eyebrow="Seu assistente de combate"
              title="Mestre IA"
              action={<Sparkles className="size-6 text-game-cyan" />}
            />
            <div className="relative z-10 mt-4 flex gap-3 rounded-xl border border-game-cyan/15 bg-game-cyan/[0.06] p-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-game-cyan/12 text-game-cyan">
                <BrainCircuit className="size-5" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-bold text-white">
                  {aiStep?.subject_name ?? 'Estratégia personalizada'}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">
                  {aiStep?.action ??
                    'Converse com o Mestre IA para analisar seu próximo movimento.'}
                </p>
                {aiStep?.evidence && (
                  <p className="mt-2 text-[10px] leading-relaxed text-game-cyan/70">
                    Base: {aiStep.evidence}
                  </p>
                )}
              </div>
            </div>
            <GameButton asChild variant="action" className="relative z-10 mt-4 w-full">
              <Link to="/mestre-ia">
                Conversar <ArrowRight />
              </Link>
            </GameButton>
          </GameCard>
          <div className="grid grid-cols-2 gap-3">
            <GameButton asChild variant="ghost" size="sm">
              <Link to="/plano">
                <Target /> Plano
              </Link>
            </GameButton>
            <GameButton asChild variant="ghost" size="sm">
              <Link to="/calendario">
                <CalendarDays /> Agenda
              </Link>
            </GameButton>
          </div>
        </aside>
      </div>
    </div>
  )
}
