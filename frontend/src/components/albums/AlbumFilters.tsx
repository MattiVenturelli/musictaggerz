import { useState, useEffect } from 'react'
import { Search, Tag, SkipForward, X, CheckSquare, Square } from 'lucide-react'
import type { AlbumStatus } from '@/types'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useDebounce } from '@/hooks'
import { cn, getStatusColor, getStatusLabel } from '@/utils'

const statuses: (AlbumStatus | '')[] = ['', 'pending', 'matching', 'tagged', 'needs_review', 'failed', 'skipped']

const sortOptions = [
  { value: 'updated_desc', label: 'Recently Updated' },
  { value: 'created_desc', label: 'Recently Added' },
  { value: 'artist', label: 'Artist A-Z' },
  { value: 'album', label: 'Album A-Z' },
  { value: 'confidence_desc', label: 'Confidence High-Low' },
  { value: 'confidence_asc', label: 'Confidence Low-High' },
]

export function AlbumFilters() {
  const { filters, setFilters, selectedIds, selectAll, clearSelection, batchTag, batchSkip } = useAlbumStore()
  const [searchInput, setSearchInput] = useState(filters.search || '')
  const debouncedSearch = useDebounce(searchInput)

  useEffect(() => {
    if (debouncedSearch !== (filters.search || '')) {
      setFilters({ search: debouncedSearch || undefined })
    }
  }, [debouncedSearch])

  const hasSelection = selectedIds.size > 0

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-subtle" />
          <input
            type="text"
            placeholder="Search artists or albums..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-surface-100 border border-surface-400 rounded-lg text-sm text-text placeholder:text-text-subtle focus:outline-none focus:border-accent-blue transition-colors"
          />
          {searchInput && (
            <button
              onClick={() => setSearchInput('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-text-subtle hover:text-text"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Sort */}
        <select
          value={filters.sort || 'updated_desc'}
          onChange={(e) => setFilters({ sort: e.target.value })}
          className="bg-surface-100 border border-surface-400 rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent-blue cursor-pointer"
        >
          {sortOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Status pills */}
      <div className="flex flex-wrap items-center gap-2">
        {statuses.map((status) => (
          <button
            key={status || 'all'}
            onClick={() => setFilters({ status })}
            className={cn(
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              (filters.status || '') === status
                ? status
                  ? getStatusColor(status)
                  : 'bg-accent-blue/20 text-accent-blue'
                : 'bg-surface-400/50 text-text-muted hover:text-text'
            )}
          >
            {status ? getStatusLabel(status) : 'All'}
          </button>
        ))}
      </div>

      {/* Batch actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={hasSelection ? clearSelection : selectAll}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-text-muted hover:text-text rounded-lg hover:bg-surface-400/50 transition-colors"
        >
          {hasSelection ? <CheckSquare className="h-3.5 w-3.5" /> : <Square className="h-3.5 w-3.5" />}
          {hasSelection ? `${selectedIds.size} selected` : 'Select all'}
        </button>
        {hasSelection && (
          <>
            <button
              onClick={batchTag}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent-green/15 text-accent-green rounded-lg hover:bg-accent-green/25 transition-colors"
            >
              <Tag className="h-3.5 w-3.5" />
              Tag Selected
            </button>
            <button
              onClick={batchSkip}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-500/30 text-text-muted rounded-lg hover:bg-surface-500/50 transition-colors"
            >
              <SkipForward className="h-3.5 w-3.5" />
              Skip Selected
            </button>
          </>
        )}
      </div>
    </div>
  )
}
