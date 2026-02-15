import { Disc3 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/utils'

interface Props {
  icon?: LucideIcon
  title: string
  description?: string
  className?: string
  children?: React.ReactNode
}

export function EmptyState({ icon: Icon = Disc3, title, description, className, children }: Props) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
      <Icon className="h-12 w-12 text-text-subtle mb-4" />
      <h3 className="text-lg font-medium text-text mb-1">{title}</h3>
      {description && <p className="text-sm text-text-muted max-w-sm">{description}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}
