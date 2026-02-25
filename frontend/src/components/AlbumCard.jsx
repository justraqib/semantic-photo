import { Link } from 'react-router-dom';

export default function AlbumCard({ album }) {
  return (
    <Link
      to={`/albums/${album.id}`}
      className="group block overflow-hidden rounded-xl border border-surface-border bg-surface transition-all duration-300 hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5"
    >
      <div className="relative h-44 w-full overflow-hidden bg-surface-light">
        {album.cover_thumbnail_url ? (
          <img
            src={album.cover_thumbnail_url}
            alt={album.name}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-foreground-dim">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          </div>
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      </div>
      <div className="flex items-center justify-between px-4 py-3">
        <h3 className="truncate text-sm font-semibold text-foreground">{album.name}</h3>
        <span className="badge-surface ml-2 shrink-0">
          {album.photo_count}
        </span>
      </div>
    </Link>
  );
}
