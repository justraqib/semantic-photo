import { useCallback, useState } from 'react';
import { previewUploadPhotos, uploadPhotos } from '../api/photos';

function getUploadErrorMessage(error) {
  return error?.response?.data?.detail || 'Upload failed. Please try again.';
}

export function useUpload({ onUploaded, onComplete } = {}) {
  const [pendingFiles, setPendingFiles] = useState([]);
  const [preview, setPreview] = useState(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [progress, setProgress] = useState({});
  const [summary, setSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const reset = useCallback(() => {
    setPendingFiles([]);
    setPreview(null);
    setIsPreviewing(false);
    setProgress({});
    setSummary(null);
    setErrorMessage('');
    setIsUploading(false);
  }, []);

  const prepareUpload = useCallback(async (files) => {
    if (!files?.length) return;
    setErrorMessage('');
    setSummary(null);
    setPreview(null);
    setPendingFiles(files);
    setIsPreviewing(true);

    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      const response = await previewUploadPhotos(formData);
      setPreview(response.data);
    } catch (error) {
      setErrorMessage(getUploadErrorMessage(error));
    } finally {
      setIsPreviewing(false);
    }
  }, []);

  const handleUpload = useCallback(
    async (files = pendingFiles) => {
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
      setPendingFiles([]);
      setPreview(null);
    },
    [onUploaded, onComplete, pendingFiles]
  );

  return {
    pendingFiles,
    preview,
    isPreviewing,
    progress,
    summary,
    errorMessage,
    isUploading,
    reset,
    prepareUpload,
    handleUpload,
  };
}
