import { useEffect, useState, useRef, type KeyboardEvent } from 'react'
import {
  Save, Sliders, Globe, Image, Key, X, Plus, GripVertical,
  CheckCircle2, AlertCircle, RotateCcw, FolderOpen, Info, Github, Puzzle, RefreshCw,
} from 'lucide-react'
import { useSettingsStore } from '@/store/useSettingsStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { batchRetagAll } from '@/services/api'
import { LoadingSpinner } from '@/components/common'
import { cn } from '@/utils'

const tabs = [
  { id: 'general', label: 'General', icon: Sliders },
  { id: 'matching', label: 'Matching', icon: Globe },
  { id: 'artwork', label: 'Artwork', icon: Image },
  { id: 'features', label: 'Features', icon: Puzzle },
  { id: 'api', label: 'API Keys', icon: Key },
] as const

type TabId = (typeof tabs)[number]['id']

// Default values matching backend config.py
const DEFAULTS: Record<string, string> = {
  auto_tag_on_scan: 'false',
  confidence_auto_threshold: '85',
  confidence_review_threshold: '50',
  watch_stabilization_delay: '30',
  preferred_countries: 'US,GB,DE,IT',
  preferred_media: 'Digital Media,CD',
  artwork_min_size: '500',
  artwork_max_size: '1400',
  artwork_sources: 'coverart,filesystem,fanarttv,itunes,spotify',
  acoustid_api_key: '',
  fingerprint_enabled: 'false',
  fanarttv_api_key: '',
  spotify_client_id: '',
  spotify_client_secret: '',
  disc_subfolder_patterns: JSON.stringify([
    String.raw`^(?:cd|disc|disk)\s*(\d+)$`,
    String.raw`^(?:(?:7|10|12)\s*(?:inch\s*)?)?vinyl\s*(\d+)$`,
    String.raw`^side\s*([A-Da-d\d])$`,
    String.raw`^cassette\s*(\d+)$`,
  ]),
  // Features
  backup_enabled: 'true',
  backup_max_per_album: '5',
  lyrics_enabled: 'true',
  lyrics_auto_fetch: 'false',
  lyrics_prefer_synced: 'true',
  replaygain_enabled: 'true',
  replaygain_auto_calculate: 'false',
  replaygain_reference_loudness: '-18.0',
}

const ARTWORK_SOURCE_LABELS: Record<string, string> = {
  filesystem: 'Local Files',
  itunes: 'iTunes',
  fanarttv: 'fanart.tv',
  spotify: 'Spotify',
  coverart: 'Cover Art Archive',
}

