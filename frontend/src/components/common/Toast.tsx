import { X, CheckCircle, AlertTriangle, Info, XCircle } from 'lucide-react'
import type { Toast as ToastType } from '@/store/useNotificationStore'
import { cn } from '@/utils'

interface Props {
  toast: ToastType
  onDismiss: (id: string) => void
}

const icons = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
}

const styles = {
  info: 'border-accent-blue/30 bg-accent-blue/10',
  success: 'border-accent-green/30 bg-accent-green/10',
  warning: 'border-accent-yellow/30 bg-accent-yellow/10',
  error: 'border-accent-red/30 bg-accent-red/10',
}

const iconColors = {
  info: 'text-accent-blue',
  success: 'text-accent-green',
  warning: 'text-accent-yellow',
  error: 'text-accent-red',
}

export function Toast({ toast, onDismiss }: Props) {
  const Icon = icons[toast.level]

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border p-3 shadow-lg backdrop-blur-sm animate-in slide-in-from-right',
        styles[toast.level]
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0 mt-0.5', iconColors[toast.level])} />
      <p className="text-sm text-text flex-1">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-text-subtle hover:text-text shrink-0"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
