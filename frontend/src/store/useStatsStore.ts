import { create } from 'zustand'
import type { StatsResponse, ActivityLogResponse } from '@/types'
import * as api from '@/services/api'

interface StatsState {
  stats: StatsResponse | null
  loading: boolean
  fetchStats: () => Promise<void>
}

export const useStatsStore = create<StatsState>((set) => ({
  stats: null,
  loading: false,

  fetchStats: async () => {
    set({ loading: true })
    try {
      const stats = await api.fetchStats()
      set({ stats })
    } finally {
      set({ loading: false })
    }
  },
}))
