export default function PhotoCard({ photo, onOpen, renderActions }) {
  const takenAt = photo?.taken_at ? new Date(photo.taken_at) : null;
  const dateLabel = takenAt && !Number.isNaN(takenAt.getTime())
    ? takenAt.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
    : 'Unknown date';

  return (
    <button
      type="button"
      className="group relative overflow-hidden rounded-xl bg-slate-100 text-left"
      onClick={() => onOpen?.(photo)}
    >
      <img
        src={photo?.thumbnail_url}
        alt={photo?.original_filename || 'Photo'}
        className="h-40 w-full object-cover md:h-48"
        loading="lazy"
      />

      <div className="pointer-events-none absolute inset-0 bg-black/0 transition group-hover:bg-black/35" />

      <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/60 px-2 py-1 text-xs text-white opacity-0 transition group-hover:opacity-100">
        {dateLabel}
      </div>

      <label
        className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded bg-white/90 opacity-0 shadow transition group-hover:opacity-100"
        onClick={(e) => e.stopPropagation()}
      >
        <input type="checkbox" className="h-4 w-4" aria-label="Select photo" />
      </label>

      {renderActions && (
        <div
          className="absolute right-2 top-2 opacity-0 transition group-hover:opacity-100"
          onClick={(event) => event.stopPropagation()}
        >
          {renderActions(photo)}
        </div>
      )}
    </button>
  );
}
