export interface TrackResponse {
  id: number
  album_id: number
  track_number: number | null
  disc_number: number | null
  title: string | null
  artist: string | null
  duration: number | null
  path: string
  status: string
  error_message: string | null
  musicbrainz_recording_id: string | null
}

export interface MatchCandidateResponse {
  id: number
  musicbrainz_release_id: string
  confidence: number
  artist: string | null
  album: string | null
  year: number | null
  original_year: number | null
  track_count: number | null
  country: string | null
  media: string | null
  label: string | null
  is_selected: boolean
}

export interface AlbumSummary {
  id: number
  path: string
  artist: string | null
  album: string | null
  year: number | null
  status: AlbumStatus
  match_confidence: number | null
  cover_path: string | null
  track_count: number | null
  updated_at: string | null
}

export interface AlbumDetail extends AlbumSummary {
  musicbrainz_release_id: string | null
  cover_url: string | null
  error_message: string | null
  created_at: string | null
  tracks: TrackResponse[]
  match_candidates: MatchCandidateResponse[]
}

export interface AlbumListResponse {
  items: AlbumSummary[]
  total: number
  limit: number
  offset: number
}

export interface StatsResponse {
  total_albums: number
  tagged_count: number
  pending_count: number
  matching_count: number
  needs_review_count: number
  failed_count: number
  skipped_count: number
  queue_size: number
  is_processing: boolean
  recent_activity: ActivityLogResponse[]
}

export interface SettingResponse {
  key: string
  value: string | null
  value_type: string | null
  description: string | null
}

export interface ActivityLogResponse {
  id: number
  album_id: number | null
  action: string
  details: string | null
  timestamp: string | null
}

export type AlbumStatus = 'pending' | 'matching' | 'tagged' | 'failed' | 'needs_review' | 'skipped'

export type WSMessageType = 'album_update' | 'progress' | 'notification' | 'scan_update'

export interface WSAlbumUpdate {
  type: 'album_update'
  album_id: number
  status: AlbumStatus
  artist?: string
  album?: string
  confidence?: number
  error?: string
}

export interface WSProgress {
  type: 'progress'
  album_id: number
  progress: number
  message: string
}

export interface WSNotification {
  type: 'notification'
  level: 'info' | 'success' | 'warning' | 'error'
  message: string
}

export interface WSScanUpdate {
  type: 'scan_update'
  found: number
  message: string
}

export type WSMessage = WSAlbumUpdate | WSProgress | WSNotification | WSScanUpdate

export interface AlbumFilters {
  status?: AlbumStatus | ''
  search?: string
  sort?: string
  limit?: number
  offset?: number
}
