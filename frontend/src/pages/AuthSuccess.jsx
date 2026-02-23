import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

export default function AuthSuccess() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['user'] });
    navigate('/gallery');
  }, []);

  return <div style={{ textAlign: 'center', marginTop: '40vh' }}>Signing you in...</div>;
}
