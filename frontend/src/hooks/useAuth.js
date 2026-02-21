import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMe, logout } from '../api/auth';

export function useAuth() {
  const queryClient = useQueryClient();

  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['user'],
    queryFn: () => getMe().then(r => r.data),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(['user'], null);
      window.location.href = '/login';
    }
  });

  return {
    user,
    isLoading,
    isLoggedIn: !!user && !isError,
    logout: logoutMutation.mutate
  };
}