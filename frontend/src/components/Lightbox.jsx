import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { addAlbumPhotos } from '../api/albums';
import { getPhotoById } from '../api/photos';
import { useAlbums } from '../hooks/useAlbums';

export default function Lightbox({ photo, isOpen, onClose, onNext, onPrev }) {
  const [fullUrl, setFullUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showAlbumMenu, setShowAlbumMenu] = useState(false);
  const [albumMessage, setAlbumMessage] = useState('');
  const { albums } = useAlbums();

  const addToAlbumMutation = useMutation({
    mutationFn: async (albumId) => {
      await addAlbumPhotos(albumId, { photo_ids: [photo.id] });
    },
    onSuccess: () => {
      setAlbumMessage('Added to album');
      setTimeout(() => setAlbumMessage(''), 1500);
      setShowAlbumMenu(false);
    },
    onError: () => {
      setAlbumMessage('Failed to add photo');
      setTimeout(() => setAlbumMessage(''), 2000);
    },
  });

  useEffect(() => {
    if (!isOpen || !photo?.id) {
      setFullUrl(null);
      setShowAlbumMenu(false);
      setAlbumMessage('');
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

      <div className="absolute left-4 top-4" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => setShowAlbumMenu((prev) => !prev)}
          className="rounded bg-white/20 px-3 py-2 text-sm text-white hover:bg-white/30"
        >
          Add to Album
        </button>
        {showAlbumMenu && (
          <div className="mt-2 w-56 rounded-lg border border-slate-200 bg-white p-1 shadow-xl">
            {albums.length === 0 && (
              <div className="px-3 py-2 text-sm text-slate-500">No albums available</div>
            )}
            {albums.map((album) => (
              <button
                key={album.id}
                type="button"
                onClick={() => addToAlbumMutation.mutate(album.id)}
                className="block w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                disabled={addToAlbumMutation.isPending}
              >
                {album.name}
              </button>
            ))}
          </div>
        )}
        {albumMessage && (
          <div className="mt-2 rounded bg-white/90 px-2 py-1 text-xs text-slate-700">
            {albumMessage}
          </div>
        )}
      </div>
    </div>
  );
}
