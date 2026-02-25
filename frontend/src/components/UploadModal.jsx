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

  const collectUploadFilesFromDirectory = useCallback(async (directoryHandle) => {
    const files = [];

    const visitDirectory = async (dirHandle) => {
      for await (const entry of dirHandle.values()) {
        if (entry.kind === 'file') {
          const file = await entry.getFile();
          const lowerName = file.name.toLowerCase();
          if (file.type?.startsWith('image/') || file.type === 'application/zip' || lowerName.endsWith('.zip')) {
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
      const files = await collectUploadFilesFromDirectory(directoryHandle);
      if (!files.length) {
        setFolderError('No image or ZIP files found in selected folder.');
        return;
      }
      await handleUpload(files);
    } catch (error) {
      if (error?.name === 'AbortError') return;
      setFolderError('Failed to read selected folder.');
    }
  }, [collectUploadFilesFromDirectory, handleUpload]);

  const onDrop = useCallback((acceptedFiles) => {
    void handleUpload(acceptedFiles);
  }, [handleUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: { 'image/*': [], 'application/zip': ['.zip'] },
  });

  const progressEntries = useMemo(() => Object.entries(progress), [progress]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="mb-4 text-xl font-semibold text-slate-900">Upload photos</h2>

        <div
          {...getRootProps()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
            isDragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50'
          }`}
        >
          <input {...getInputProps()} />
          <p className="text-slate-700">Drop photos or ZIP files here, or click to browse</p>
        </div>

        <div className="mt-3">
          <button
            type="button"
            onClick={() => void handleChooseFolder()}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            disabled={isUploading}
          >
            Choose a Folder
          </button>
          {folderError && (
            <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
              {folderError}
            </p>
          )}
        </div>

        {progressEntries.length > 0 && (
          <div className="mt-4 space-y-3">
            {progressEntries.map(([name, percent]) => (
              <div key={name}>
                <div className="mb-1 flex justify-between text-xs text-slate-600">
                  <span className="truncate">{name}</span>
                  <span>{percent}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded bg-slate-200">
                  <div className="h-full bg-blue-600 transition-all" style={{ width: `${percent}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {summary && (
          <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {summary.uploaded} uploaded, {summary.skipped} duplicate skipped, {summary.failed} failed
          </p>
        )}

        {errorMessage && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {errorMessage}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
            disabled={isUploading}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
