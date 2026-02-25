import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { deleteAlbum, disableAlbumShare, enableAlbumShare, getAlbum, patchAlbum } from '../api/albums';
import Lightbox from '../components/Lightbox';
import PhotoGrid from '../components/PhotoGrid';

export default function AlbumDetail() {
  const { albumId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [nameError, setNameError] = useState('');
  const [openMenuPhotoId, setOpenMenuPhotoId] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [shareMessage, setShareMessage] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['album-detail', albumId],
    queryFn: async () => {
      const response = await getAlbum(albumId, { limit: 200, offset: 0 });
      return response.data;
    },
    enabled: !!albumId,
  });

  const photos = data?.photos || [];
  const albumName = data?.name || 'Album';
  const selectedIndex = useMemo(
    () => photos.findIndex((photo) => photo.id === selectedPhoto?.id),
    [photos, selectedPhoto]
  );

  const renameMutation = useMutation({
    mutationFn: async (name) => {
      const response = await patchAlbum(albumId, { name });
      return response.data;
    },
    onSuccess: () => {
      setIsEditingName(false);
      setNameError('');
      queryClient.invalidateQueries({ queryKey: ['album-detail', albumId] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
    onError: (error) => {
      setNameError(error?.response?.data?.detail || 'Unable to rename album');
    },
  });

  const setCoverMutation = useMutation({
    mutationFn: async (photoId) => {
      const response = await patchAlbum(albumId, { cover_photo_id: photoId });
      return response.data;
    },
    onSuccess: () => {
      setOpenMenuPhotoId(null);
      queryClient.invalidateQueries({ queryKey: ['album-detail', albumId] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await deleteAlbum(albumId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      navigate('/albums');
    },
  });

  const shareMutation = useMutation({
    mutationFn: async () => {
      if (data?.is_public) {
        await disableAlbumShare(albumId);
        return { disabled: true };
      }
      const response = await enableAlbumShare(albumId);
      return response.data;
    },
    onSuccess: async (result) => {
      if (!result?.disabled && result?.public_url) {
        const absoluteUrl = `${window.location.origin}${result.public_url}`;
        try {
          await navigator.clipboard.writeText(absoluteUrl);
          setShareMessage('Public link copied to clipboard');
        } catch {
          setShareMessage(`Public link: ${absoluteUrl}`);
        }
      } else {
        setShareMessage('Public sharing disabled');
      }
      queryClient.invalidateQueries({ queryKey: ['album-detail', albumId] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      setTimeout(() => setShareMessage(''), 2500);
    },
  });

  const startEditingName = () => {
    setEditedName(albumName);
    setNameError('');
    setIsEditingName(true);
  };

  const cancelEditingName = () => {
    setEditedName(albumName);
    setNameError('');
    setIsEditingName(false);
  };

  const saveName = () => {
    const trimmed = editedName.trim();
    if (!trimmed) {
      setNameError('Album name is required');
      return;
    }
    if (trimmed.length > 100) {
      setNameError('Album name must be 100 characters or fewer');
      return;
    }
    if (trimmed === albumName) {
      setIsEditingName(false);
      setNameError('');
      return;
    }
    renameMutation.mutate(trimmed);
  };

  const onNext = () => {
    if (selectedIndex < 0 || selectedIndex >= photos.length - 1) return;
    setSelectedPhoto(photos[selectedIndex + 1]);
  };

  const onPrev = () => {
    if (selectedIndex <= 0) return;
    setSelectedPhoto(photos[selectedIndex - 1]);
  };

  return (
    <div className="mx-auto max-w-[1600px] p-4 md:p-8">
      {isLoading && <div className="h-20 rounded-xl bg-surface animate-pulse" />}

      {!isLoading && isError && (
        <div className="glass-card border-warning/20 bg-warning/5 px-4 py-3 text-sm text-warning">
          Unable to load this album.
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              {isEditingName ? (
                <div>
                  <input
                    autoFocus
                    value={editedName}
                    onChange={(event) => {
                      setEditedName(event.target.value);
                      setNameError('');
                    }}
                    onBlur={saveName}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') saveName();
                      if (event.key === 'Escape') cancelEditingName();
                    }}
                    className="w-full max-w-xl input-dark text-2xl font-bold"
                    maxLength={100}
                  />
                  {nameError && <p className="mt-1 text-sm text-danger">{nameError}</p>}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={startEditingName}
                  className="text-left text-2xl font-bold text-foreground hover:text-accent-light transition-colors"
                >
                  {albumName}
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => shareMutation.mutate()}
                className="btn-secondary text-sm"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="18" cy="5" r="3" />
                  <circle cx="6" cy="12" r="3" />
                  <circle cx="18" cy="19" r="3" />
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                </svg>
                {data?.is_public ? 'Disable Share' : 'Share'}
              </button>
              <button
                type="button"
                onClick={() => setShowDeleteModal(true)}
                className="btn-ghost text-sm text-danger hover:bg-danger/10"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                Delete
              </button>
            </div>
          </div>

          {shareMessage && (
            <div className="mb-2 glass-card border-accent/20 bg-accent-muted px-4 py-2 text-sm text-accent-light animate-fade-in">
              {shareMessage}
            </div>
          )}

          <p className="mb-6 mt-1 text-sm text-foreground-muted">{data?.photo_count || 0} photos</p>

          {photos.length === 0 ? (
            <div className="glass-card border-dashed px-6 py-16 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-muted">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </div>
              <p className="text-foreground-muted">This album has no photos yet.</p>
            </div>
          ) : (
            <PhotoGrid
              photos={photos}
              onPhotoClick={setSelectedPhoto}
              renderActions={(photo) => (
                <div className="relative">
                  <button
                    type="button"
                    className="flex h-8 w-8 items-center justify-center rounded-lg bg-black/50 text-white backdrop-blur-sm transition-colors hover:bg-black/70"
                    onClick={() => setOpenMenuPhotoId((prev) => (prev === photo.id ? null : photo.id))}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <circle cx="12" cy="5" r="2" />
                      <circle cx="12" cy="12" r="2" />
                      <circle cx="12" cy="19" r="2" />
                    </svg>
                  </button>
                  {openMenuPhotoId === photo.id && (
                    <div className="absolute right-0 mt-1 w-44 glass-card p-1 shadow-2xl animate-fade-in">
                      <button
                        type="button"
                        onClick={() => setCoverMutation.mutate(photo.id)}
                        className="block w-full rounded-lg px-3 py-2 text-left text-sm text-foreground hover:bg-surface-hover"
                        disabled={setCoverMutation.isPending}
                      >
                        Set as cover photo
                      </button>
                    </div>
                  )}
                </div>
              )}
            />
          )}
        </>
      )}

      <Lightbox
        photo={selectedPhoto}
        isOpen={!!selectedPhoto}
        onClose={() => setSelectedPhoto(null)}
        onNext={onNext}
        onPrev={onPrev}
      />

      {/* Delete album modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md glass-card p-5 animate-slide-up">
            <h2 className="text-lg font-semibold text-foreground">Delete this album?</h2>
            <p className="mt-2 text-sm text-foreground-muted">
              Your photos will not be deleted, only the album.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
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
                {deleteMutation.isPending ? 'Deleting...' : 'Delete Album'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
