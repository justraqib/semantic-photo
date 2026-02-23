import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { listPhotos } from '../api/photos';

export function usePhotos() {
  const query = useInfiniteQuery({
    queryKey: ['photos'],
    initialPageParam: null,
    queryFn: async ({ pageParam }) => {
      const params = { limit: 50 };
      if (pageParam) params.cursor = pageParam;
      const response = await listPhotos(params);
      return response.data;
    },
    getNextPageParam: (lastPage) => lastPage?.next_cursor || undefined,
  });

  const photos = useMemo(
    () => query.data?.pages.flatMap((page) => page.items || []) || [],
    [query.data]
  );

  return {
    photos,
    fetchNextPage: query.fetchNextPage,
    hasNextPage: query.hasNextPage,
    isLoading: query.isLoading,
  };
}
