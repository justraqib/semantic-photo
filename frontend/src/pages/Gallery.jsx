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
        <div
          key={i}
          className="animate-pulse rounded-xl bg-surface"
          style={{ height: `${160 + (i % 3) * 40}px` }}
        />
      ))}
    </div>
  );
}

function MemoryCard({ memory, onPhotoClick }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="mb-6 glass-card-hover p-4 animate-slide-up">
      <div className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="text-left"
        >
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-muted">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent-light">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                {memory.label} today
              </p>
              <p className="text-xs text-foreground-muted">
                {memory.photo_count} photos &middot; Tap to {isExpanded ? 'collapse' : 'explore'}
              </p>
            </div>
          </div>
        </button>
      </div>

      {isExpanded && (
        <div className="mt-3 flex gap-3 overflow-x-auto pb-1 scrollbar-thin">
          {memory.photos.map((photo) => (
            <button
              key={photo.id}
              type="button"
              onClick={() => onPhotoClick(photo)}
              className="shrink-0 overflow-hidden rounded-xl border border-surface-border transition-all duration-300 hover:ring-2 hover:ring-accent/30"
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
  );
}

function EmbeddingProgress({ status, onStart, isPending }) {
  const pendingEmbeddings = status?.pending_for_user || 0;
  const progressPercent = status?.progress_percent ?? 0;
  const etaSeconds = status?.eta_seconds || 0;
  const etaMinutes = Math.max(1, Math.ceil(etaSeconds / 60));
  const queueLength = status?.queue_length || 0;

  if (pendingEmbeddings <= 0) return null;

  return (
    <div className="mb-6 glass-card p-4 animate-fade-in">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-8 w-8 items-center justify-center">
            <div className="absolute inset-0 animate-pulse-slow rounded-lg bg-accent/20" />
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="relative text-accent-light">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">AI indexing in progress</p>
            <p className="text-xs text-foreground-muted">
              {pendingEmbeddings} photo{pendingEmbeddings > 1 ? 's' : ''} remaining &middot; Queue {queueLength} &middot; ~{etaMinutes} min
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onStart}
          disabled={isPending}
          className="btn-secondary text-xs px-3 py-1.5"
        >
          {isPending ? 'Starting...' : 'Retry'}
        </button>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-surface-light">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-light transition-all duration-700"
          style={{ width: `${Math.max(2, progressPercent)}%` }}
        />
      </div>
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
  const sentinelRef = useRef(null);
  const { memory } = useMemories();
  const { status: embeddingStatus } = useEmbeddingStatus();
  const isSearchActive = query.trim().length >= 2;
  const clearSearch = () => setQuery('');

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
      {/* Memory card */}
      {memory && (
        <MemoryCard memory={memory} onPhotoClick={setSelectedPhoto} />
      )}

      {/* Search bar */}
      <SearchBar onSearch={setQuery} onClear={clearSearch} isSearching={isSearching} />

      {/* Embedding progress */}
      <EmbeddingProgress
        status={embeddingStatus}
        onStart={() => startEmbeddingMutation.mutate()}
        isPending={startEmbeddingMutation.isPending}
      />

      {/* Search active indicator */}
      {isSearchActive && (
        <div className="mb-4 flex items-center justify-between glass-card px-4 py-3 animate-fade-in">
          <span className="text-sm text-foreground-muted">
            {'Showing results for "' + query + '"'}
          </span>
          <button
            type="button"
            onClick={clearSearch}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-foreground-dim transition-colors hover:bg-surface-hover hover:text-foreground"
            aria-label="Clear search"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && photos.length === 0 && <SkeletonGrid />}

      {/* Empty state */}
      {!isLoading && photos.length === 0 && (
        <EmptyState message="Upload your first photo to get started" />
      )}

      {/* Photo grid */}
      {(!isSearchActive || isSearchError) && photos.length > 0 && (
        <PhotoGrid photos={photos} onPhotoClick={setSelectedPhoto} />
      )}

      {/* Search results */}
      {isSearchActive && (
        <>
          {isSearchError && (
            <div className="mb-4 glass-card border-warning/20 bg-warning/5 px-4 py-3 text-sm text-warning animate-fade-in">
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

      {/* Infinite scroll sentinel */}
      {(!isSearchActive || isSearchError) && <div ref={sentinelRef} className="h-8" />}

      {/* Upload FAB */}
      <button
        type="button"
        onClick={() => setIsUploadOpen(true)}
        className="fixed bottom-6 right-6 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg shadow-accent/30 transition-all duration-300 hover:bg-accent-hover hover:shadow-xl hover:shadow-accent/40 hover:scale-105 active:scale-95"
        aria-label="Upload photos"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
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
