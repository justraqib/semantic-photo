import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { addAlbumPhotos } from '../api/albums';
import { getPhotoById, softDeletePhoto } from '../api/photos';
import { useAlbums } from '../hooks/useAlbums';

function DetailRow({ icon, label, value }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-3 py-2">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-light text-foreground-dim">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-foreground-dim">{label}</p>
        <p className="text-sm text-foreground truncate">{value}</p>
      </div>
    </div>
  );
}

export default function Lightbox({ photo, isOpen, onClose, onNext, onPrev }) {
  const [fullUrl, setFullUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showAlbumMenu, setShowAlbumMenu] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [albumMessage, setAlbumMessage] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(false);
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

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await softDeletePhoto(photo.id);
    },
    onSuccess: () => {
      setDeleteConfirm(false);
      onClose?.();
    },
  });

  useEffect(() => {
    if (!isOpen || !photo?.id) {
      setFullUrl(null);
      setShowAlbumMenu(false);
      setAlbumMessage('');
      setShowSidebar(false);
      setDeleteConfirm(false);
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
      if (event.key === 'i') setShowSidebar((prev) => !prev);
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose, onNext, onPrev]);

  if (!isOpen) return null;

  const takenAt = photo?.taken_at ? new Date(photo.taken_at) : null;
  const dateLabel =
    takenAt && !Number.isNaN(takenAt.getTime())
      ? takenAt.toLocaleDateString('en-US', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        })
      : null;
  const timeLabel =
    takenAt && !Number.isNaN(takenAt.getTime())
      ? takenAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
      : null;

  const handleDownload = () => {
    const url = fullUrl || photo?.thumbnail_url;
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = photo?.original_filename || 'photo';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="fixed inset-0 z-50 flex bg-black/95" role="dialog" aria-modal="true">
      {/* Main photo area */}
      <div className="relative flex flex-1 items-center justify-center" onClick={onClose}>
        {/* Top bar */}
        <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm transition-colors hover:bg-white/20"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          <div className="flex items-center gap-2">
            {/* Add to Album */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowAlbumMenu((prev) => !prev)}
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm transition-colors hover:bg-white/20"
                aria-label="Add to album"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
              {showAlbumMenu && (
                <div className="absolute right-0 mt-2 w-56 glass-card p-1 shadow-2xl animate-fade-in">
                  <p className="px-3 py-2 text-xs font-medium text-foreground-dim">Add to album</p>
                  {albums.length === 0 && (
                    <div className="px-3 py-2 text-sm text-foreground-muted">No albums available</div>
                  )}
                  {albums.map((album) => (
                    <button
                      key={album.id}
                      type="button"
                      onClick={() => addToAlbumMutation.mutate(album.id)}
                      className="block w-full rounded-lg px-3 py-2 text-left text-sm text-foreground hover:bg-surface-hover"
                      disabled={addToAlbumMutation.isPending}
                    >
                      {album.name}
                    </button>
                  ))}
                </div>
              )}
              {albumMessage && (
                <div className="absolute right-0 mt-2 rounded-lg bg-surface px-3 py-1.5 text-xs text-foreground-muted shadow-lg animate-fade-in">
                  {albumMessage}
                </div>
              )}
            </div>

            {/* Download */}
            <button
              type="button"
              onClick={handleDownload}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm transition-colors hover:bg-white/20"
              aria-label="Download"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </button>

            {/* Delete */}
            <button
              type="button"
              onClick={() => setDeleteConfirm(true)}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm transition-colors hover:bg-danger/30"
              aria-label="Delete"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>

            {/* Info toggle */}
            <button
              type="button"
              onClick={() => setShowSidebar((prev) => !prev)}
              className={`flex h-10 w-10 items-center justify-center rounded-xl backdrop-blur-sm transition-colors ${
                showSidebar ? 'bg-accent text-white' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
              aria-label="Photo info"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
            </button>
          </div>
        </div>

        {/* Nav arrows */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onPrev?.();
          }}
          className="absolute left-4 z-10 flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm transition-all hover:bg-white/20"
          aria-label="Previous photo"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <div className="max-h-[90vh] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
          {loading ? (
            <div className="flex h-64 w-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white" />
            </div>
          ) : (
            <img
              src={fullUrl || photo?.thumbnail_url}
              alt={photo?.original_filename || 'Photo'}
              className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain"
            />
          )}
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onNext?.();
          }}
          className="absolute right-4 z-10 flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 text-white backdrop-blur-sm transition-all hover:bg-white/20"
          aria-label="Next photo"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* Info sidebar */}
      {showSidebar && (
        <div
          className="w-80 shrink-0 overflow-y-auto border-l border-surface-border bg-background/95 backdrop-blur-xl p-5 animate-slide-in-right"
          onClick={(e) => e.stopPropagation()}
        >
          <h3 className="mb-4 text-lg font-semibold text-foreground">Photo Details</h3>

          <div className="mb-4 overflow-hidden rounded-xl">
            <img
              src={photo?.thumbnail_url}
              alt=""
              className="w-full object-cover"
            />
          </div>

          <div className="flex flex-col divide-y divide-surface-border">
            <DetailRow
              icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              }
              label="Date"
              value={dateLabel}
            />
            <DetailRow
              icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              }
              label="Time"
              value={timeLabel}
            />
            <DetailRow
              icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                </svg>
              }
              label="Filename"
              value={photo?.original_filename}
            />
            {(photo?.gps_lat && photo?.gps_lng) && (
              <DetailRow
                icon={
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                    <circle cx="12" cy="10" r="3" />
                  </svg>
                }
                label="Location"
                value={`${Number(photo.gps_lat).toFixed(4)}, ${Number(photo.gps_lng).toFixed(4)}`}
              />
            )}
          </div>

          <p className="mt-6 text-xs text-foreground-dim">
            Press <kbd className="rounded bg-surface-light px-1.5 py-0.5 text-xs font-mono">i</kbd> to toggle info
          </p>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={(e) => e.stopPropagation()}>
          <div className="w-full max-w-sm glass-card p-5 animate-slide-up">
            <h2 className="text-lg font-semibold text-foreground">Delete this photo?</h2>
            <p className="mt-2 text-sm text-foreground-muted">
              This action will move the photo to trash.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirm(false)}
                className="btn-secondary text-sm"
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteMutation.mutate()}
                className="btn-danger text-sm"
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
