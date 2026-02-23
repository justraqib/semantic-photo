import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchPhotos } from '../api/search';

export function useSearch(query) {
  const normalizedQuery = query.trim();

  const searchQuery = useQuery({
    queryKey: ['search', normalizedQuery],
    queryFn: async () => {
      const response = await searchPhotos(normalizedQuery);
      return response.data;
    },
    enabled: normalizedQuery.length >= 2,
    staleTime: 60_000,
    gcTime: 60_000,
  });

  const results = useMemo(
    () => (Array.isArray(searchQuery.data) ? searchQuery.data : []),
    [searchQuery.data]
  );

  return {
    results,
    isLoading: searchQuery.isLoading,
    isError: searchQuery.isError,
  };
}
