import { useQuery } from '@tanstack/react-query';
import { getTodayMemory } from '../api/memories';

export function useMemories() {
  const query = useQuery({
    queryKey: ['memories', 'today'],
    queryFn: async () => {
      const response = await getTodayMemory();
      return response.data;
    },
  });

  return {
    memory: query.data || null,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
