import { useAuth } from '../hooks/useAuth';

export default function Home() {
  const { user, isLoading, logout } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-surface-border border-t-accent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-10">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Your Gallery</h1>
        <div className="flex items-center gap-4">
          {user?.avatar_url && (
            <img src={user.avatar_url} alt={user.display_name}
              width={36} height={36} className="rounded-full ring-2 ring-surface-border" />
          )}
          <span className="text-foreground-muted">{user?.display_name}</span>
          <button onClick={logout} className="btn-secondary text-sm">
            Logout
          </button>
        </div>
      </div>
      <p className="mb-2 text-foreground-muted">Welcome back, {user?.display_name}.</p>
      <p className="mb-6 text-foreground-dim">Logged in as: <span className="font-medium text-foreground">{user?.email}</span></p>
    </div>
  );
}
