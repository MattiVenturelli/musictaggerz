import { clsx, type ClassValue } from 'clsx'
import type { AlbumStatus } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatDuration(seconds: number | null): string {
  if (seconds == null) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function formatConfidence(confidence: number | null): string {
  if (confidence == null) return 'N/A'
  return `${Math.round(confidence)}%`
}

export function getStatusColor(status: AlbumStatus): string {
  const colors: Record<AlbumStatus, string> = {
    pending: 'bg-accent-yellow/20 text-accent-yellow',
    matching: 'bg-accent-blue/20 text-accent-blue',
    tagged: 'bg-accent-green/20 text-accent-green',
    failed: 'bg-accent-red/20 text-accent-red',
    needs_review: 'bg-accent-peach/20 text-accent-peach',
    skipped: 'bg-overlay/20 text-overlay-light',
  }
  return colors[status] || 'bg-overlay/20 text-overlay-light'
}

export function getStatusLabel(status: AlbumStatus): string {
  const labels: Record<AlbumStatus, string> = {
    pending: 'Pending',
    matching: 'Matching',
    tagged: 'Tagged',
    failed: 'Failed',
    needs_review: 'Review',
    skipped: 'Skipped',
  }
  return labels[status] || status
}

export function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString()
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 85) return 'text-accent-green'
  if (confidence >= 50) return 'text-accent-yellow'
  return 'text-accent-red'
}

export function getConfidenceBgColor(confidence: number): string {
  if (confidence >= 85) return 'bg-accent-green'
  if (confidence >= 50) return 'bg-accent-yellow'
  return 'bg-accent-red'
}
