import type { LucideIcon } from 'lucide-react'
import { cn } from '@/utils'

interface Props {
  icon: LucideIcon
  title: string
  value: number
  color?: string
  className?: string
}

export function StatCard({ icon: Icon, title, value, color = 'text-accent-blue', className }: Props) {
  return (
    <div className={cn('bg-surface-100 rounded-xl p-5 border border-surface-400', className)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-muted">{title}</p>
          <p className="text-3xl font-bold text-text mt-1">{value}</p>
        </div>
        <Icon className={cn('h-10 w-10 opacity-60', color)} />
      </div>
    </div>
  )
}
