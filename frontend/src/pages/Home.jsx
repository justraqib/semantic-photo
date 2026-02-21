import { useAuth } from '../hooks/useAuth';

export default function Home() {
  const { user, isLoading, logout } = useAuth();

  if (isLoading) return <div style={{ textAlign: 'center', marginTop: '40vh' }}>Loading...</div>;

  return (
    <div style={{ padding: '40px', fontFamily: 'Arial' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>📸 Your Gallery</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {user?.avatar_url && (
            <img src={user.avatar_url} alt={user.display_name}
              width={36} height={36} style={{ borderRadius: '50%' }} />
          )}
          <span>{user?.display_name}</span>
          <button onClick={logout} style={{ cursor: 'pointer' }}>Logout</button>
        </div>
      </div>
      <p style={{ color: '#888' }}>Welcome back, {user?.display_name}! 🎉</p>
      <p style={{ color: '#aaa' }}>Photo upload coming in Phase 2.</p>
    </div>
  );
}