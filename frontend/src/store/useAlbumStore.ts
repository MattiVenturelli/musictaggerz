import { create } from 'zustand'
import type { AlbumSummary, AlbumDetail, AlbumFilters } from '@/types'
import * as api from '@/services/api'

export interface ProgressInfo {
  albumId: number
  progress: number
  message: string
}

interface AlbumState {
  albums: AlbumSummary[]
  total: number
  filters: AlbumFilters
  selectedIds: Set<number>
  currentAlbum: AlbumDetail | null
  loading: boolean
  detailLoading: boolean
  activeProgress: ProgressInfo | null

  setFilters: (filters: Partial<AlbumFilters>) => void
  fetchAlbums: (silent?: boolean) => Promise<void>
  fetchAlbum: (id: number, silent?: boolean) => Promise<void>
  toggleSelect: (id: number) => void
  selectAll: () => void
  clearSelection: () => void

  tagAlbum: (id: number, releaseId?: string) => Promise<void>
  retagAlbum: (id: number, releaseId?: string) => Promise<void>
  skipAlbum: (id: number) => Promise<void>
  deleteAlbum: (id: number) => Promise<void>
  batchTag: () => Promise<void>
  batchSkip: () => Promise<void>
  batchTagPending: () => Promise<void>
  triggerScan: () => Promise<void>

  handleAlbumUpdate: (albumId: number, status: string, confidence?: number) => void
  handleProgress: (albumId: number, progress: number, message: string) => void
}

export const useAlbumStore = create<AlbumState>((set, get) => ({
  albums: [],
  total: 0,
  filters: { sort: 'updated_desc', limit: 50, offset: 0 },
  selectedIds: new Set(),
  currentAlbum: null,
  loading: false,
  detailLoading: false,
  activeProgress: null,

  setFilters: (filters) => {
    set((s) => ({ filters: { ...s.filters, ...filters, offset: filters.offset ?? 0 } }))
    get().fetchAlbums()
  },

  fetchAlbums: async (silent) => {
    if (!silent) set({ loading: true })
    try {
      const res = await api.fetchAlbums(get().filters)
      set({ albums: res.items, total: res.total })
    } finally {
      if (!silent) set({ loading: false })
    }
  },

  fetchAlbum: async (id, silent) => {
    if (!silent) set({ detailLoading: true })
    try {
      const album = await api.fetchAlbum(id)
      set({ currentAlbum: album })
    } finally {
      if (!silent) set({ detailLoading: false })
    }
  },

  toggleSelect: (id) =>
    set((s) => {
      const next = new Set(s.selectedIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selectedIds: next }
    }),

  selectAll: () =>
    set((s) => ({ selectedIds: new Set(s.albums.map((a) => a.id)) })),

  clearSelection: () => set({ selectedIds: new Set() }),

  tagAlbum: async (id, releaseId) => {
    await api.tagAlbum(id, releaseId)
  },

  retagAlbum: async (id, releaseId) => {
    await api.retagAlbum(id, releaseId)
  },

  skipAlbum: async (id) => {
    await api.skipAlbum(id)
    const { currentAlbum } = get()
    if (currentAlbum?.id === id) {
      set({ currentAlbum: { ...currentAlbum, status: 'skipped' } })
    }
    get().fetchAlbums()
  },

  deleteAlbum: async (id) => {
    await api.deleteAlbum(id)
    set((s) => ({
      albums: s.albums.filter((a) => a.id !== id),
      total: s.total - 1,
      currentAlbum: s.currentAlbum?.id === id ? null : s.currentAlbum,
    }))
  },

  batchTag: async () => {
    const ids = [...get().selectedIds]
    if (ids.length === 0) return
    await api.batchTag(ids)
    set({ selectedIds: new Set() })
    get().fetchAlbums()
  },

  batchSkip: async () => {
    const ids = [...get().selectedIds]
    if (ids.length === 0) return
    await api.batchSkip(ids)
    set({ selectedIds: new Set() })
    get().fetchAlbums()
  },

  batchTagPending: async () => {
    await api.batchTagPending()
    get().fetchAlbums()
  },

  triggerScan: async () => {
    await api.triggerScan()
  },

  handleAlbumUpdate: (albumId, status, confidence) => {
    // Patch list in-place for instant feedback
    set((s) => ({
      albums: s.albums.map((a) =>
        a.id === albumId ? { ...a, status: status as AlbumSummary['status'], match_confidence: confidence ?? a.match_confidence } : a
      ),
    }))

    // Clear progress when tagging completes or fails
    const terminal = ['tagged', 'failed', 'skipped', 'needs_review']
    if (terminal.includes(status)) {
      const { activeProgress } = get()
      if (activeProgress?.albumId === albumId) {
        set({ activeProgress: null })
      }
    }

    // If we're viewing this album, silently refetch full detail (tracks, candidates, etc.)
    const { currentAlbum } = get()
    if (currentAlbum?.id === albumId) {
      get().fetchAlbum(albumId, true)
    }

    // Refresh the album list silently (no loading flash)
    get().fetchAlbums(true)
  },

  handleProgress: (albumId, progress, message) => {
    set({ activeProgress: { albumId, progress, message } })
  },
}))
