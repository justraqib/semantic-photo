import { useEffect, useRef, useState } from 'react';
import Lightbox from '../components/Lightbox';
import SearchBar from '../components/SearchBar';
import SearchResults from '../components/SearchResults';
import SearchEmptyState from '../components/SearchEmptyState';
import { useSearch } from '../hooks/useSearch';

export default function Home() {
  const [query, setQuery] = useState('');
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const sentinelRef = useRef(null);
  const {
    results,
    isLoading: isSearching,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useSearch(query);
  const hasQuery = query.trim().length >= 2;
  const selectedIndex = results.findIndex((p) => p.id === selectedPhoto?.id);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasQuery) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (first?.isIntersecting && hasNextPage) {
          void fetchNextPage();
        }
      },
      { rootMargin: '220px' }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, hasQuery]);

  const onNext = () => {
    if (selectedIndex < 0 || selectedIndex >= results.length - 1) return;
    setSelectedPhoto(results[selectedIndex + 1]);
  };

  const onPrev = () => {
    if (selectedIndex <= 0) return;
    setSelectedPhoto(results[selectedIndex - 1]);
  };

  const clearSearch = () => setQuery('');
  const searchStatus = error?.response?.status;
  const errorMessage =
    searchStatus === 401
      ? 'Session expired. Please login again.'
      : searchStatus === 429
        ? 'Too many searches. Please wait a moment and try again.'
        : 'Search service is temporarily unavailable.';

  return (
    <div className="mx-auto min-h-[calc(100vh-64px)] w-full max-w-[1200px] px-4 pb-32 pt-8 md:px-8 md:pb-10">
      <div className="mb-8 text-center md:mb-10">
        <h1 className="text-2xl font-bold text-foreground md:text-4xl">Search Your Photos</h1>
      </div>

      <SearchBar onSearch={setQuery} onClear={clearSearch} isSearching={isSearching} />

      {isError && (
        <div className="mb-4 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 text-sm text-warning">
          {errorMessage}
        </div>
      )}

      {hasQuery && isSearching && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, idx) => (
            <div key={idx} className="h-36 animate-pulse rounded-xl bg-surface md:h-44" />
          ))}
        </div>
      )}

      {hasQuery && !isSearching && !isError && results.length > 0 && (
        <>
          <SearchResults results={results} onPhotoClick={setSelectedPhoto} />
          <div ref={sentinelRef} className="h-8" />
          {isFetchingNextPage && (
            <div className="mt-3 text-center text-sm text-foreground-muted">Loading more results...</div>
          )}
        </>
      )}

      {hasQuery && !isSearching && !isError && results.length === 0 && (
        <SearchEmptyState query={query} onClear={clearSearch} />
      )}

      {!hasQuery && (
        <div className="rounded-2xl border border-surface-border bg-surface px-6 py-10 text-center">
          <p className="text-foreground-muted">Start typing to search photos.</p>
        </div>
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
