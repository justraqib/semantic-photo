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
      {isLoading && <div className="rounded-xl bg-slate-200 p-8 animate-pulse" />}

      {!isLoading && isError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          Unable to load this album.
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <div className="mb-2 flex items-start justify-between gap-4">
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
                    className="w-full max-w-xl rounded-lg border border-slate-300 px-3 py-2 text-2xl font-bold text-slate-900 outline-none focus:border-slate-500"
                    maxLength={100}
                  />
                  {nameError && <p className="mt-1 text-sm text-red-600">{nameError}</p>}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={startEditingName}
                  className="text-left text-2xl font-bold text-slate-900 hover:text-slate-700"
                >
                  {albumName}
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => shareMutation.mutate()}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              {data?.is_public ? 'Disable Share' : 'Share Album'}
            </button>
            <button
              type="button"
              onClick={() => setShowDeleteModal(true)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Delete Album
            </button>
          </div>
          {shareMessage && (
            <p className="mb-2 rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-700">{shareMessage}</p>
          )}
          <p className="mb-6 mt-1 text-sm text-slate-500">{data?.photo_count || 0} photos</p>

          {photos.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center text-slate-500">
              This album has no photos yet.
            </div>
          ) : (
            <PhotoGrid
              photos={photos}
              onPhotoClick={setSelectedPhoto}
              renderActions={(photo) => (
                <div className="relative">
                  <button
                    type="button"
                    className="rounded bg-white/90 px-2 py-1 text-sm shadow hover:bg-white"
                    onClick={() => setOpenMenuPhotoId((prev) => (prev === photo.id ? null : photo.id))}
                  >
                    ⋯
                  </button>
                  {openMenuPhotoId === photo.id && (
                    <div className="absolute right-0 mt-1 w-44 rounded-lg border border-slate-200 bg-white p-1 shadow-xl">
                      <button
                        type="button"
                        onClick={() => setCoverMutation.mutate(photo.id)}
                        className="block w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
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

      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-900">Delete this album?</h2>
            <p className="mt-2 text-sm text-slate-600">
              Delete this album? Your photos will not be deleted.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteMutation.mutate()}
                className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-60"
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
