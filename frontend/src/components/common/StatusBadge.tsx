import type { AlbumStatus } from '@/types'
import { getStatusColor, getStatusLabel, cn } from '@/utils'

interface Props {
  status: AlbumStatus
  className?: string
}

export function StatusBadge({ status, className }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        getStatusColor(status),
        className
      )}
    >
      {getStatusLabel(status)}
    </span>
  )
}
