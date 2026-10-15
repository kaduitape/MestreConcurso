import type { BattleModifiers } from '@/lib/api/types'

const MODIFIER_LABEL: Record<keyof BattleModifiers, string> = {
  damage_percent: 'dano',
  max_hp_percent: 'vida',
  coin_percent: 'moedas',
  power_discount_percent: 'desconto nos poderes',
}

/**
 * Traduz os modificadores em uma frase curta, com sinal.
 *
 * Toda peça declara o que dá **e o que tira**. Mostrar só o bônus faria parecer
 * que existe escolha sem custo, e aí não haveria escolha nenhuma.
 */
export function modifierSummary(modifiers: BattleModifiers): string {
  const parts = (Object.keys(MODIFIER_LABEL) as (keyof BattleModifiers)[])
    .filter((key) => modifiers[key] !== 0)
    // Sinal de menos tipográfico (−), o mesmo que o servidor usa nas trocas das
    // classes: os dois textos aparecem lado a lado no arsenal.
    .map(
      (key) =>
        `${modifiers[key] > 0 ? '+' : '−'}${Math.abs(modifiers[key])}% de ${MODIFIER_LABEL[key]}`,
    )
  return parts.length > 0 ? parts.join(', ') : 'sem alteração no combate'
}
