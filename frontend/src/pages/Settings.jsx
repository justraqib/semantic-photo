import { useEffect, useRef, useState } from 'react';
import {
  connectDriveSync,
  disconnectDriveSync,
  getPickerToken,
  getSyncStatus,
  selectDriveFolder,
  triggerSync,
} from '../api/sync';
import { exportPhotosArchive } from '../api/photos';
import { useAuth } from '../hooks/useAuth';

const GOOGLE_API_SCRIPT_ID = 'google-api-script';

function parseDownloadMessage(message) {
  if (!message) return null;
  const match = message.match(/(\d+)% \((\d+)MB\/(\d+)MB\)/);
  if (!match) return null;
  return {
    percent: Number(match[1]),
    downloadedMb: Number(match[2]),
    totalMb: Number(match[3]),
  };
}

function getDownloadInfo(progress) {
  if (typeof progress?.download_percent === 'number' && progress.download_percent > 0) {
    return {
      percent: Number(progress.download_percent),
      downloadedMb: Number(progress.downloaded_mb || 0),
      totalMb: Number(progress.download_total_mb || 0),
    };
  }
  return parseDownloadMessage(progress?.message);
}

function loadGoogleApiScript() {
  if (document.getElementById(GOOGLE_API_SCRIPT_ID)) return;
  const script = document.createElement('script');
  script.id = GOOGLE_API_SCRIPT_ID;
  script.src = 'https://apis.google.com/js/api.js';
  script.async = true;
  script.defer = true;
  document.body.appendChild(script);
}

