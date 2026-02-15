import { AlertTriangle } from 'lucide-react'

interface Props {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', onConfirm, onCancel }: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />
      <div className="relative bg-surface-100 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl border border-surface-400">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-accent-yellow mt-0.5 shrink-0" />
          <div>
            <h3 className="text-lg font-semibold text-text">{title}</h3>
            <p className="mt-2 text-sm text-text-muted">{message}</p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-text-muted hover:text-text rounded-lg hover:bg-surface-400 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium bg-accent-red text-surface-300 rounded-lg hover:opacity-90 transition-opacity"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
