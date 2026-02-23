import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getAlbum, patchAlbum } from '../api/albums';
import Lightbox from '../components/Lightbox';
import PhotoGrid from '../components/PhotoGrid';

export default function AlbumDetail() {
  const { albumId } = useParams();
  const queryClient = useQueryClient();
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [nameError, setNameError] = useState('');

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
          {isEditingName ? (
            <div className="mb-2">
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
          <p className="mb-6 mt-1 text-sm text-slate-500">{data?.photo_count || 0} photos</p>

          {photos.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center text-slate-500">
              This album has no photos yet.
            </div>
          ) : (
            <PhotoGrid photos={photos} onPhotoClick={setSelectedPhoto} />
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
    </div>
  );
}
