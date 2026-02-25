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

const GOOGLE_API_SCRIPT_ID = 'google-api-script';

function loadGoogleApiScript() {
  if (document.getElementById(GOOGLE_API_SCRIPT_ID)) return;
  const script = document.createElement('script');
  script.id = GOOGLE_API_SCRIPT_ID;
  script.src = 'https://apis.google.com/js/api.js';
  script.async = true;
  script.defer = true;
  document.body.appendChild(script);
}

export default function Settings() {
  const [status, setStatus] = useState('');
  const [syncState, setSyncState] = useState({
    connected: false,
    folder_name: null,
    last_sync_at: null,
    sync_enabled: false,
    status: 'idle',
    last_error: null,
    pending_count: 0,
    processed_count: 0,
    imported_count: 0,
    skipped_count: 0,
    failed_count: 0,
  });
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [runningSync, setRunningSync] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const tokenRef = useRef(null);

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
    const poll = setInterval(() => {
      void loadStatus();
    }, syncState.status === 'running' ? 3_000 : 30_000);
    return () => clearInterval(poll);
  }, [syncState.status]);

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

    if (!developerKey) {
      setStatus('Google Picker requires VITE_GOOGLE_API_KEY in frontend/.env and docker compose restart.');
      return;
    }
    if (!oauthToken) {
      setStatus('Google access token missing. Reconnect Google login and try again.');
      return;
    }
    if (!gapi?.picker || !google?.picker) {
      setStatus('Google Picker library not loaded yet. Refresh and try again.');
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
        if (data.action === google.picker.Action.CANCEL) {
          return;
        }
        if (data.action === google.picker.Action.ERROR) {
          setStatus(
            'The API developer key is invalid. In Google Cloud Console, enable "Google Picker API" and allow http://localhost:5173/* as HTTP referrer.'
          );
          return;
        }
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
      const response = await triggerSync();
      await loadStatus();
      if (response.data?.started === false) {
        setStatus('Sync is already running.');
      } else {
        setStatus('Sync started. Checking Google Drive for new files...');
      }
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
      <h1 className="mb-4 text-2xl font-semibold text-slate-900">Settings</h1>
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-2 text-lg font-medium text-slate-800">Google Drive Sync</h2>
        {loadingStatus ? (
          <p className="text-sm text-slate-600">Loading sync status...</p>
        ) : !syncState.connected ? (
          <>
            <p className="mb-4 text-sm text-slate-600">Choose Folder to connect your Drive photos.</p>
            <button
              type="button"
              onClick={openPicker}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Connect Google Drive
            </button>
          </>
        ) : (
          <div className="space-y-3 text-sm text-slate-700">
            <p><span className="font-medium">Folder:</span> {syncState.folder_name}</p>
            <p>
              <span className="font-medium">Last sync:</span>{' '}
              {syncState.last_sync_at ? new Date(syncState.last_sync_at).toLocaleString() : 'Never'}
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleSyncNow}
                disabled={runningSync}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60"
              >
                {runningSync ? 'Syncing...' : 'Sync Now'}
              </button>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={!!syncState.sync_enabled} readOnly />
                Auto-sync enabled
              </label>
              <button
                type="button"
                onClick={handleDisconnect}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
              >
                Disconnect
              </button>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="font-medium text-slate-800">
                Sync status: {syncState.status === 'running' ? 'Running' : 'Idle'}
              </p>
              <p className="mt-1 text-slate-700">
                Remaining photos: {syncState.pending_count}
              </p>
              <p className="text-slate-700">
                Imported: {syncState.imported_count} | Skipped: {syncState.skipped_count} | Failed: {syncState.failed_count}
              </p>
            </div>
            {syncState.last_error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-red-700">{syncState.last_error}</p>
            )}
          </div>
        )}
        {status && <p className="mt-3 text-sm text-slate-600">{status}</p>}
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-2 text-lg font-medium text-slate-800">Storage</h2>
        <p className="mb-4 text-sm text-slate-600">Download all your photos and metadata as a ZIP archive.</p>
        <button
          type="button"
          onClick={handleExportArchive}
          disabled={isExporting}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-60"
        >
          {isExporting ? 'Preparing export...' : 'Export My Archive'}
        </button>
      </div>
    </div>
  );
}
