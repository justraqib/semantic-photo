import { useAuth } from '../hooks/useAuth';

export default function Navbar() {
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 md:px-8">
        <div className="text-lg font-bold text-slate-900">Semantic Photo</div>

        <div className="flex items-center gap-3">
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt={user.display_name || 'User'} className="h-8 w-8 rounded-full" />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-300 text-xs font-semibold text-slate-700">
              {(user?.display_name || 'U').slice(0, 1).toUpperCase()}
            </div>
          )}
          <span className="text-sm font-medium text-slate-700">{user?.display_name || user?.email || 'User'}</span>
        </div>
      </div>
    </header>
  );
}
