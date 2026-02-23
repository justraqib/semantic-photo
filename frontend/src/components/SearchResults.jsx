export default function SearchResults({ results, onPhotoClick }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {results.map((photo) => (
        <button
          key={photo.id}
          type="button"
          onClick={() => onPhotoClick(photo)}
          className="group relative overflow-hidden rounded-xl bg-slate-200 text-left"
        >
          <img
            src={photo.thumbnail_url}
            alt=""
            className="h-40 w-full object-cover transition-transform duration-300 group-hover:scale-105 md:h-48"
            loading="lazy"
          />
          <div className="pointer-events-none absolute left-2 top-2 rounded-full bg-black/60 px-2 py-1 text-xs font-semibold text-white">
            {Math.round((photo.score || 0) * 100)}% match
          </div>
        </button>
      ))}
    </div>
  );
}