export function SettingsPage() {
  const { settings, loading, saving, fetchSettings, updateSettings } = useSettingsStore()
  const addToast = useNotificationStore((s) => s.addToast)
  const [activeTab, setActiveTab] = useState<TabId>('general')
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [initialDraft, setInitialDraft] = useState<Record<string, string>>({})

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  useEffect(() => {
    const map: Record<string, string> = { ...DEFAULTS }
    settings.forEach((s) => {
      if (s.value != null) map[s.key] = s.value
    })
    setDraft(map)
    setInitialDraft(map)
  }, [settings])

  const updateDraft = (key: string, value: string) => {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(initialDraft)

  const handleSave = async () => {
    try {
      await updateSettings(draft)
      addToast('success', 'Settings saved')
    } catch {
      addToast('error', 'Failed to save settings')
    }
  }

  const handleReset = () => {
    setDraft({ ...initialDraft })
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
        <div className="flex items-center gap-2">
          {hasChanges && (
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-3 py-2 text-text-muted rounded-lg text-sm hover:bg-surface-200 transition-colors"
            >
              <RotateCcw className="h-4 w-4" />
              Discard
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
              hasChanges
                ? 'bg-accent-blue text-surface-300 hover:opacity-90'
                : 'bg-surface-400 text-text-subtle cursor-not-allowed',
              saving && 'opacity-50',
            )}
          >
            {saving ? <LoadingSpinner size="sm" /> : <Save className="h-4 w-4" />}
            {hasChanges ? 'Save Changes' : 'Saved'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-200 p-1 rounded-lg">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors',
                activeTab === tab.id
                  ? 'bg-surface-100 text-text shadow-sm'
                  : 'text-text-muted hover:text-text',
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div className="space-y-4">
        {activeTab === 'general' && (
          <GeneralTab draft={draft} updateDraft={updateDraft} />
        )}
        {activeTab === 'matching' && (
          <MatchingTab draft={draft} updateDraft={updateDraft} />
        )}
        {activeTab === 'artwork' && (
          <ArtworkTab draft={draft} updateDraft={updateDraft} />
        )}
        {activeTab === 'features' && (
          <FeaturesTab draft={draft} updateDraft={updateDraft} />
        )}
        {activeTab === 'api' && (
          <ApiKeysTab draft={draft} updateDraft={updateDraft} />
        )}
      </div>

      {/* About footer */}
      <div className="flex items-center justify-center gap-2 pt-2 pb-4 text-xs text-text-subtle">
        <span>MusicTaggerz</span>
        <span className="text-surface-500">·</span>
        <a
          href="https://github.com/MattiVenturelli/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-text-subtle hover:text-text transition-colors"
        >
          <Github className="h-3.5 w-3.5" />
          MattiVenturelli
        </a>
      </div>
    </div>
  )
}

// ─── Tab Sections ────────────────────────────────────────────────

interface TabProps {
  draft: Record<string, string>
  updateDraft: (key: string, value: string) => void
}

function GeneralTab({ draft, updateDraft }: TabProps) {
  const addToast = useNotificationStore((s) => s.addToast)
  const [retagging, setRetagging] = useState(false)
  const autoThreshold = parseFloat(draft['confidence_auto_threshold'] || '85')
  const reviewThreshold = parseFloat(draft['confidence_review_threshold'] || '50')

  const handleRetagAll = async () => {
    if (!window.confirm('This will re-match and re-tag ALL albums in your library. Are you sure?')) return
    setRetagging(true)
    try {
      await batchRetagAll()
      addToast('success', 'All albums queued for re-tagging')
    } catch {
      addToast('error', 'Failed to queue albums for re-tagging')
    } finally {
      setRetagging(false)
    }
  }

  return (
    <>
      <SettingsCard title="Tagging Mode" description="Control how albums are tagged after matching.">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text">
              {draft['auto_tag_on_scan'] === 'true' ? 'Automatic' : 'Manual'}
            </p>
            <p className="text-xs text-text-subtle mt-0.5">
              {draft['auto_tag_on_scan'] === 'true'
                ? 'Albums are tagged automatically when confidence is high enough'
                : 'Albums are matched but you must approve tagging manually'}
            </p>
          </div>
          <ToggleSwitch
            checked={draft['auto_tag_on_scan'] === 'true'}
            onChange={(v) => updateDraft('auto_tag_on_scan', v ? 'true' : 'false')}
          />
        </div>
      </SettingsCard>

      <SettingsCard title="Confidence Thresholds" description="Control how matches are classified based on their confidence score.">
        {/* Visual threshold bar */}
        <div className="mb-5">
          <div className="flex h-3 rounded-full overflow-hidden">
            <div
              className="bg-accent-red/60"
              style={{ width: `${reviewThreshold}%` }}
            />
            <div
              className="bg-accent-yellow/60"
              style={{ width: `${autoThreshold - reviewThreshold}%` }}
            />
            <div
              className="bg-accent-green/60"
              style={{ width: `${100 - autoThreshold}%` }}
            />
          </div>
          <div className="flex justify-between mt-1.5 text-[10px] text-text-subtle">
            <span>0 - Skip</span>
            <span style={{ marginLeft: `${reviewThreshold - 10}%` }}>{reviewThreshold} - Review</span>
            <span>{autoThreshold} - Auto-tag</span>
            <span>100</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text mb-1">Auto-tag Threshold</label>
            <p className="text-xs text-text-subtle mb-2">Albums above this score are tagged automatically</p>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="50"
                max="100"
                step="5"
                value={draft['confidence_auto_threshold'] || '85'}
                onChange={(e) => updateDraft('confidence_auto_threshold', e.target.value)}
                className="flex-1 accent-accent-green"
              />
              <span className="text-sm font-mono text-text w-8 text-right">
                {draft['confidence_auto_threshold'] || '85'}
              </span>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1">Review Threshold</label>
            <p className="text-xs text-text-subtle mb-2">Albums between this and auto-tag need review</p>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="10"
                max="80"
                step="5"
                value={draft['confidence_review_threshold'] || '50'}
                onChange={(e) => updateDraft('confidence_review_threshold', e.target.value)}
                className="flex-1 accent-accent-yellow"
              />
              <span className="text-sm font-mono text-text w-8 text-right">
                {draft['confidence_review_threshold'] || '50'}
              </span>
            </div>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard title="File Watcher" description="Settings for automatic detection of new music files.">
        <div>
          <label className="block text-sm font-medium text-text mb-1">Stabilization Delay</label>
          <p className="text-xs text-text-subtle mb-2">
            Seconds to wait after detecting new files before processing (allows large copies to finish)
          </p>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="5"
              max="120"
              step="5"
              value={draft['watch_stabilization_delay'] || '30'}
              onChange={(e) => updateDraft('watch_stabilization_delay', e.target.value)}
              className="flex-1 accent-accent-blue"
            />
            <span className="text-sm font-mono text-text w-10 text-right">
              {draft['watch_stabilization_delay'] || '30'}s
            </span>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard
        title="Multi-Disc Detection"
        description="Regex patterns to identify disc subfolders (e.g. CD1, Disc 2, Vinyl1). Each pattern must have one capture group returning the disc number or letter. Matched folders are merged into a single album."
      >
        <RegexListInput
          value={draft['disc_subfolder_patterns'] || DEFAULTS.disc_subfolder_patterns}
          onChange={(v) => updateDraft('disc_subfolder_patterns', v)}
        />
      </SettingsCard>

      <SettingsCard title="Maintenance" description="Actions that affect your entire library.">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text">Re-tag All Albums</p>
            <p className="text-xs text-text-subtle mt-0.5">
              Reset all albums and re-queue them for matching and tagging
            </p>
          </div>
          <button
            onClick={handleRetagAll}
            disabled={retagging}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
              'bg-accent-red/15 text-accent-red hover:bg-accent-red/25',
              retagging && 'opacity-50 cursor-not-allowed',
            )}
          >
            {retagging ? <LoadingSpinner size="sm" /> : <RefreshCw className="h-4 w-4" />}
            {retagging ? 'Queuing...' : 'Re-tag All'}
          </button>
        </div>
      </SettingsCard>
    </>
  )
}

