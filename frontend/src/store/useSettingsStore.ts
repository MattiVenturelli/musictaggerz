import { create } from 'zustand'
import type { SettingResponse } from '@/types'
import * as api from '@/services/api'

interface SettingsState {
  settings: SettingResponse[]
  loading: boolean
  saving: boolean
  fetchSettings: () => Promise<void>
  updateSettings: (values: Record<string, string>) => Promise<void>
  getValue: (key: string) => string
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: [],
  loading: false,
  saving: false,

  fetchSettings: async () => {
    set({ loading: true })
    try {
      const settings = await api.fetchSettings()
      set({ settings })
    } finally {
      set({ loading: false })
    }
  },

  updateSettings: async (values) => {
    set({ saving: true })
    try {
      await api.updateSettings(values)
      await get().fetchSettings()
    } finally {
      set({ saving: false })
    }
  },

  getValue: (key) => {
    const setting = get().settings.find((s) => s.key === key)
    return setting?.value ?? ''
  },
}))
