import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getAlbum } from '../api/albums';
import Lightbox from '../components/Lightbox';
import PhotoGrid from '../components/PhotoGrid';

export default function AlbumDetail() {
  const { albumId } = useParams();
  const [selectedPhoto, setSelectedPhoto] = useState(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['album-detail', albumId],
    queryFn: async () => {
      const response = await getAlbum(albumId, { limit: 200, offset: 0 });
      return response.data;
    },
    enabled: !!albumId,
  });

  const photos = data?.photos || [];
  const selectedIndex = useMemo(
    () => photos.findIndex((photo) => photo.id === selectedPhoto?.id),
    [photos, selectedPhoto]
  );

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
          <h1 className="text-2xl font-bold text-slate-900">{data?.name || 'Album'}</h1>
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