function MatchingTab({ draft, updateDraft }: TabProps) {
  return (
    <>
      <SettingsCard
        title="Audio Fingerprinting"
        description="Use AcoustID audio fingerprinting to improve matching when metadata is poor or missing."
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text">
              {draft['fingerprint_enabled'] === 'true' ? 'Enabled' : 'Disabled'}
            </p>
            <p className="text-xs text-text-subtle mt-0.5">
              {draft['fingerprint_enabled'] === 'true'
                ? 'Fingerprinting is used as a supplementary/fallback matching method'
                : 'Only text-based matching is used'}
            </p>
            {draft['fingerprint_enabled'] === 'true' && !draft['acoustid_api_key'] && (
              <p className="text-xs text-accent-yellow mt-1">
                Requires an AcoustID API key (configure in API Keys tab)
              </p>
            )}
          </div>
          <ToggleSwitch
            checked={draft['fingerprint_enabled'] === 'true'}
            onChange={(v) => updateDraft('fingerprint_enabled', v ? 'true' : 'false')}
          />
        </div>
      </SettingsCard>

      <SettingsCard
        title="Preferred Countries"
        description="Release countries to prefer when multiple versions of an album exist. Higher priority countries get better match scores."
      >
        <ChipListInput
          value={draft['preferred_countries'] || 'US,GB,DE,IT'}
          onChange={(v) => updateDraft('preferred_countries', v)}
          placeholder="Add country code (e.g. US, GB, JP)..."
          transform="upper"
        />
      </SettingsCard>

      <SettingsCard
        title="Preferred Media"
        description="Media formats to prefer. Digital releases usually have the best metadata."
      >
        <ChipListInput
          value={draft['preferred_media'] || 'Digital Media,CD'}
          onChange={(v) => updateDraft('preferred_media', v)}
          placeholder="Add media format (e.g. Vinyl, Cassette)..."
        />
      </SettingsCard>
    </>
  )
}

