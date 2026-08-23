import { cn } from '@/lib/utils'

const rules = [
  { label: '10+ caracteres', test: (value: string) => value.length >= 10 },
  { label: 'letra maiúscula', test: (value: string) => /[A-Z]/.test(value) },
  { label: 'letra minúscula', test: (value: string) => /[a-z]/.test(value) },
  { label: 'número', test: (value: string) => /\d/.test(value) },
  { label: 'símbolo', test: (value: string) => /[^A-Za-z0-9]/.test(value) },
]

/** Espelha exatamente a política validada no backend. */
export function PasswordStrength({ value }: { value: string }) {
  const passed = rules.filter((rule) => rule.test(value)).length
  const tone =
    passed <= 2 ? 'bg-danger' : passed <= 4 ? 'bg-warning' : 'bg-success'

  return (
    <div className="space-y-2">
      <div className="flex gap-1" aria-hidden>
        {rules.map((rule, index) => (
          <span
            key={rule.label}
            className={cn(
              'h-1 flex-1 rounded-full transition-colors',
              index < passed ? tone : 'bg-border',
            )}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {rules.map((rule) => (
          <li
            key={rule.label}
            className={rule.test(value) ? 'text-success' : 'text-subtle'}
          >
            {rule.test(value) ? '✓' : '○'} {rule.label}
          </li>
        ))}
      </ul>
    </div>
  )
}
