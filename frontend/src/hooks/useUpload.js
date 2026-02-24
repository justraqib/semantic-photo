import { useCallback, useState } from 'react';
import { uploadPhotos } from '../api/photos';

function getUploadErrorMessage(error) {
  return error?.response?.data?.detail || 'Upload failed. Please try again.';
}

export function useUpload({ onUploaded, onComplete } = {}) {
  const [progress, setProgress] = useState({});
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const reset = useCallback(() => {
    setProgress({});
    setSummary(null);
    setErrorMessage('');
    setIsUploading(false);
  }, []);

  const handleUpload = useCallback(
    async (files) => {
      if (!files?.length) return;

      setIsUploading(true);
      setErrorMessage('');
      let uploaded = 0;
      let skipped = 0;
      let failed = 0;

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
        } catch (error) {
          failed += 1;
          setProgress((prev) => ({ ...prev, [file.name]: 0 }));
          setErrorMessage(getUploadErrorMessage(error));
        }
      }

      const nextSummary = { uploaded, skipped, failed };
      setSummary(nextSummary);
      setIsUploading(false);

      if (uploaded > 0) onUploaded?.();
      onComplete?.(nextSummary);
    },
    [onUploaded, onComplete]
  );

  return {
    progress,
    summary,
    errorMessage,
    isUploading,
    reset,
    handleUpload,
  };
}
