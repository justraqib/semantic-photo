import { useAuth } from '../hooks/useAuth';

export default function Home() {
  const { user, isLoading, logout } = useAuth();

  if (isLoading) return <div className="mt-[40vh] text-center">Loading...</div>;

  return (
    <div className="min-h-screen p-10">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-3xl font-bold text-slate-900">Your Gallery</h1>
        <div className="flex items-center gap-4">
          {user?.avatar_url && (
            <img src={user.avatar_url} alt={user.display_name}
              width={36} height={36} className="rounded-full" />
          )}
          <span className="text-slate-700">{user?.display_name}</span>
          <button onClick={logout} className="rounded-lg border border-slate-300 px-3 py-2">
            Logout
          </button>
        </div>
      </div>
      <p className="mb-2 text-slate-700">Welcome back, {user?.display_name}.</p>
      <p className="mb-6 text-slate-600">Logged in as: <span className="font-medium">{user?.email}</span></p>
      <p className="text-slate-500">Photo upload coming in Phase 2.</p>
    </div>
  );
}
