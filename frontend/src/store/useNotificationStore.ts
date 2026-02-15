import { create } from 'zustand'

export interface Toast {
  id: string
  level: 'info' | 'success' | 'warning' | 'error'
  message: string
}

interface NotificationState {
  toasts: Toast[]
  wsConnected: boolean
  addToast: (level: Toast['level'], message: string) => void
  removeToast: (id: string) => void
  setWsConnected: (connected: boolean) => void
}

let toastCounter = 0

export const useNotificationStore = create<NotificationState>((set) => ({
  toasts: [],
  wsConnected: false,

  addToast: (level, message) => {
    const id = `toast-${++toastCounter}`
    set((s) => ({ toasts: [...s.toasts, { id, level, message }] }))
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
    }, 5000)
  },

  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  setWsConnected: (connected) => set({ wsConnected: connected }),
}))
