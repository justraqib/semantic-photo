import AlbumCard from '../components/AlbumCard';
import { useAlbums } from '../hooks/useAlbums';

function AlbumsEmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
      <div className="text-4xl">🗂️</div>
      <h2 className="mt-3 text-lg font-semibold text-slate-800">No albums yet</h2>
      <p className="mt-1 text-sm text-slate-500">Create your first album to organize photos.</p>
    </div>
  );
}

export default function Albums() {
  const { albums, isLoading, isError } = useAlbums();

  return (
    <div className="mx-auto max-w-[1600px] p-4 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Albums</h1>
          <p className="mt-1 text-sm text-slate-500">Group your photos into collections.</p>
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-56 animate-pulse rounded-xl bg-slate-200" />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          Unable to load albums right now.
        </div>
      )}

      {!isLoading && !isError && albums.length === 0 && <AlbumsEmptyState />}

      {!isLoading && !isError && albums.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      )}
    </div>
  );
}
