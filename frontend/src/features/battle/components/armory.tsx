import { Lock, Shield, Sparkles, Sword } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { GameButton } from '@/components/game/game-button'
import { cn } from '@/lib/utils'
import type {
  BattleArmory,
  BattleClass,
  BattleEquipment,
  BattleEquipmentSlot,
  BattleModifiers,
} from '@/lib/api/types'
import { modifierSummary } from '../modifiers'

const SLOT_ICON: Record<BattleEquipmentSlot, LucideIcon> = {
  WEAPON: Sword,
  ARMOR: Shield,
  TRINKET: Sparkles,
}

const SLOT_LABEL: Record<BattleEquipmentSlot, string> = {
  WEAPON: 'Arma',
  ARMOR: 'Armadura',
  TRINKET: 'Amuleto',
}

function ModifierLine({ modifiers }: { modifiers: BattleModifiers }) {
  return <span className="text-xs text-subtle">{modifierSummary(modifiers)}</span>
}

/**
 * O arsenal: classe e três peças.
 *
 * A linha que o painel inteiro respeita, e que o rodapé repete em voz alta:
 * **classe e equipamento mudam o combate, nunca a medição.** Eles não escolhem
 * questão, não mexem na dificuldade e não destravam conteúdo. O que dá XP,
 * limpa um estágio de campanha e ordena o ranking continua sendo a taxa de
 * acerto — a mesma com e sem armadura.
 */
export function ArmoryPanel({
  armory,
  onSave,
  saving,
  draft,
  onDraft,
}: {
  armory: BattleArmory
  onSave: () => void
  saving: boolean
  draft: {
    class_slug: string
    weapon_slug: string
    armor_slug: string
    trinket_slug: string
  }
  onDraft: (next: Partial<typeof draft>) => void
}) {
  const bySlot = (slot: BattleEquipmentSlot) =>
    armory.equipment.filter((item) => item.slot === slot)

  const chosen: Record<BattleEquipmentSlot, string> = {
    WEAPON: draft.weapon_slug,
    ARMOR: draft.armor_slug,
    TRINKET: draft.trinket_slug,
  }

  const pick = (slot: BattleEquipmentSlot, slug: string) =>
    onDraft(
      slot === 'WEAPON'
        ? { weapon_slug: slug }
        : slot === 'ARMOR'
          ? { armor_slug: slug }
          : { trinket_slug: slug },
    )

  const dirty =
    draft.class_slug !== armory.loadout.class_slug ||
    draft.weapon_slug !== armory.loadout.weapon_slug ||
    draft.armor_slug !== armory.loadout.armor_slug ||
    draft.trinket_slug !== armory.loadout.trinket_slug

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-black tracking-wide uppercase">Classe</h3>
          <p className="text-xs text-subtle">
            Livre para qualquer candidato — nenhuma se destrava por nível, liga ou pagamento.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {armory.classes.map((item: BattleClass) => {
            const active = draft.class_slug === item.slug
            return (
              <button
                key={item.slug}
                type="button"
                onClick={() => onDraft({ class_slug: item.slug })}
                aria-pressed={active}
                className={cn(
                  'rounded-xl border p-3 text-left transition-colors',
                  'focus-visible:outline-2 focus-visible:outline-offset-2',
                  'focus-visible:outline-game-purple-light',
                  active
                    ? 'border-game-purple bg-game-purple/[0.08]'
                    : 'border-white/10 hover:border-game-purple/40',
                )}
              >
                <span className="block text-sm font-bold">{item.name}</span>
                <span className="block text-xs text-muted">{item.description}</span>
                <span className="mt-1 block text-xs font-semibold text-game-gold">
                  {item.tradeoff}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      {(Object.keys(SLOT_LABEL) as BattleEquipmentSlot[]).map((slot) => {
        const Icon = SLOT_ICON[slot]
        return (
          <section key={slot} className="space-y-3">
            <h3 className="flex items-center gap-2 text-sm font-black tracking-wide uppercase">
              <Icon className="size-4 text-game-gold" aria-hidden />
              {SLOT_LABEL[slot]}
            </h3>
            <div className="grid gap-2 sm:grid-cols-3">
              {bySlot(slot).map((item: BattleEquipment) => {
                const active = chosen[slot] === item.slug
                return (
                  <button
                    key={item.slug}
                    type="button"
                    disabled={!item.is_unlocked}
                    onClick={() => pick(slot, item.slug)}
                    aria-pressed={active}
                    aria-label={
                      item.is_unlocked
                        ? `${item.name}: ${modifierSummary(item.modifiers)}.`
                        : `${item.name}: travado pela conquista ${item.requirement_label}.`
                    }
                    className={cn(
                      'rounded-xl border p-3 text-left transition-colors',
                      'focus-visible:outline-2 focus-visible:outline-offset-2',
                      'focus-visible:outline-game-purple-light',
                      !item.is_unlocked
                        ? 'border-white/[0.06] opacity-60'
                        : active
                          ? 'border-game-purple bg-game-purple/[0.08]'
                          : 'border-white/10 hover:border-game-purple/40',
                    )}
                  >
                    <span className="flex items-center gap-1.5 text-sm font-bold">
                      {!item.is_unlocked && <Lock className="size-3.5" aria-hidden />}
                      {item.name}
                    </span>
                    <span className="block text-xs text-muted">{item.description}</span>
                    <ModifierLine modifiers={item.modifiers} />
                    {!item.is_unlocked && item.requirement_label && (
                      // Peça travada sem caminho é armadilha: o nome da
                      // conquista aparece junto do cadeado.
                      <span className="mt-1 block text-xs text-game-gold">
                        Conquista: {item.requirement_label}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </section>
        )
      })}

      <div className="flex flex-wrap items-center gap-3">
        <GameButton onClick={onSave} loading={saving} disabled={!dirty}>
          Salvar equipamento
        </GameButton>
        <p className="text-xs text-subtle">
          Classe e equipamento mudam o combate, nunca a medição. O XP, os estágios da campanha e
          o ranking continuam saindo da sua taxa de acerto.
        </p>
      </div>
    </div>
  )
}