function SettingsCard({ title, description, icon, children }) {
  return (
    <div className="glass-card p-5">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-muted">
          {icon}
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          {description && <p className="text-sm text-foreground-muted">{description}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const [status, setStatus] = useState('');
  const [syncState, setSyncState] = useState({
    connected: false,
    folder_name: null,
    last_sync_at: null,
    sync_enabled: false,
    status: 'idle',
    last_error: null,
  });
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [runningSync, setRunningSync] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const tokenRef = useRef(null);
  const progress = syncState.progress || {};
  const job = syncState.job || {};
  const totalFiles = Number(job.total_discovered ?? progress.total_files ?? 0);
  const processedFiles = Number(job.processed_count ?? progress.processed_files ?? 0);
  const uploadedFiles = Number(job.uploaded_count ?? progress.uploaded ?? 0);
  const skippedFiles = Number(job.skipped_count ?? progress.skipped ?? 0);
  const failedFiles = Number(job.failed_count ?? progress.failed ?? 0);
  const remainingFiles = Math.max(totalFiles - processedFiles, 0);
  const processingPercent = totalFiles > 0 ? Math.min(100, Math.round((processedFiles / totalFiles) * 100)) : 0;
  const downloadInfo = getDownloadInfo(progress);

  const loadStatus = async () => {
    try {
      const response = await getSyncStatus();
      setSyncState(response.data);
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    loadGoogleApiScript();
    const interval = setInterval(() => {
      if (window.gapi?.load && !tokenRef.current) {
        window.gapi.load('picker', () => {
          tokenRef.current = true;
          setStatus('Google Picker loaded');
        });
      }
    }, 300);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    void loadStatus();
  }, []);

  useEffect(() => {
    const livePhases = new Set(['auth', 'listing', 'downloading_zip', 'extracting', 'importing']);
    const currentPhase = syncState.progress?.phase || 'idle';
    const isRunning = syncState.status === 'running' || livePhases.has(currentPhase);
    const pollMs = isRunning ? 2000 : 30000;
    const poll = setInterval(() => {
      void loadStatus();
    }, pollMs);
    return () => clearInterval(poll);
  }, [syncState.status, syncState.progress?.phase]);

  const openPicker = async () => {
    const gapi = window.gapi;
    const google = window.google;
    const developerKey = import.meta.env.VITE_GOOGLE_API_KEY;
    let oauthToken = null;

    try {
      const tokenResponse = await getPickerToken();
      oauthToken = tokenResponse.data?.access_token || null;
    } catch {
      oauthToken = null;
    }

    if (!gapi?.picker || !google?.picker || !oauthToken || !developerKey) {
      setStatus('Picker requires Google OAuth login and VITE_GOOGLE_API_KEY in frontend env.');
      return;
    }

    const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS)
      .setIncludeFolders(true)
      .setSelectFolderEnabled(true);

    const picker = new google.picker.PickerBuilder()
      .setDeveloperKey(developerKey)
      .setOAuthToken(oauthToken)
      .setTitle('Choose Google Drive Folder')
      .addView(view)
      .setCallback(async (data) => {
        if (data.action !== google.picker.Action.PICKED) return;
        const doc = data.docs?.[0];
        if (!doc) return;
        try {
          await selectDriveFolder({ folder_id: doc.id, folder_name: doc.name || 'Google Drive Folder' });
          await connectDriveSync();
          await loadStatus();
          setStatus(`Folder selected: ${doc.name || doc.id}`);
        } catch {
          setStatus('Failed to save selected folder');
        }
      })
      .build();

    picker.setVisible(true);
  };

  const handleSyncNow = async () => {
    try {
      setRunningSync(true);
      await triggerSync();
      await loadStatus();
    } finally {
      setRunningSync(false);
    }
  };

  const handleDisconnect = async () => {
    await disconnectDriveSync();
    await loadStatus();
    setStatus('Drive sync disconnected');
  };

  const handleExportArchive = async () => {
    try {
      setIsExporting(true);
      const response = await exportPhotosArchive();
      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'photo-export.zip';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setStatus('Archive download started');
    } catch {
      setStatus('Failed to export archive');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[900px] p-4 md:p-8">
      <h1 className="mb-6 text-2xl font-bold text-foreground">Settings</h1>

      <div className="flex flex-col gap-4">
        {/* Account card */}
        <SettingsCard
          title="Account"
          description="Your profile information"
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          }
        >
          <div className="flex items-center gap-4">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.display_name || 'User'}
                className="h-14 w-14 rounded-xl ring-2 ring-surface-border"
              />
            ) : (
              <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-accent/10 text-lg font-semibold text-accent-light ring-2 ring-surface-border">
                {(user?.display_name || 'U').slice(0, 1).toUpperCase()}
              </div>
            )}
            <div>
              <p className="font-medium text-foreground">{user?.display_name || 'User'}</p>
              <p className="text-sm text-foreground-muted">{user?.email || ''}</p>
            </div>
          </div>
        </SettingsCard>

        {/* Google Drive Sync */}
        <SettingsCard
          title="Google Drive Sync"
          description="Keep your photos in sync with Google Drive"
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
              <polyline points="16 16 12 12 8 16" />
              <line x1="12" y1="12" x2="12" y2="21" />
              <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
            </svg>
          }
        >
          {loadingStatus ? (
            <div className="h-8 w-48 animate-pulse rounded-lg bg-surface-light" />
          ) : !syncState.connected ? (
            <button
              type="button"
              onClick={openPicker}
              className="btn-primary"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 16 12 12 8 16" />
                <line x1="12" y1="12" x2="12" y2="21" />
                <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
              </svg>
              Connect Google Drive
            </button>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="rounded-xl border border-surface-border bg-surface px-4 py-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wide text-foreground-muted">Live Sync Status</span>
                  <span className="text-xs font-medium text-foreground">{syncState.status || 'idle'}</span>
                </div>

                {progress.phase === 'downloading_zip' && downloadInfo && (
                  <div className="mb-3">
                    <div className="mb-1 flex items-center justify-between text-xs text-foreground-muted">
                      <span>Downloading ZIP</span>
                      <span>{downloadInfo.percent}%</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-light">
                      <div
                        className="h-full rounded-full bg-accent-light transition-all duration-500 animate-pulse"
                        style={{ width: `${downloadInfo.percent}%` }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-foreground-dim">
                      {downloadInfo.downloadedMb}MB / {downloadInfo.totalMb}MB
                    </p>
                  </div>
                )}

                <div className="mb-2 flex items-center justify-between text-xs text-foreground-muted">
                  <span>Processing</span>
                  <span>{processingPercent}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-surface-light">
                  <div
                    className="h-full rounded-full bg-success transition-all duration-500"
                    style={{ width: `${processingPercent}%` }}
                  />
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <span className="text-foreground-muted">Total: <span className="text-foreground">{totalFiles}</span></span>
                  <span className="text-foreground-muted">Remaining: <span className="text-foreground">{remainingFiles}</span></span>
                  <span className="text-foreground-muted">Processed: <span className="text-foreground">{processedFiles}</span></span>
                  <span className="text-foreground-muted">Uploaded: <span className="text-success">{uploadedFiles}</span></span>
                  <span className="text-foreground-muted">Skipped: <span className="text-foreground">{skippedFiles}</span></span>
                  <span className="text-foreground-muted">Failed: <span className="text-danger">{failedFiles}</span></span>
                </div>

                {progress.message && (
                  <p className="mt-2 text-xs text-foreground-dim">{progress.message}</p>
                )}
              </div>

              <div className="flex flex-col gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-foreground-muted">Folder:</span>
                  <span className="font-medium text-foreground">{syncState.folder_name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-foreground-muted">Last sync:</span>
                  <span className="text-foreground">
                    {syncState.last_sync_at
                      ? new Date(syncState.last_sync_at).toLocaleString()
                      : 'Never'}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleSyncNow}
                  disabled={runningSync}
                  className="btn-primary text-sm"
                >
                  {runningSync ? 'Syncing...' : 'Sync Now'}
                </button>
                <div className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2">
                  <div className={`h-2 w-2 rounded-full ${syncState.sync_enabled ? 'bg-success' : 'bg-foreground-dim'}`} />
                  <span className="text-sm text-foreground-muted">
                    Auto-sync {syncState.sync_enabled ? 'on' : 'off'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleDisconnect}
                  className="btn-ghost text-sm text-danger hover:bg-danger/10"
                >
                  Disconnect
                </button>
              </div>

              {syncState.last_error && (
                <div className="rounded-xl bg-danger/10 border border-danger/20 px-3 py-2 text-sm text-danger">
                  {syncState.last_error}
                </div>
              )}
            </div>
          )}
          {status && (
            <p className="mt-3 text-sm text-foreground-muted">{status}</p>
          )}
        </SettingsCard>

        {/* Storage & Export */}
        <SettingsCard
          title="Storage & Export"
          description="Download all your photos and metadata"
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          }
        >
          <button
            type="button"
            onClick={handleExportArchive}
            disabled={isExporting}
            className="btn-secondary"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {isExporting ? 'Preparing export...' : 'Export My Archive'}
          </button>
        </SettingsCard>

        {/* About */}
        <SettingsCard
          title="About"
          description="Semantic Photo"
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
          }
        >
          <div className="flex flex-col gap-2 text-sm text-foreground-muted">
            <p>AI-powered semantic search for your self-hosted photo gallery.</p>
            <p>
              Open source &middot; Privacy first &middot;{' '}
              <a
                href="https://github.com/justraqib/semantic-photo"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-light hover:underline"
              >
                GitHub
              </a>
            </p>
          </div>
        </SettingsCard>
      </div>
    </div>
  );
}
