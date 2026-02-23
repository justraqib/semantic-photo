import { Link } from 'react-router-dom';

export default function AlbumCard({ album }) {
  return (
    <Link
      to={`/albums/${album.id}`}
      className="group block overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="h-40 w-full bg-slate-200">
        {album.cover_thumbnail_url ? (
          <img
            src={album.cover_thumbnail_url}
            alt={album.name}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            No cover
          </div>
        )}
      </div>
      <div className="flex items-center justify-between px-3 py-3">
        <h3 className="truncate text-sm font-semibold text-slate-900">{album.name}</h3>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
          {album.photo_count}
        </span>
      </div>
    </Link>
  );
}
