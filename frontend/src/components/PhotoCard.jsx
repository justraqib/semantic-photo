export default function PhotoCard({ photo, onOpen, renderActions }) {
  const takenAt = photo?.taken_at ? new Date(photo.taken_at) : null;
  const dateLabel =
    takenAt && !Number.isNaN(takenAt.getTime())
      ? takenAt.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
      : null;

  return (
    <button
      type="button"
      className="group relative overflow-hidden rounded-xl bg-surface text-left transition-all duration-300 hover:ring-2 hover:ring-accent/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      onClick={() => onOpen?.(photo)}
    >
      <img
        src={photo?.thumbnail_url}
        alt={photo?.original_filename || 'Photo'}
        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        loading="lazy"
      />

      {/* Hover overlay */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

      {/* Date label */}
      {dateLabel && (
        <div className="pointer-events-none absolute bottom-2 left-2 rounded-lg bg-black/60 px-2 py-1 text-xs font-medium text-white/90 opacity-0 transition-all duration-300 group-hover:opacity-100 backdrop-blur-sm">
          {dateLabel}
        </div>
      )}

      {/* Select checkbox */}
      <label
        className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-lg bg-black/40 opacity-0 backdrop-blur-sm transition-all duration-300 group-hover:opacity-100"
        onClick={(e) => e.stopPropagation()}
      >
        <input type="checkbox" className="h-3.5 w-3.5 accent-accent" aria-label="Select photo" />
      </label>

      {/* Custom actions */}
      {renderActions && (
        <div
          className="absolute right-2 top-2 opacity-0 transition-all duration-300 group-hover:opacity-100"
          onClick={(event) => event.stopPropagation()}
        >
          {renderActions(photo)}
        </div>
      )}
    </button>
  );
}
