import { useCallback, useEffect, useMemo, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadPhotos } from '../api/photos';

export default function UploadModal({ isOpen, onClose, onUploaded }) {
  const [progress, setProgress] = useState({});
  const [summary, setSummary] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const reset = useCallback(() => {
    setProgress({});
    setSummary(null);
    setIsUploading(false);
  }, []);

  useEffect(() => {
    if (!isOpen) reset();
  }, [isOpen, reset]);

  const handleUpload = useCallback(async (files) => {
    if (!files?.length) return;

    setIsUploading(true);
    let uploaded = 0;
    let skipped = 0;

    for (const file of files) {
      const formData = new FormData();
      formData.append('files', file);

      try {
        const response = await uploadPhotos(formData, (evt) => {
          const percent = evt.total ? Math.round((evt.loaded / evt.total) * 100) : 0;
          setProgress((prev) => ({ ...prev, [file.name]: percent }));
        });

        uploaded += response.data?.uploaded ?? 0;
        skipped += response.data?.skipped ?? 0;
      } catch {
        setProgress((prev) => ({ ...prev, [file.name]: 0 }));
      }
    }

    setSummary({ uploaded, skipped });
    setIsUploading(false);
    onUploaded?.();

    setTimeout(() => {
      onClose?.();
    }, 3000);
  }, [onClose, onUploaded]);

  const onDrop = useCallback((acceptedFiles) => {
    void handleUpload(acceptedFiles);
  }, [handleUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: { 'image/*': [] },
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
          <p className="text-slate-700">Drop photos here or click to browse</p>
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
            {summary.uploaded} uploaded, {summary.skipped} duplicate skipped
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
