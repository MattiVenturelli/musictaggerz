import axios from 'axios'
import type {
  AlbumListResponse,
  AlbumDetail,
  StatsResponse,
  SettingResponse,
  ActivityLogResponse,
  AlbumFilters,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
})

// Albums
export async function fetchAlbums(filters: AlbumFilters = {}): Promise<AlbumListResponse> {
  const params: Record<string, string | number> = {}
  if (filters.status) params.status = filters.status
  if (filters.search) params.search = filters.search
  if (filters.sort) params.sort = filters.sort
  if (filters.limit != null) params.limit = filters.limit
  if (filters.offset != null) params.offset = filters.offset
  const { data } = await api.get<AlbumListResponse>('/albums', { params })
  return data
}

export async function fetchAlbum(id: number): Promise<AlbumDetail> {
  const { data } = await api.get<AlbumDetail>(`/albums/${id}`)
  return data
}

export async function tagAlbum(id: number, releaseId?: string): Promise<void> {
  await api.post(`/albums/${id}/tag`, releaseId ? { release_id: releaseId } : {})
}

export async function retagAlbum(id: number, releaseId?: string): Promise<void> {
  await api.post(`/albums/${id}/retag`, releaseId ? { release_id: releaseId } : {})
}

export async function skipAlbum(id: number): Promise<void> {
  await api.post(`/albums/${id}/skip`)
}

export async function deleteAlbum(id: number): Promise<void> {
  await api.delete(`/albums/${id}`)
}

export async function batchTag(albumIds: number[]): Promise<void> {
  await api.post('/albums/batch/tag', { album_ids: albumIds })
}

export async function batchSkip(albumIds: number[]): Promise<void> {
  await api.post('/albums/batch/skip', { album_ids: albumIds })
}

export async function batchTagPending(): Promise<void> {
  await api.post('/albums/batch/tag-pending')
}

export async function triggerScan(path?: string, force?: boolean): Promise<void> {
  await api.post('/albums/scan', { path: path || null, force: force || false })
}

// Stats
export async function fetchStats(): Promise<StatsResponse> {
  const { data } = await api.get<StatsResponse>('/stats')
  return data
}

export async function fetchActivity(limit = 50, offset = 0): Promise<ActivityLogResponse[]> {
  const { data } = await api.get<ActivityLogResponse[]>('/stats/activity', {
    params: { limit, offset },
  })
  return data
}

// Settings
export async function fetchSettings(): Promise<SettingResponse[]> {
  const { data } = await api.get<SettingResponse[]>('/settings')
  return data
}

export async function updateSettings(settings: Record<string, string>): Promise<void> {
  await api.put('/settings', { settings })
}

// Track tags
export interface TrackTags {
  track_id: number
  path: string
  title: string | null
  artist: string | null
  album: string | null
  album_artist: string | null
  track_number: number | null
  disc_number: number | null
  year: number | null
  genre: string | null
  duration: number | null
  format: string | null
  has_cover: boolean
  musicbrainz_recording_id: string | null
}

export async function fetchTrackTags(albumId: number, trackId: number): Promise<TrackTags> {
  const { data } = await api.get<TrackTags>(`/albums/${albumId}/tracks/${trackId}/tags`)
  return data
}

// Cover art URL helper
export function getAlbumCoverUrl(albumId: number): string {
  return `/api/albums/${albumId}/cover`
}

export default api
