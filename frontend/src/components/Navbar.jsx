import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listMapPhotos } from '../api/photos';
import { useAuth } from '../hooks/useAuth';
import { Link, useLocation } from 'react-router-dom';

function NavLink({ to, children }) {
  const { pathname } = useLocation();
  const isActive = pathname === to || pathname.startsWith(to + '/');
  return (
    <Link
      to={to}
      className={`rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 ${
        isActive
          ? 'bg-accent/10 text-accent-light'
          : 'text-foreground-muted hover:bg-surface-hover hover:text-foreground'
      }`}
    >
      {children}
    </Link>
  );
}

function MobileNavLink({ to, children, icon, onClick }) {
  const { pathname } = useLocation();
  const isActive = pathname === to || pathname.startsWith(to + '/');
  return (
    <Link
      to={to}
      onClick={onClick}
      className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
        isActive
          ? 'bg-accent/10 text-accent-light'
          : 'text-foreground-muted hover:bg-surface-hover hover:text-foreground'
      }`}
    >
      {icon}
      {children}
    </Link>
  );
}

function HamburgerIcon({ open }) {
  return (
    <div className="flex h-5 w-5 flex-col items-center justify-center gap-1">
      <span
        className={`block h-0.5 w-5 rounded bg-foreground transition-all duration-300 ${
          open ? 'translate-y-[3px] rotate-45' : ''
        }`}
      />
      <span
        className={`block h-0.5 w-5 rounded bg-foreground transition-all duration-300 ${
          open ? 'opacity-0' : ''
        }`}
      />
      <span
        className={`block h-0.5 w-5 rounded bg-foreground transition-all duration-300 ${
          open ? '-translate-y-[3px] -rotate-45' : ''
        }`}
      />
    </div>
  );
}

export default function Navbar() {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const { data: mapPhotos } = useQuery({
    queryKey: ['map-photos-nav'],
    queryFn: async () => {
      const response = await listMapPhotos();
      return response.data;
    },
    staleTime: 60 * 1000,
  });
  const hasMapPhotos = Array.isArray(mapPhotos) && mapPhotos.length > 0;

  const closeMobile = () => setMobileMenuOpen(false);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-surface-border bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 md:px-8">
          {/* Left: Logo + Desktop nav */}
          <div className="flex items-center gap-6">
            <Link to="/gallery" className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 border border-accent/30">
                <svg width="16" height="16" viewBox="0 0 40 40" fill="none" className="text-accent-light">
                  <rect x="4" y="4" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="2.5" />
                  <rect x="22" y="4" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="2.5" />
                  <rect x="4" y="22" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="2.5" />
                  <circle cx="29" cy="29" r="7" stroke="currentColor" strokeWidth="2.5" />
                  <circle cx="29" cy="29" r="3" fill="currentColor" />
                </svg>
              </div>
              <span className="text-lg font-bold text-foreground">Semantic Photo</span>
            </Link>

            <nav className="hidden items-center gap-1 md:flex">
              <NavLink to="/gallery">Gallery</NavLink>
              <NavLink to="/albums">Albums</NavLink>
              {hasMapPhotos && <NavLink to="/map">Map</NavLink>}
              <NavLink to="/settings">Settings</NavLink>
            </nav>
          </div>

          {/* Right: User + mobile toggle */}
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-3 md:flex">
              {user?.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.display_name || 'User'}
                  className="h-8 w-8 rounded-full ring-2 ring-surface-border"
                />
              ) : (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 text-xs font-semibold text-accent-light ring-2 ring-surface-border">
                  {(user?.display_name || 'U').slice(0, 1).toUpperCase()}
                </div>
              )}
              <span className="text-sm font-medium text-foreground-muted">
                {user?.display_name || user?.email || 'User'}
              </span>
              <button
                type="button"
                onClick={logout}
                className="btn-ghost rounded-lg px-3 py-1.5 text-sm"
              >
                Logout
              </button>
            </div>

            {/* Mobile hamburger */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              className="flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-surface-hover md:hidden"
              aria-label="Toggle menu"
            >
              <HamburgerIcon open={mobileMenuOpen} />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={closeMobile}
          />
          <div className="fixed right-0 top-[57px] z-40 w-72 animate-slide-in-right border-l border-surface-border bg-background/95 backdrop-blur-xl md:hidden"
            style={{ height: 'calc(100vh - 57px)' }}
          >
            <div className="flex flex-col p-4">
              {/* User info */}
              <div className="mb-4 flex items-center gap-3 rounded-xl bg-surface p-3">
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.display_name || 'User'}
                    className="h-10 w-10 rounded-full ring-2 ring-surface-border"
                  />
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/10 text-sm font-semibold text-accent-light ring-2 ring-surface-border">
                    {(user?.display_name || 'U').slice(0, 1).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {user?.display_name || 'User'}
                  </p>
                  <p className="truncate text-xs text-foreground-dim">
                    {user?.email || ''}
                  </p>
                </div>
              </div>

              {/* Nav links */}
              <nav className="flex flex-col gap-1">
                <MobileNavLink
                  to="/gallery"
                  onClick={closeMobile}
                  icon={
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="3" width="7" height="7" rx="1" />
                      <rect x="14" y="3" width="7" height="7" rx="1" />
                      <rect x="3" y="14" width="7" height="7" rx="1" />
                      <rect x="14" y="14" width="7" height="7" rx="1" />
                    </svg>
                  }
                >
                  Gallery
                </MobileNavLink>

                <MobileNavLink
                  to="/albums"
                  onClick={closeMobile}
                  icon={
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                  }
                >
                  Albums
                </MobileNavLink>

                {hasMapPhotos && (
                  <MobileNavLink
                    to="/map"
                    onClick={closeMobile}
                    icon={
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                        <circle cx="12" cy="10" r="3" />
                      </svg>
                    }
                  >
                    Map
                  </MobileNavLink>
                )}

                <MobileNavLink
                  to="/settings"
                  onClick={closeMobile}
                  icon={
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                    </svg>
                  }
                >
                  Settings
                </MobileNavLink>
              </nav>

              {/* Logout */}
              <div className="mt-auto pt-4 border-t border-surface-border mt-6">
                <button
                  type="button"
                  onClick={() => {
                    closeMobile();
                    logout();
                  }}
                  className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-foreground-muted transition-all duration-200 hover:bg-surface-hover hover:text-foreground"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                  Logout
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
