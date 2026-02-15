import type { TrackResponse } from '@/types'
import { formatDuration } from '@/utils'
import { StatusBadge } from '@/components/common'

interface Props {
  tracks: TrackResponse[]
}

export function TrackList({ tracks }: Props) {
  if (tracks.length === 0) {
    return <p className="text-sm text-text-subtle py-4 text-center">No tracks found</p>
  }

  // Group by disc number
  const discs = new Map<number, TrackResponse[]>()
  tracks.forEach((t) => {
    const disc = t.disc_number || 1
    if (!discs.has(disc)) discs.set(disc, [])
    discs.get(disc)!.push(t)
  })

  const multiDisc = discs.size > 1

  return (
    <div className="space-y-4">
      {[...discs.entries()]
        .sort(([a], [b]) => a - b)
        .map(([discNum, discTracks]) => (
          <div key={discNum}>
            {multiDisc && (
              <h4 className="text-xs font-medium text-text-subtle uppercase tracking-wider mb-2 px-2">
                Disc {discNum}
              </h4>
            )}
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-text-subtle uppercase tracking-wider border-b border-surface-400">
                  <th className="text-right pr-3 py-2 w-10">#</th>
                  <th className="text-left py-2">Title</th>
                  <th className="text-left py-2 hidden sm:table-cell">Artist</th>
                  <th className="text-right py-2 w-16">Duration</th>
                  <th className="text-right py-2 w-20">Status</th>
                </tr>
              </thead>
              <tbody>
                {discTracks
                  .sort((a, b) => (a.track_number || 0) - (b.track_number || 0))
                  .map((track) => (
                    <tr
                      key={track.id}
                      className="border-b border-surface-400/50 hover:bg-surface-400/20 transition-colors"
                    >
                      <td className="text-right pr-3 py-2 text-text-subtle tabular-nums">
                        {track.track_number || '-'}
                      </td>
                      <td className="py-2 text-text truncate max-w-[200px]">
                        {track.title || 'Unknown'}
                      </td>
                      <td className="py-2 text-text-muted truncate max-w-[150px] hidden sm:table-cell">
                        {track.artist || '-'}
                      </td>
                      <td className="text-right py-2 text-text-muted tabular-nums">
                        {formatDuration(track.duration)}
                      </td>
                      <td className="text-right py-2">
                        <StatusBadge status={track.status as any} />
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}
