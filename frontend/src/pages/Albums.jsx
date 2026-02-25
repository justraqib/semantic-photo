import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createAlbum } from '../api/albums';
import AlbumCard from '../components/AlbumCard';
import { useAlbums } from '../hooks/useAlbums';

function AlbumsEmptyState() {
  return (
    <div className="glass-card border-dashed px-6 py-16 text-center animate-fade-in">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-muted">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-foreground">No albums yet</h2>
      <p className="mt-1 text-sm text-foreground-muted">Create your first album to organize photos.</p>
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
          <h1 className="text-2xl font-bold text-foreground">Albums</h1>
          <p className="mt-1 text-sm text-foreground-muted">Group your photos into collections.</p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="btn-primary"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Album
        </button>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-56 animate-pulse rounded-xl bg-surface" />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <div className="glass-card border-warning/20 bg-warning/5 px-4 py-3 text-sm text-warning">
          Unable to load albums right now.
        </div>
      )}

      {!isLoading && !isError && albums.length === 0 && <AlbumsEmptyState />}

      {!isLoading && !isError && albums.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      )}

      {/* Create Album Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md glass-card p-5 animate-slide-up">
            <h2 className="text-lg font-semibold text-foreground">Create Album</h2>
            <p className="mt-1 text-sm text-foreground-muted">Name your album.</p>
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
              className="input-dark mt-4"
              placeholder="Album name"
              maxLength={100}
            />
            {error && <p className="mt-2 text-sm text-danger">{error}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setIsModalOpen(false);
                  setError('');
                  setName('');
                }}
                className="btn-secondary text-sm"
                disabled={createMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onCreate}
                className="btn-primary text-sm"
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
