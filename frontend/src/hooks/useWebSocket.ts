import { useEffect } from 'react'
import { wsService } from '@/services/websocket'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useStatsStore } from '@/store/useStatsStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import type { WSMessage } from '@/types'

export function useWebSocket() {
  const handleAlbumUpdate = useAlbumStore((s) => s.handleAlbumUpdate)
  const handleProgress = useAlbumStore((s) => s.handleProgress)
  const fetchAlbums = useAlbumStore((s) => s.fetchAlbums)
  const fetchStats = useStatsStore((s) => s.fetchStats)
  const addToast = useNotificationStore((s) => s.addToast)
  const setWsConnected = useNotificationStore((s) => s.setWsConnected)

  useEffect(() => {
    wsService.connect()
    setWsConnected(true)

    const unsubscribe = wsService.subscribe((msg: WSMessage) => {
      switch (msg.type) {
        case 'album_update':
          handleAlbumUpdate(msg.album_id, msg.status, msg.confidence)
          fetchStats()
          break
        case 'progress':
          handleProgress(msg.album_id, msg.progress, msg.message)
          break
        case 'notification':
          addToast(msg.level, msg.message)
          break
        case 'scan_update':
          addToast('info', msg.message)
          fetchAlbums()
          fetchStats()
          break
      }
    })

    // Poll connection status
    const interval = setInterval(() => {
      setWsConnected(wsService.isConnected)
    }, 3000)

    return () => {
      unsubscribe()
      clearInterval(interval)
      wsService.disconnect()
      setWsConnected(false)
    }
  }, [handleAlbumUpdate, handleProgress, fetchAlbums, fetchStats, addToast, setWsConnected])
}