function FeaturesTab({ draft, updateDraft }: TabProps) {
  return (
    <>
      <SettingsCard title="Tag Backups" description="Automatically save tag state before any write operation so you can restore later.">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text">
                {draft['backup_enabled'] === 'true' ? 'Enabled' : 'Disabled'}
              </p>
              <p className="text-xs text-text-subtle mt-0.5">
                {draft['backup_enabled'] === 'true'
                  ? 'Backups are created before tagging, editing, artwork, lyrics, and ReplayGain'
                  : 'No backups will be created (cannot undo tag changes)'}
              </p>
            </div>
            <ToggleSwitch
              checked={draft['backup_enabled'] === 'true'}
              onChange={(v) => updateDraft('backup_enabled', v ? 'true' : 'false')}
            />
          </div>
          {draft['backup_enabled'] === 'true' && (
            <div>
              <label className="block text-sm font-medium text-text mb-1">Max Backups Per Album</label>
              <p className="text-xs text-text-subtle mb-2">Older backups are automatically pruned</p>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="1"
                  value={draft['backup_max_per_album'] || '5'}
                  onChange={(e) => updateDraft('backup_max_per_album', e.target.value)}
                  className="flex-1 accent-accent-blue"
                />
                <span className="text-sm font-mono text-text w-6 text-right">
                  {draft['backup_max_per_album'] || '5'}
                </span>
              </div>
            </div>
          )}
        </div>
      </SettingsCard>

      <SettingsCard title="Lyrics (LRCLIB)" description="Fetch and embed song lyrics from LRCLIB. Supports plain text and synced (LRC) lyrics.">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text">
                {draft['lyrics_enabled'] === 'true' ? 'Enabled' : 'Disabled'}
              </p>
              <p className="text-xs text-text-subtle mt-0.5">
                No API key required
              </p>
            </div>
            <ToggleSwitch
              checked={draft['lyrics_enabled'] === 'true'}
              onChange={(v) => updateDraft('lyrics_enabled', v ? 'true' : 'false')}
            />
          </div>
          {draft['lyrics_enabled'] === 'true' && (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-text">Auto-fetch during tagging</p>
                  <p className="text-xs text-text-subtle mt-0.5">
                    Automatically fetch lyrics after MusicBrainz tagging
                  </p>
                </div>
                <ToggleSwitch
                  checked={draft['lyrics_auto_fetch'] === 'true'}
                  onChange={(v) => updateDraft('lyrics_auto_fetch', v ? 'true' : 'false')}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-text">Prefer synced lyrics</p>
                  <p className="text-xs text-text-subtle mt-0.5">
                    Use LRC (timestamped) lyrics when available
                  </p>
                </div>
                <ToggleSwitch
                  checked={draft['lyrics_prefer_synced'] === 'true'}
                  onChange={(v) => updateDraft('lyrics_prefer_synced', v ? 'true' : 'false')}
                />
              </div>
            </>
          )}
        </div>
      </SettingsCard>

      <SettingsCard title="ReplayGain" description="Calculate and embed ReplayGain volume normalization using ffmpeg. Requires ffmpeg to be installed.">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text">
                {draft['replaygain_enabled'] === 'true' ? 'Enabled' : 'Disabled'}
              </p>
              <p className="text-xs text-text-subtle mt-0.5">
                Analyzes track loudness and writes gain/peak tags
              </p>
            </div>
            <ToggleSwitch
              checked={draft['replaygain_enabled'] === 'true'}
              onChange={(v) => updateDraft('replaygain_enabled', v ? 'true' : 'false')}
            />
          </div>
          {draft['replaygain_enabled'] === 'true' && (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-text">Auto-calculate during tagging</p>
                  <p className="text-xs text-text-subtle mt-0.5">
                    Automatically calculate ReplayGain after MusicBrainz tagging (CPU-intensive)
                  </p>
                </div>
                <ToggleSwitch
                  checked={draft['replaygain_auto_calculate'] === 'true'}
                  onChange={(v) => updateDraft('replaygain_auto_calculate', v ? 'true' : 'false')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text mb-1">Reference Loudness</label>
                <p className="text-xs text-text-subtle mb-2">Standard is -18.0 LUFS (Opus uses -23.0 LUFS internally)</p>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.5"
                    min="-30"
                    max="-10"
                    value={draft['replaygain_reference_loudness'] || '-18.0'}
                    onChange={(e) => updateDraft('replaygain_reference_loudness', e.target.value)}
                    className="w-32 px-3 py-2 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text focus:outline-none focus:border-accent-blue transition-colors font-mono"
                  />
                  <span className="text-xs text-text-subtle">LUFS</span>
                </div>
              </div>
            </>
          )}
        </div>
      </SettingsCard>
    </>
  )
}

function ArtworkTab({ draft, updateDraft }: TabProps) {
  const sources = (draft['artwork_sources'] || 'filesystem,itunes,fanarttv,spotify,coverart')
    .split(',')
    .filter(Boolean)

  const moveSource = (index: number, direction: -1 | 1) => {
    const newSources = [...sources]
    const target = index + direction
    if (target < 0 || target >= newSources.length) return
    ;[newSources[index], newSources[target]] = [newSources[target], newSources[index]]
    updateDraft('artwork_sources', newSources.join(','))
  }

  return (
    <>
      <SettingsCard title="Image Size" description="Minimum and maximum dimensions for downloaded cover art.">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text mb-1">Minimum Size</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="100"
                max="2000"
                step="100"
                value={draft['artwork_min_size'] || '500'}
                onChange={(e) => updateDraft('artwork_min_size', e.target.value)}
                className="w-full px-3 py-2 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text focus:outline-none focus:border-accent-blue transition-colors"
              />
              <span className="text-xs text-text-subtle shrink-0">px</span>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1">Maximum Size</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="500"
                max="5000"
                step="100"
                value={draft['artwork_max_size'] || '1400'}
                onChange={(e) => updateDraft('artwork_max_size', e.target.value)}
                className="w-full px-3 py-2 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text focus:outline-none focus:border-accent-blue transition-colors"
              />
              <span className="text-xs text-text-subtle shrink-0">px</span>
            </div>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard
        title="Source Priority"
        description="Order in which artwork sources are tried. The first source that returns a valid image wins."
      >
        <div className="space-y-1.5">
          {sources.map((source, i) => (
            <div
              key={source}
              className="flex items-center gap-3 px-3 py-2.5 bg-surface-200 rounded-lg border border-surface-400"
            >
              <GripVertical className="h-4 w-4 text-text-subtle shrink-0" />
              <span className="text-xs font-mono text-text-subtle w-5">{i + 1}.</span>
              <span className="text-sm text-text flex-1">
                {ARTWORK_SOURCE_LABELS[source] || source}
              </span>
              <SourceBadge source={source} draft={draft} />
              <div className="flex gap-1">
                <button
                  onClick={() => moveSource(i, -1)}
                  disabled={i === 0}
                  className="px-1.5 py-0.5 text-xs text-text-muted hover:text-text hover:bg-surface-300 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  Up
                </button>
                <button
                  onClick={() => moveSource(i, 1)}
                  disabled={i === sources.length - 1}
                  className="px-1.5 py-0.5 text-xs text-text-muted hover:text-text hover:bg-surface-300 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  Down
                </button>
              </div>
            </div>
          ))}
        </div>
      </SettingsCard>
    </>
  )
}

function ApiKeysTab({ draft, updateDraft }: TabProps) {
  return (
    <>
      <div className="flex items-start gap-2 px-4 py-3 bg-accent-blue/10 border border-accent-blue/20 rounded-lg text-sm text-accent-blue">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        <p>API keys are optional. Without them, only iTunes and Cover Art Archive will be used for artwork (both free, no key needed).</p>
      </div>

      <ApiKeyCard
        title="AcoustID"
        description="Audio fingerprinting for identifying tracks when metadata is missing or incorrect."
        signupUrl="https://acoustid.org/new-application"
        value={draft['acoustid_api_key'] || ''}
        onChange={(v) => updateDraft('acoustid_api_key', v)}
      />

      <ApiKeyCard
        title="fanart.tv"
        description="High-quality album art and artist images."
        signupUrl="https://fanart.tv/get-an-api-key/"
        value={draft['fanarttv_api_key'] || ''}
        onChange={(v) => updateDraft('fanarttv_api_key', v)}
      />

      <ApiKeyCard
        title="Spotify"
        description="Album cover art from Spotify's catalog."
        signupUrl="https://developer.spotify.com/dashboard"
        value={draft['spotify_client_id'] || ''}
        onChange={(v) => updateDraft('spotify_client_id', v)}
        fields={[
          { key: 'spotify_client_id', label: 'Client ID', value: draft['spotify_client_id'] || '' },
          { key: 'spotify_client_secret', label: 'Client Secret', value: draft['spotify_client_secret'] || '', secret: true },
        ]}
        onChangeMulti={(key, v) => updateDraft(key, v)}
      />
    </>
  )
}

// ─── Reusable Components ─────────────────────────────────────────

function SettingsCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-surface-100 rounded-xl border border-surface-400 p-5">
      <h3 className="text-sm font-semibold text-text">{title}</h3>
      <p className="text-xs text-text-subtle mt-0.5 mb-4">{description}</p>
      {children}
    </div>
  )
}

