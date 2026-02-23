import { useQuery } from '@tanstack/react-query';
import { listAlbums } from '../api/albums';

export function useAlbums() {
  const query = useQuery({
    queryKey: ['albums'],
    queryFn: async () => {
      const response = await listAlbums();
      return response.data;
    },
  });

  return {
    albums: query.data || [],
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}
