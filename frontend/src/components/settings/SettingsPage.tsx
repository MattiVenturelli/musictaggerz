import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { useSettingsStore } from '@/store/useSettingsStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { LoadingSpinner } from '@/components/common'
import { cn } from '@/utils'

const tabs = [
  { id: 'general', label: 'General' },
  { id: 'matching', label: 'Matching' },
  { id: 'artwork', label: 'Artwork' },
  { id: 'api', label: 'API Keys' },
] as const

type TabId = (typeof tabs)[number]['id']

export function SettingsPage() {
  const { settings, loading, saving, fetchSettings, updateSettings, getValue } = useSettingsStore()
  const addToast = useNotificationStore((s) => s.addToast)
  const [activeTab, setActiveTab] = useState<TabId>('general')
  const [draft, setDraft] = useState<Record<string, string>>({})

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  useEffect(() => {
    const map: Record<string, string> = {}
    settings.forEach((s) => {
      if (s.value != null) map[s.key] = s.value
    })
    setDraft(map)
  }, [settings])

  const updateDraft = (key: string, value: string) => {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  const handleSave = async () => {
    try {
      await updateSettings(draft)
      addToast('success', 'Settings saved')
    } catch {
      addToast('error', 'Failed to save settings')
    }
  }

  if (loading && settings.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Settings</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-accent-blue text-surface-300 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? <LoadingSpinner size="sm" /> : <Save className="h-4 w-4" />}
          Save
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-200 p-1 rounded-lg">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors',
              activeTab === tab.id
                ? 'bg-surface-100 text-text shadow-sm'
                : 'text-text-muted hover:text-text'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-surface-100 rounded-xl border border-surface-400 p-6">
        {activeTab === 'general' && (
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-text mb-1">Automatic Mode</label>
              <p className="text-xs text-text-subtle mb-2">
                When enabled, new albums discovered by scan or file watcher are automatically queued for tagging.
                When disabled (manual mode), albums are added to the library but you must tag them manually.
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => updateDraft('auto_tag_on_scan', draft['auto_tag_on_scan'] === 'true' ? 'false' : 'true')}
                  className={cn(
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    draft['auto_tag_on_scan'] === 'true'
                      ? 'bg-accent-green'
                      : 'bg-surface-400'
                  )}
                >
                  <span
                    className={cn(
                      'inline-block h-4 w-4 rounded-full bg-white transition-transform',
                      draft['auto_tag_on_scan'] === 'true' ? 'translate-x-6' : 'translate-x-1'
                    )}
                  />
                </button>
                <span className="text-sm text-text-muted">
                  {draft['auto_tag_on_scan'] === 'true' ? 'Automatic' : 'Manual'}
                </span>
              </div>
            </div>
            <SettingField
              label="Auto-tag Confidence Threshold"
              description="Albums above this confidence score will be tagged automatically"
              value={draft['confidence_auto_threshold'] || '85'}
              onChange={(v) => updateDraft('confidence_auto_threshold', v)}
              type="number"
            />
            <SettingField
              label="Review Confidence Threshold"
              description="Albums between this and auto-tag threshold will need manual review"
              value={draft['confidence_review_threshold'] || '50'}
              onChange={(v) => updateDraft('confidence_review_threshold', v)}
              type="number"
            />
            <SettingField
              label="Watch Stabilization Delay (seconds)"
              description="How long to wait after detecting new files before processing"
              value={draft['watch_stabilization_delay'] || '30'}
              onChange={(v) => updateDraft('watch_stabilization_delay', v)}
              type="number"
            />
          </div>
        )}

        {activeTab === 'matching' && (
          <div className="space-y-5">
            <SettingField
              label="Preferred Countries"
              description="Comma-separated list of preferred release countries (e.g. US,GB,DE,IT)"
              value={draft['preferred_countries'] || 'US,GB,DE,IT'}
              onChange={(v) => updateDraft('preferred_countries', v)}
            />
            <SettingField
              label="Preferred Media"
              description="Comma-separated list of preferred media formats (e.g. Digital Media,CD)"
              value={draft['preferred_media'] || 'Digital Media,CD'}
              onChange={(v) => updateDraft('preferred_media', v)}
            />
          </div>
        )}

        {activeTab === 'artwork' && (
          <div className="space-y-5">
            <SettingField
              label="Minimum Artwork Size (px)"
              description="Minimum width/height for downloaded artwork"
              value={draft['artwork_min_size'] || '500'}
              onChange={(v) => updateDraft('artwork_min_size', v)}
              type="number"
            />
            <SettingField
              label="Maximum Artwork Size (px)"
              description="Maximum width/height for downloaded artwork"
              value={draft['artwork_max_size'] || '1400'}
              onChange={(v) => updateDraft('artwork_max_size', v)}
              type="number"
            />
            <SettingField
              label="Artwork Sources"
              description="Comma-separated priority list: filesystem,itunes,fanarttv,spotify,coverart"
              value={draft['artwork_sources'] || 'filesystem,itunes,fanarttv,spotify,coverart'}
              onChange={(v) => updateDraft('artwork_sources', v)}
            />
          </div>
        )}

        {activeTab === 'api' && (
          <div className="space-y-5">
            <SettingField
              label="fanart.tv API Key"
              description="API key for fanart.tv artwork source"
              value={draft['fanarttv_api_key'] || ''}
              onChange={(v) => updateDraft('fanarttv_api_key', v)}
              placeholder="Enter API key..."
            />
            <SettingField
              label="Spotify Client ID"
              description="OAuth client ID for Spotify artwork source"
              value={draft['spotify_client_id'] || ''}
              onChange={(v) => updateDraft('spotify_client_id', v)}
              placeholder="Enter client ID..."
            />
            <SettingField
              label="Spotify Client Secret"
              description="OAuth client secret for Spotify artwork source"
              value={draft['spotify_client_secret'] || ''}
              onChange={(v) => updateDraft('spotify_client_secret', v)}
              placeholder="Enter client secret..."
              type="password"
            />
          </div>
        )}
      </div>
    </div>
  )
}

function SettingField({
  label,
  description,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string
  description: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-text mb-1">{label}</label>
      <p className="text-xs text-text-subtle mb-2">{description}</p>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text placeholder:text-text-subtle focus:outline-none focus:border-accent-blue transition-colors"
      />
    </div>
  )
}