function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-7 w-12 items-center rounded-full transition-colors shrink-0',
        checked ? 'bg-accent-green' : 'bg-surface-400',
      )}
    >
      <span
        className={cn(
          'inline-block h-5 w-5 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-6' : 'translate-x-1',
        )}
      />
    </button>
  )
}

function ChipListInput({
  value,
  onChange,
  placeholder,
  transform,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  transform?: 'upper' | 'lower'
}) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const items = value.split(',').filter(Boolean).map((s) => s.trim())

  const addItem = () => {
    let trimmed = input.trim()
    if (!trimmed) return
    if (transform === 'upper') trimmed = trimmed.toUpperCase()
    if (transform === 'lower') trimmed = trimmed.toLowerCase()
    if (items.includes(trimmed)) {
      setInput('')
      return
    }
    onChange([...items, trimmed].join(','))
    setInput('')
  }

  const removeItem = (index: number) => {
    const newItems = items.filter((_, i) => i !== index)
    onChange(newItems.join(','))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addItem()
    } else if (e.key === 'Backspace' && !input && items.length > 0) {
      removeItem(items.length - 1)
    }
  }

  return (
    <div
      className="flex flex-wrap gap-2 p-2 bg-surface-200 border border-surface-400 rounded-lg cursor-text min-h-[42px]"
      onClick={() => inputRef.current?.focus()}
    >
      {items.map((item, i) => (
        <span
          key={`${item}-${i}`}
          className="flex items-center gap-1 px-2.5 py-1 bg-surface-300 border border-surface-500 rounded-md text-sm text-text"
        >
          {item}
          <button
            onClick={(e) => {
              e.stopPropagation()
              removeItem(i)
            }}
            className="text-text-subtle hover:text-accent-red transition-colors"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={addItem}
        placeholder={items.length === 0 ? placeholder : ''}
        className="flex-1 min-w-[120px] bg-transparent text-sm text-text placeholder:text-text-subtle focus:outline-none py-1 px-1"
      />
    </div>
  )
}

function parsePatterns(raw: string): string[] {
  if (raw.startsWith('[')) {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed.map(String)
    } catch { /* fall through */ }
  }
  return raw.split(',').filter(Boolean)
}

function serializePatterns(items: string[]): string {
  return JSON.stringify(items.filter((p) => p.trim()))
}

function validatePattern(pattern: string): string | null {
  if (!pattern.trim()) return null
  try {
    new RegExp(pattern)
    return null
  } catch (e) {
    return e instanceof Error ? e.message : 'Invalid regex'
  }
}

function RegexListInput({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const items = parsePatterns(value)
  const [editingNew, setEditingNew] = useState(false)
  const [newValue, setNewValue] = useState('')
  const newInputRef = useRef<HTMLInputElement>(null)

  const errors = items.map(validatePattern)
  const newError = newValue ? validatePattern(newValue) : null

  const updateItem = (index: number, newVal: string) => {
    const newItems = [...items]
    newItems[index] = newVal
    onChange(serializePatterns(newItems))
  }

  const removeItem = (index: number) => {
    onChange(serializePatterns(items.filter((_, i) => i !== index)))
  }

  const commitNew = () => {
    const trimmed = newValue.trim()
    if (trimmed) {
      onChange(serializePatterns([...items, trimmed]))
    }
    setNewValue('')
    setEditingNew(false)
  }

  const startAdding = () => {
    setEditingNew(true)
    setNewValue('')
    setTimeout(() => newInputRef.current?.focus(), 0)
  }

  const handleNewKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      commitNew()
    } else if (e.key === 'Escape') {
      setNewValue('')
      setEditingNew(false)
    }
  }

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i}>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={item}
              onChange={(e) => updateItem(i, e.target.value)}
              placeholder="^pattern\s*(\d+)$"
              className={cn(
                'flex-1 px-3 py-2 bg-surface-200 border rounded-lg text-sm text-text font-mono placeholder:text-text-subtle focus:outline-none transition-colors',
                errors[i]
                  ? 'border-accent-red focus:border-accent-red'
                  : 'border-surface-400 focus:border-accent-blue',
              )}
            />
            <button
              onClick={() => removeItem(i)}
              className="p-1.5 text-text-subtle hover:text-accent-red transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {errors[i] && (
            <p className="text-xs text-accent-red mt-1 ml-1">{errors[i]}</p>
          )}
        </div>
      ))}
      {editingNew && (
        <div>
          <div className="flex items-center gap-2">
            <input
              ref={newInputRef}
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={handleNewKeyDown}
              onBlur={commitNew}
              placeholder="^pattern\s*(\d+)$"
              className={cn(
                'flex-1 px-3 py-2 bg-surface-200 border rounded-lg text-sm text-text font-mono placeholder:text-text-subtle focus:outline-none transition-colors',
                newError
                  ? 'border-accent-red focus:border-accent-red'
                  : 'border-surface-400 focus:border-accent-blue',
              )}
            />
            <button
              onClick={() => { setNewValue(''); setEditingNew(false) }}
              className="p-1.5 text-text-subtle hover:text-accent-red transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {newError && (
            <p className="text-xs text-accent-red mt-1 ml-1">{newError}</p>
          )}
        </div>
      )}
      <button
        onClick={startAdding}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent-blue hover:bg-accent-blue/10 rounded-lg transition-colors"
      >
        <Plus className="h-3.5 w-3.5" />
        Add pattern
      </button>
    </div>
  )
}

