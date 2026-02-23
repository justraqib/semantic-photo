import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createAlbum } from '../api/albums';
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
  const queryClient = useQueryClient();
  const { albums, isLoading, isError } = useAlbums();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  const createMutation = useMutation({
    mutationFn: async (albumName) => {
      const response = await createAlbum({ name: albumName });
      return response.data;
    },
    onSuccess: () => {
      setName('');
      setError('');
      setIsModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['albums'] });
    },
    onError: (mutationError) => {
      setError(mutationError?.response?.data?.detail || 'Failed to create album');
    },
  });

  const onCreate = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Album name is required');
      return;
    }
    if (trimmed.length > 100) {
      setError('Album name must be 100 characters or fewer');
      return;
    }
    createMutation.mutate(trimmed);
  };

  return (
    <div className="mx-auto max-w-[1600px] p-4 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Albums</h1>
          <p className="mt-1 text-sm text-slate-500">Group your photos into collections.</p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          + New Album
        </button>
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

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-900">Create Album</h2>
            <p className="mt-1 text-sm text-slate-500">Name your album.</p>
            <input
              autoFocus
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setError('');
              }}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setIsModalOpen(false);
                  setError('');
                  setName('');
                }
                if (event.key === 'Enter') {
                  onCreate();
                }
              }}
              className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-500"
              placeholder="Album name"
              maxLength={100}
            />
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setIsModalOpen(false);
                  setError('');
                  setName('');
                }}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                disabled={createMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onCreate}
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
