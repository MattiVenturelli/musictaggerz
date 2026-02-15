import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/utils'

interface Props {
  total: number
  limit: number
  offset: number
  onPageChange: (offset: number) => void
}

export function Pagination({ total, limit, offset, onPageChange }: Props) {
  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  if (totalPages <= 1) return null

  const pages: number[] = []
  const start = Math.max(1, currentPage - 2)
  const end = Math.min(totalPages, currentPage + 2)
  for (let i = start; i <= end; i++) pages.push(i)

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onPageChange(Math.max(0, offset - limit))}
        disabled={currentPage === 1}
        className="p-1.5 rounded-lg hover:bg-surface-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      {pages.map((page) => (
        <button
          key={page}
          onClick={() => onPageChange((page - 1) * limit)}
          className={cn(
            'min-w-[2rem] h-8 rounded-lg text-sm font-medium transition-colors',
            page === currentPage
              ? 'bg-accent-blue text-surface-300'
              : 'hover:bg-surface-400 text-text-muted'
          )}
        >
          {page}
        </button>
      ))}

      <button
        onClick={() => onPageChange(offset + limit)}
        disabled={currentPage === totalPages}
        className="p-1.5 rounded-lg hover:bg-surface-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronRight className="h-4 w-4" />
      </button>

      <span className="ml-2 text-xs text-text-subtle">
        {total} total
      </span>
    </div>
  )
}
