import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { searchPhotos } from '../api/search';

export function useSearch(query) {
  const normalizedQuery = query.trim();

  const searchQuery = useInfiniteQuery({
    queryKey: ['search', normalizedQuery],
    queryFn: async ({ pageParam = 0 }) => {
      const response = await searchPhotos(normalizedQuery, {
        limit: 40,
        offset: pageParam,
      });
      return response.data;
    },
    enabled: normalizedQuery.length >= 2,
    getNextPageParam: (lastPage) => (lastPage?.has_more ? lastPage?.next_offset : undefined),
    initialPageParam: 0,
    retry: (failureCount, error) => {
      const status = error?.response?.status;
      if ([400, 401, 403, 404, 422, 429, 503].includes(status)) {
        return false;
      }
      return failureCount < 1;
    },
    refetchOnWindowFocus: false,
    staleTime: 60_000,
    gcTime: 60_000,
  });

  const results = useMemo(() => {
    const pages = searchQuery.data?.pages ?? [];
    return pages.flatMap((page) => (Array.isArray(page?.items) ? page.items : []));
  }, [searchQuery.data]);

  return {
    results,
    isLoading: searchQuery.isLoading,
    isError: searchQuery.isError,
    error: searchQuery.error,
    fetchNextPage: searchQuery.fetchNextPage,
    hasNextPage: searchQuery.hasNextPage,
    isFetchingNextPage: searchQuery.isFetchingNextPage,
    isFetching: searchQuery.isFetching,
  };
}
