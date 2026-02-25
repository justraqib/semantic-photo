export default function SearchResults({ results, onPhotoClick }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {results.map((photo) => (
        <button
          key={photo.id}
          type="button"
          onClick={() => onPhotoClick(photo)}
          className="group relative overflow-hidden rounded-xl bg-surface text-left transition-all duration-300 hover:ring-2 hover:ring-accent/30"
        >
          <img
            src={photo.thumbnail_url}
            alt=""
            className="h-40 w-full object-cover transition-transform duration-500 group-hover:scale-105 md:h-48"
            loading="lazy"
          />
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          <div className="absolute left-2 top-2 badge-accent backdrop-blur-sm">
            {Math.round((photo.score || 0) * 100)}% match
          </div>
        </button>
      ))}
    </div>
  );
}
