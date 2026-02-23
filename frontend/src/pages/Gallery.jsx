import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import EmptyState from '../components/EmptyState';
import Lightbox from '../components/Lightbox';
import PhotoGrid from '../components/PhotoGrid';
import SearchEmptyState from '../components/SearchEmptyState';
import SearchBar from '../components/SearchBar';
import SearchResults from '../components/SearchResults';
import UploadModal from '../components/UploadModal';
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
  const { results: searchResults, isLoading: isSearching } = useSearch(query);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const sentinelRef = useRef(null);
  const isSearchActive = query.trim().length >= 2;
  const clearSearch = () => setQuery('');

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
      <SearchBar
        onSearch={setQuery}
        onClear={clearSearch}
        isSearching={isSearching}
      />

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

      {!isSearchActive && photos.length > 0 && (
        <PhotoGrid photos={photos} onPhotoClick={setSelectedPhoto} />
      )}

      {isSearchActive && (
        <>
          {!isSearching && searchResults.length === 0 && (
            <SearchEmptyState query={query} onClear={clearSearch} />
          )}
          {searchResults.length > 0 && (
            <SearchResults results={searchResults} onPhotoClick={setSelectedPhoto} />
          )}
        </>
      )}

      {!isSearchActive && <div ref={sentinelRef} className="h-8" />}

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
        onUploaded={() => queryClient.invalidateQueries({ queryKey: ['photos'] })}
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
