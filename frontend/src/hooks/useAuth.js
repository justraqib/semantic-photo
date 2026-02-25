import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMe, logout } from '../api/auth';

const DEV_PREVIEW = !import.meta.env.VITE_API_URL && typeof window !== 'undefined' && !window.location.hostname.includes('localhost:8000');

const DEMO_USER = {
  id: 'demo',
  display_name: 'Demo User',
  email: 'demo@example.com',
  avatar_url: null,
};

export function useAuth() {
  const queryClient = useQueryClient();

  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['user'],
    queryFn: () => {
      if (DEV_PREVIEW) return Promise.resolve(DEMO_USER);
      return getMe().then(r => r.data);
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const logoutMutation = useMutation({
    mutationFn: () => {
      if (DEV_PREVIEW) return Promise.resolve();
      return logout();
    },
    onSuccess: () => {
      queryClient.setQueryData(['user'], null);
      window.location.href = '/login';
    }
  });

  return {
    user: DEV_PREVIEW ? (user || DEMO_USER) : user,
    isLoading: DEV_PREVIEW ? false : isLoading,
    isLoggedIn: DEV_PREVIEW ? true : (!!user && !isError),
    logout: logoutMutation.mutate
  };
}