function SourceBadge({ source, draft }: { source: string; draft: Record<string, string> }) {
  if (source === 'filesystem') {
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-green/15 text-accent-green">free</span>
  }
  if (source === 'itunes' || source === 'coverart') {
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-green/15 text-accent-green">no key</span>
  }
  if (source === 'fanarttv') {
    const configured = !!draft['fanarttv_api_key']
    return configured
      ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-green/15 text-accent-green">configured</span>
      : <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow">needs key</span>
  }
  if (source === 'spotify') {
    const configured = !!draft['spotify_client_id'] && !!draft['spotify_client_secret']
    return configured
      ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-green/15 text-accent-green">configured</span>
      : <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-yellow/15 text-accent-yellow">needs key</span>
  }
  return null
}

function ApiKeyCard({
  title,
  description,
  signupUrl,
  value,
  onChange,
  fields,
  onChangeMulti,
}: {
  title: string
  description: string
  signupUrl: string
  value: string
  onChange: (v: string) => void
  fields?: { key: string; label: string; value: string; secret?: boolean }[]
  onChangeMulti?: (key: string, v: string) => void
}) {
  const configured = fields
    ? fields.every((f) => !!f.value)
    : !!value

  return (
    <div className="bg-surface-100 rounded-xl border border-surface-400 p-5">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        {configured ? (
          <span className="flex items-center gap-1 text-xs text-accent-green">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Configured
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-text-subtle">
            <AlertCircle className="h-3.5 w-3.5" />
            Not configured
          </span>
        )}
      </div>
      <p className="text-xs text-text-subtle mb-3">
        {description}{' '}
        <a
          href={signupUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-blue hover:underline"
        >
          Get API key
        </a>
      </p>

      {fields ? (
        <div className="space-y-3">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="block text-xs font-medium text-text-muted mb-1">{f.label}</label>
              <input
                type={f.secret ? 'password' : 'text'}
                value={f.value}
                onChange={(e) => onChangeMulti?.(f.key, e.target.value)}
                placeholder={`Enter ${f.label.toLowerCase()}...`}
                className="w-full px-3 py-2 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text placeholder:text-text-subtle focus:outline-none focus:border-accent-blue transition-colors font-mono"
              />
            </div>
          ))}
        </div>
      ) : (
        <input
          type="password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter API key..."
          className="w-full px-3 py-2 bg-surface-200 border border-surface-400 rounded-lg text-sm text-text placeholder:text-text-subtle focus:outline-none focus:border-accent-blue transition-colors font-mono"
        />
      )}
    </div>
  )
}
