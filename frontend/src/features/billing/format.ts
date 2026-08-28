/** Formatação de preço da camada comercial, fora do componente. */
export function formatPrice(cents: number, months = 1): string {
  if (cents === 0) return 'Grátis'
  const value = (cents / 100).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
  return months > 1 ? `${value}/ano` : `${value}/mês`
}
