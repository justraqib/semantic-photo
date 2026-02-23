import { useAuth } from '../hooks/useAuth';
import { Link } from 'react-router-dom';

export default function Navbar() {
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 md:px-8">
        <div className="flex items-center gap-4">
          <Link to="/gallery" className="text-lg font-bold text-slate-900">Semantic Photo</Link>
          <Link to="/gallery" className="text-sm text-slate-600 hover:text-slate-900">Gallery</Link>
          <Link to="/albums" className="text-sm text-slate-600 hover:text-slate-900">Albums</Link>
          <Link to="/settings" className="text-sm text-slate-600 hover:text-slate-900">Settings</Link>
        </div>

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
