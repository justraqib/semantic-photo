import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import EmptyState from '../components/EmptyState';
import Lightbox from '../components/Lightbox';
import PhotoGrid from '../components/PhotoGrid';
import SearchEmptyState from '../components/SearchEmptyState';
import SearchBar from '../components/SearchBar';
import SearchResults from '../components/SearchResults';
import UploadModal from '../components/UploadModal';
import { startEmbedding } from '../api/photos';
import { useEmbeddingStatus } from '../hooks/useEmbeddingStatus';
import { useMemories } from '../hooks/useMemories';
import { usePhotos } from '../hooks/usePhotos';
import { useSearch } from '../hooks/useSearch';

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="h-40 animate-pulse rounded-xl bg-slate-200 md:h-48" />
      ))}
    </div>
  );
}

export default function Gallery() {
  const queryClient = useQueryClient();
  const { photos, fetchNextPage, hasNextPage, isLoading } = usePhotos();
  const [query, setQuery] = useState('');
  const { results: searchResults, isLoading: isSearching, isError: isSearchError } = useSearch(query);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isMemoryExpanded, setIsMemoryExpanded] = useState(false);
  const [isMemoryDismissed, setIsMemoryDismissed] = useState(false);
  const sentinelRef = useRef(null);
  const { memory } = useMemories();
  const { status: embeddingStatus } = useEmbeddingStatus();
  const isSearchActive = query.trim().length >= 2;
  const clearSearch = () => setQuery('');
  const pendingEmbeddings = embeddingStatus?.pending_for_user || 0;
  const progressPercent = embeddingStatus?.progress_percent ?? 0;
  const etaSeconds = embeddingStatus?.eta_seconds || 0;
  const etaMinutes = Math.max(1, Math.ceil(etaSeconds / 60));
  const queueLength = embeddingStatus?.queue_length || 0;

  const startEmbeddingMutation = useMutation({
    mutationFn: startEmbedding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-status'] });
    },
  });

  const selectedIndex = useMemo(
    () => photos.findIndex((p) => p.id === selectedPhoto?.id),
    [photos, selectedPhoto]
  );

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (first?.isIntersecting && hasNextPage) {
          void fetchNextPage();
        }
      },
      { rootMargin: '200px' }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage]);

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
      {!isMemoryDismissed && memory && (
        <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-start justify-between gap-3">
            <button
              type="button"
              onClick={() => setIsMemoryExpanded((prev) => !prev)}
              className="text-left"
            >
              <p className="text-sm font-semibold text-emerald-900">
                📅 {memory.label} today — {memory.photo_count} photos
              </p>
              <p className="mt-1 text-xs text-emerald-700">
                Tap to {isMemoryExpanded ? 'collapse' : 'expand'}
              </p>
            </button>
            <button
              type="button"
              onClick={() => setIsMemoryDismissed(true)}
              className="rounded px-2 py-1 text-sm text-emerald-700 hover:bg-emerald-100"
              aria-label="Dismiss memories banner"
            >
              ×
            </button>
          </div>

          {isMemoryExpanded && (
            <div className="mt-3 flex gap-3 overflow-x-auto pb-1">
              {memory.photos.map((photo) => (
                <button
                  key={photo.id}
                  type="button"
                  onClick={() => setSelectedPhoto(photo)}
                  className="shrink-0 overflow-hidden rounded-lg border border-emerald-200 bg-white"
                >
                  <img
                    src={photo.thumbnail_url}
                    alt="Memory"
                    className="h-24 w-24 object-cover md:h-28 md:w-28"
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <SearchBar
        onSearch={setQuery}
        onClear={clearSearch}
        isSearching={isSearching}
      />

      {pendingEmbeddings > 0 && (
        <div className="mb-4 rounded-2xl border border-cyan-200 bg-gradient-to-r from-cyan-50 via-sky-50 to-indigo-50 p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-slate-800">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-500" />
              <p className="text-sm font-semibold">AI indexing in progress</p>
            </div>
            <button
              type="button"
              onClick={() => startEmbeddingMutation.mutate()}
              disabled={startEmbeddingMutation.isPending}
              className="rounded-lg border border-cyan-300 bg-white px-3 py-1.5 text-xs font-medium text-cyan-700 hover:bg-cyan-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {startEmbeddingMutation.isPending ? 'Starting...' : 'Start/Retry Now'}
            </button>
          </div>

          <div className="mb-2 h-2.5 overflow-hidden rounded-full bg-white">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-600 transition-all duration-700"
              style={{ width: `${Math.max(2, progressPercent)}%` }}
            />
          </div>

          <p className="text-xs text-slate-700">
            {pendingEmbeddings} photo{pendingEmbeddings > 1 ? 's' : ''} not embedded yet • Queue {queueLength} • ETA ~{etaMinutes} min
          </p>
        </div>
      )}

      {isSearchActive && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-700">
          <span>
            Showing results for "{query}"
          </span>
          <button
            type="button"
            onClick={clearSearch}
            className="rounded-md px-2 py-1 text-xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Clear search"
          >
            ×
          </button>
        </div>
      )}

      {isLoading && photos.length === 0 && <SkeletonGrid />}

      {!isLoading && photos.length === 0 && (
        <EmptyState message="Upload your first photo to get started" />
      )}

      {(!isSearchActive || isSearchError) && photos.length > 0 && (
        <PhotoGrid photos={photos} onPhotoClick={setSelectedPhoto} />
      )}

      {isSearchActive && (
        <>
          {isSearchError && (
            <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
              Search is temporarily unavailable. Try again in a moment.
            </div>
          )}
          {!isSearchError && isSearching && <SkeletonGrid />}
          {!isSearchError && !isSearching && searchResults.length === 0 && (
            <SearchEmptyState query={query} onClear={clearSearch} />
          )}
          {!isSearchError && searchResults.length > 0 && (
            <SearchResults results={searchResults} onPhotoClick={setSelectedPhoto} />
          )}
        </>
      )}

      {(!isSearchActive || isSearchError) && <div ref={sentinelRef} className="h-8" />}

      <button
        type="button"
        onClick={() => setIsUploadOpen(true)}
        className="fixed bottom-6 right-6 z-30 h-14 w-14 rounded-full bg-blue-600 text-3xl text-white shadow-lg hover:bg-blue-500"
        aria-label="Upload photos"
      >
        +
      </button>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploaded={() => {
          queryClient.invalidateQueries({ queryKey: ['photos'] });
          queryClient.invalidateQueries({ queryKey: ['embedding-status'] });
        }}
      />

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
