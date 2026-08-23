import * as AvatarPrimitive from '@radix-ui/react-avatar'
import { cn } from '@/lib/utils'
import { initials } from '@/lib/utils'

export function Avatar({
  name,
  src,
  className,
}: {
  name: string
  src?: string | null
  className?: string
}) {
  return (
    <AvatarPrimitive.Root
      className={cn(
        'inline-flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full',
        className,
      )}
    >
      {src && <AvatarPrimitive.Image src={src} alt={name} className="size-full object-cover" />}
      <AvatarPrimitive.Fallback className="ai-gradient flex size-full items-center justify-center text-xs font-semibold text-white">
        {initials(name)}
      </AvatarPrimitive.Fallback>
    </AvatarPrimitive.Root>
  )
}
