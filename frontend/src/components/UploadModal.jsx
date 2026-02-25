import { useCallback, useEffect, useMemo, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useUpload } from '../hooks/useUpload';

export default function UploadModal({ isOpen, onClose, onUploaded }) {
  const [folderError, setFolderError] = useState('');
  const {
    progress,
    summary,
    errorMessage,
    isUploading,
    reset,
    handleUpload,
  } = useUpload({
    onUploaded,
    onComplete: (result) => {
      if (result.failed === 0) {
        setTimeout(() => {
          onClose?.();
        }, 3000);
      }
    },
  });

  useEffect(() => {
    if (!isOpen) reset();
  }, [isOpen, reset]);

  const collectImageFilesFromDirectory = useCallback(async (directoryHandle) => {
    const files = [];
    const visitDirectory = async (dirHandle) => {
      for await (const entry of dirHandle.values()) {
        if (entry.kind === 'file') {
          const file = await entry.getFile();
          if (file.type?.startsWith('image/')) {
            files.push(file);
          }
        } else if (entry.kind === 'directory') {
          await visitDirectory(entry);
        }
      }
    };
    await visitDirectory(directoryHandle);
    return files;
  }, []);

  const handleChooseFolder = useCallback(async () => {
    setFolderError('');
    if (!window.showDirectoryPicker) {
      setFolderError('Folder picker is not supported in this browser.');
      return;
    }
    try {
      const directoryHandle = await window.showDirectoryPicker();
      const files = await collectImageFilesFromDirectory(directoryHandle);
      if (!files.length) {
        setFolderError('No image files found in selected folder.');
        return;
      }
      await handleUpload(files);
    } catch (error) {
      if (error?.name === 'AbortError') return;
      setFolderError('Failed to read selected folder.');
    }
  }, [collectImageFilesFromDirectory, handleUpload]);

  const onDrop = useCallback(
    (acceptedFiles) => {
      void handleUpload(acceptedFiles);
    },
    [handleUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: { 'image/*': [] },
  });

  const progressEntries = useMemo(() => Object.entries(progress), [progress]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl glass-card p-6 animate-slide-up">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">Upload photos</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-foreground-dim transition-colors hover:bg-surface-hover hover:text-foreground disabled:opacity-40"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div
          {...getRootProps()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-all duration-300 ${
            isDragActive
              ? 'border-accent bg-accent-muted'
              : 'border-surface-border bg-surface hover:border-foreground-dim'
          }`}
        >
          <input {...getInputProps()} />
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-muted">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <p className="text-foreground">
            {isDragActive ? 'Drop photos here' : 'Drop photos here or click to browse'}
          </p>
          <p className="mt-1 text-sm text-foreground-dim">Supports JPG, PNG, WebP, HEIC</p>
        </div>

        <div className="mt-3">
          <button
            type="button"
            onClick={() => void handleChooseFolder()}
            className="btn-secondary text-sm"
            disabled={isUploading}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            Choose a Folder
          </button>
          {folderError && (
            <p className="mt-2 rounded-lg bg-warning/10 border border-warning/20 px-3 py-2 text-sm text-warning">
              {folderError}
            </p>
          )}
        </div>

        {progressEntries.length > 0 && (
          <div className="mt-4 max-h-40 overflow-y-auto rounded-xl bg-surface p-3">
            <div className="space-y-3">
              {progressEntries.map(([name, percent]) => (
                <div key={name}>
                  <div className="mb-1 flex justify-between text-xs text-foreground-muted">
                    <span className="truncate">{name}</span>
                    <span>{percent}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-surface-light">
                    <div
                      className="h-full rounded-full bg-accent transition-all duration-500"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {summary && (
          <div className="mt-4 rounded-xl bg-success/10 border border-success/20 px-4 py-3 text-sm text-success">
            {summary.uploaded} uploaded, {summary.skipped} duplicate skipped, {summary.failed} failed
          </div>
        )}

        {errorMessage && (
          <div className="mt-3 rounded-xl bg-danger/10 border border-danger/20 px-4 py-3 text-sm text-danger">
            {errorMessage}
          </div>
        )}
      </div>
    </div>
  );
}
