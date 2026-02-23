import { useEffect, useRef, useState } from 'react';
import {
  connectDriveSync,
  disconnectDriveSync,
  getSyncStatus,
  selectDriveFolder,
  triggerSync,
} from '../api/sync';

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
  });
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [runningSync, setRunningSync] = useState(false);
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
    }, 30_000);
    return () => clearInterval(poll);
  }, []);

  const openPicker = () => {
    const gapi = window.gapi;
    const google = window.google;
    const oauthToken = window.localStorage.getItem('google_access_token');
    const developerKey = import.meta.env.VITE_GOOGLE_API_KEY;

    if (!gapi?.picker || !google?.picker || !oauthToken || !developerKey) {
      setStatus('Picker requires gapi + oauth token + VITE_GOOGLE_API_KEY');
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
            {syncState.last_error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-red-700">{syncState.last_error}</p>
            )}
          </div>
        )}
        {status && <p className="mt-3 text-sm text-slate-600">{status}</p>}
      </div>
    </div>
  );
}
