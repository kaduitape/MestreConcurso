import { useState } from 'react'
import { BookmarkPlus, FileText, Info, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ChatMessage, Claim } from '@/lib/api/types'
import { CLAIM_LABEL, groundingLabel, groundingTone } from './helpers'

function ClaimLine({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false)
  const hasSource = claim.status === 'CITED'

  return (
    <li className="space-y-1">
      <p className="text-sm leading-relaxed">
        {claim.text}{' '}
        {claim.kind !== 'GUIDANCE' && (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className={cn(
              'ml-1 inline-flex translate-y-px items-center gap-1 rounded-full px-2 py-0.5 align-middle text-[11px] font-medium',
              hasSource
                ? 'bg-success-soft text-success hover:brightness-95'
                : 'bg-warning-soft text-warning hover:brightness-95',
            )}
          >
            {hasSource ? (
              <>
                <FileText className="size-3" aria-hidden />
                {claim.document_title}
                {claim.page_number !== null && `, p. ${claim.page_number}`}
              </>
            ) : (
              <>
                <ShieldAlert className="size-3" aria-hidden />
                sem origem
              </>
            )}
          </button>
        )}
      </p>

      {open && (
        <div className="rounded-md border border-border bg-surface-muted p-3 text-xs">
          <p className="font-medium">{CLAIM_LABEL[claim.status]}</p>
          {claim.quote && <p className="mt-1 text-muted italic">“{claim.quote}”</p>}
          {claim.note && <p className="mt-1 text-warning">{claim.note}</p>}
          {!claim.quote && !claim.note && (
            <p className="mt-1 text-muted">
              Este número foi calculado pela plataforma e entregue pronto ao modelo.
            </p>
          )}
        </div>
      )}
    </li>
  )
}

export function MessageBubble({
  message,
  onSaveTerm,
}: {
  message: ChatMessage
  onSaveTerm?: (term: string) => void
}) {
  const [showSources, setShowSources] = useState(false)

  if (message.role === 'USER') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    )
  }

  if (message.is_refusal) {
    return (
      <div className="max-w-[90%] space-y-2 rounded-lg border border-warning bg-warning-soft/30 p-4">
        <p className="flex items-center gap-2 text-sm font-medium">
          <ShieldAlert className="size-4 text-warning" aria-hidden /> Não vou responder isso
        </p>
        <p className="text-sm text-muted">{message.refusal_reason}</p>
      </div>
    )
  }

  const facts = message.claims.filter((claim) => claim.kind !== 'GUIDANCE')

  return (
    <div className="max-w-[90%] space-y-3 rounded-lg border border-border bg-surface p-4">
      <ul className="space-y-2">
        {message.claims.map((claim, index) => (
          <ClaimLine key={`${claim.text}-${index}`} claim={claim} />
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Badge variant={groundingTone(message.grounding_ratio)}>
          <ShieldCheck className="size-3" aria-hidden />
          {groundingLabel(facts.length ? message.grounding_ratio : null)}
        </Badge>
        {message.sources.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setShowSources((value) => !value)}>
            <Info /> {message.sources.length} trecho(s) consultado(s)
          </Button>
        )}
        {onSaveTerm && (
          <Button variant="ghost" size="sm" onClick={() => onSaveTerm('')}>
            <BookmarkPlus /> Guardar termo
          </Button>
        )}
        {message.model_slug && (
          <span className="ml-auto text-xs text-subtle">
            {message.model_slug} · {message.input_tokens + message.output_tokens} tokens
          </span>
        )}
      </div>

      {showSources && (
        <ul className="space-y-2">
          {message.sources.map((source) => (
            <li key={source.chunk_id} className="rounded-md bg-surface-muted p-3 text-xs">
              <p className="font-medium">
                {source.document_title}, p. {source.page_number}
                <span className="ml-2 text-subtle">
                  proximidade {(source.score * 100).toFixed(0)}%
                </span>
              </p>
              <p className="mt-1 text-muted">{source.excerpt}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
