import { useQuery } from '@tanstack/react-query';
import { getEmbeddingStatus } from '../api/photos';

export function useEmbeddingStatus() {
  const query = useQuery({
    queryKey: ['embedding-status'],
    queryFn: async () => {
      const response = await getEmbeddingStatus();
      return response.data;
    },
    refetchInterval: 5000,
  });

  return {
    status: query.data || null,
    isLoading: query.isLoading,
  };
}
