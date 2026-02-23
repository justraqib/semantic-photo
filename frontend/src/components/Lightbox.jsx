import { useEffect, useState } from 'react';
import { getPhotoById } from '../api/photos';

export default function Lightbox({ photo, isOpen, onClose, onNext, onPrev }) {
  const [fullUrl, setFullUrl] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !photo?.id) {
      setFullUrl(null);
      return;
    }

    let active = true;
    setLoading(true);

    getPhotoById(photo.id)
      .then((res) => {
        if (active) setFullUrl(res.data?.url || null);
      })
      .catch(() => {
        if (active) setFullUrl(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, photo?.id]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
      if (event.key === 'ArrowLeft') onPrev?.();
      if (event.key === 'ArrowRight') onNext?.();
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose, onNext, onPrev]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onPrev?.();
        }}
        className="absolute left-4 rounded-full bg-white/20 px-3 py-2 text-white hover:bg-white/30"
        aria-label="Previous photo"
      >
        ←
      </button>

      <div className="max-h-[90vh] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
        {loading ? (
          <div className="text-white">Loading...</div>
        ) : (
          <img
            src={fullUrl || photo?.thumbnail_url}
            alt={photo?.original_filename || 'Photo'}
            className="max-h-[90vh] max-w-[90vw] rounded object-contain"
          />
        )}
      </div>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onNext?.();
        }}
        className="absolute right-4 rounded-full bg-white/20 px-3 py-2 text-white hover:bg-white/30"
        aria-label="Next photo"
      >
        →
      </button>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClose?.();
        }}
        className="absolute right-4 top-4 rounded bg-white/20 px-3 py-2 text-sm text-white hover:bg-white/30"
      >
        Close
      </button>
    </div>
  );
}
